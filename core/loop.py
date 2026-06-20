# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
SelfImprovementLoop — the spine, with all five engines wired in.

One running loop over a shared capability graph:

    OPTIMUS    observe : find structural holes (A->B->C exists, no direct A->C)
    OPERADUM   design  : synthesize candidate routes source->target and
                         type/resource-verify them (verdict BUILDABLE/…)
    PRONOIA    predict : rank candidate routes by MDL compression gain +
                         honesty grounding; pick the best-grounded one
    HOST       build   : hot-load a plugin for the winning capability
                         (its on_start writes the new morphism into the graph)
    COG        judge   : dual-engine verdict (AGREE/ORPHAN/HOLLOW/REJECT);
                         REJECT is rolled back

Each iteration mutates the graph, so the next observe sees fewer/new holes; the
loop runs to convergence or a budget. No git, no telemetry, no Orion — just the
Category and the real engines.

OPERADUM/PRONOIA are optional: if `operadum` isn't importable the loop degrades
to OPTIMUS+HOST+COG (design/predict columns report "n/a").

Run:
    python -m core.loop
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.category import Category
from core.executable_synthesis import ExecutableSynthesizer
from core.honesty_gate import HonestyGate
from core.host import Host, build_host
from core.optimus import OptimusEngine
from core.plugin_generator import SelfExtensionEngine

logger = logging.getLogger(__name__)

# A route is an ordered list of (source, target, relation, confidence) edges.
Route = List[Tuple[str, str, str, float]]


# ══════════════════════════════════════════════════════════════════════════════
# OPERADUM + PRONOIA loader (optional)
# ══════════════════════════════════════════════════════════════════════════════

def _load_design():
    """Import OPERADUM (design) + PRONOIA (predict), or return None if absent."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    operadum_root = os.path.join(repo_root, "operadum")
    if operadum_root not in sys.path:
        sys.path.insert(0, operadum_root)
    try:
        from operadum import Operad, Spec, Wright
        from pronoia import Hypothesis, honest_rank
        return {
            "Operad": Operad, "Spec": Spec, "Wright": Wright,
            "Hypothesis": Hypothesis, "honest_rank": honest_rank,
        }
    except Exception as exc:  # pragma: no cover - depends on operadum presence
        logger.debug("OPERADUM/PRONOIA unavailable, loop runs without design: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Result records
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FillResult:
    source: str
    target: str
    via: str
    path_confidence: float
    capability: str
    operadum_verdict: str   # BUILDABLE / OVERBUDGET / ILL_TYPED_GAP / IMPOSSIBLE / n/a
    pronoia_gain: float     # MDL compression gain (bits) of the chosen route
    pronoia_honest: bool    # was the chosen route's rationale grounded in evidence?
    loaded: bool
    cog_verdict: str        # AGREE / ORPHAN / HOLLOW / REJECT / PENDING / error
    kept: bool
    route: str = ""
    note: str = ""
    # Grounding: did we synthesize a real, runnable composite and verify it?
    executed: Optional[bool] = None       # composite actually ran on a probe
    runtime_verified: Optional[bool] = None  # composite == spine composite (ground truth)
    grounding: Optional[float] = None     # honesty: [0,1] fraction grounded in evidence


@dataclass
class IterationReport:
    gaps_found: int
    fills: List[FillResult] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return sum(1 for f in self.fills if f.kept)


# ══════════════════════════════════════════════════════════════════════════════
# Designer: OPERADUM designs, PRONOIA ranks
# ══════════════════════════════════════════════════════════════════════════════

class _Designer:
    """Turns a structural gap into a ranked, type-verified design decision."""

    def __init__(self, category: Category, deps: Dict[str, Any], max_depth: int = 4):
        self.category = category
        self.deps = deps
        self.max_depth = max_depth

    # ---- candidate routes from the live graph (each is a "way to build target") ----

    def candidate_routes(self, source: str, target: str) -> List[Route]:
        routes: List[Route] = []

        def dfs(node: str, path: Route, seen: set):
            if len(path) > self.max_depth:
                return
            for m in self.category.morphisms_from(node):
                if m.target in seen:
                    continue
                edge = (m.source, m.target, m.name, float(m.confidence))
                if m.target == target:
                    routes.append(path + [edge])
                else:
                    dfs(m.target, path + [edge], seen | {m.target})

        dfs(source, [], {source})
        return routes

    # ---- OPERADUM: design + type/resource-verify a route source->target ----

    def operadum_verdict(self, source: str, target: str) -> Tuple[str, str]:
        """Build an operad from the whole graph and ask WRIGHT to design source->target."""
        Operad, Spec, Wright = self.deps["Operad"], self.deps["Spec"], self.deps["Wright"]
        op = Operad(f"gap-{source}-{target}")
        for m in self.category.morphisms():
            # morphism A->B becomes a build rule (A,) -> B; cost = 1 - confidence
            # (higher confidence ⇒ cheaper to build), additive by default.
            op.add_op(m.name, [m.source], m.target,
                      cost={"w": round(1.0 - float(m.confidence), 3)})
        try:
            result = Wright(op, max_depth=self.max_depth).synthesize(
                Spec(inputs=(source,), output=target)
            )
        except Exception as exc:
            return "error", str(exc)
        verdict = getattr(result.verdict, "name", str(result.verdict))
        route_str = ""
        if getattr(result, "construction", None) is not None:
            route_str = self._composite_str(result.construction.composite)
        return verdict, route_str

    @staticmethod
    def _composite_str(composite: Any) -> str:
        try:
            return f"{'->'.join(composite.open_inputs())}=>{composite.output()}"
        except Exception:
            return repr(composite)[:60]

    # ---- PRONOIA: rank candidate routes by MDL compression + honesty ----

    def pronoia_rank(self, source: str, target: str,
                     routes: List[Route]) -> Tuple[Optional[Route], float, bool]:
        """Return (winning_route, gain_bits, honest) by honest MDL ranking."""
        Hypothesis, honest_rank = self.deps["Hypothesis"], self.deps["honest_rank"]
        if not routes:
            return None, 0.0, False

        evidence = self._graph_evidence()
        hyps, by_name = [], {}
        for i, route in enumerate(routes):
            claim = self._route_claim(route)
            name = f"route{i}"
            hyps.append(Hypothesis(name=name, claim=claim))
            by_name[name] = route

        ranked = honest_rank(evidence, hyps, min_grounding=0.5)
        if not ranked:
            return routes[0], 0.0, False
        best = ranked[0]
        return by_name[best.hypothesis.name], float(best.gain_bits), bool(best.honest)

    def _graph_evidence(self) -> str:
        lines = [f"{m.source} {m.name} {m.target} {round(float(m.confidence), 2)}"
                 for m in self.category.morphisms()]
        return "\n".join(sorted(lines))

    @staticmethod
    def _route_claim(route: Route) -> str:
        # Repeat the route text so a route reusing known high-frequency edges
        # compresses the evidence more (higher MDL gain) — the signal we rank on.
        steps = [f"{s} {n} {t} {round(c, 2)}" for (s, t, n, c) in route]
        return " ; ".join(steps * 3)


# ══════════════════════════════════════════════════════════════════════════════
# COG gate
# ══════════════════════════════════════════════════════════════════════════════

class _CogGate:
    def __init__(self, category: Category):
        from cog.session import CogSession
        from cog.engine import CogEngine
        self._engine = CogEngine(CogSession(category=category))

    def verdict(self, source: str, target: str, relation: str, confidence: float) -> str:
        from cog.schema import CogClaim
        claim = CogClaim(source=source, target=target, relation=relation,
                         confidence=confidence)
        try:
            return self._engine.check_claim(claim).status.name
        except Exception:
            logger.exception("COG verification failed for %s->%s", source, target)
            return "error"


# ══════════════════════════════════════════════════════════════════════════════
# The loop
# ══════════════════════════════════════════════════════════════════════════════

class SelfImprovementLoop:
    """Observe → design → predict → build → judge, over one shared Category."""

    def __init__(
        self,
        category: Optional[Category] = None,
        host: Optional[Host] = None,
        *,
        relation: str = "derived",
        max_depth: int = 3,
        gate_with_cog: bool = True,
        use_design: bool = True,
        observer: str = "optimus",
        embeddings: Any = None,
        min_grounding: float = 0.5,
    ):
        self.category = category or Category(db_path=":memory:")
        self.host = host or build_host()
        self.relation = relation
        self.max_depth = max_depth
        self.observer = observer
        self._embeddings = embeddings
        self._extender = SelfExtensionEngine(orion_core=self.host, category=self.category)
        self._synth = ExecutableSynthesizer(self.category, max_depth=max_depth + 1)
        self._honesty = HonestyGate(min_grounding=min_grounding)
        self._cog = _CogGate(self.category) if gate_with_cog else None

        deps = _load_design() if use_design else None
        self._designer = _Designer(self.category, deps, max_depth + 1) if deps else None

    @property
    def design_enabled(self) -> bool:
        return self._designer is not None

    # ---------------- observe ----------------

    def _observe(self) -> List[Dict[str, Any]]:
        """Surface structural gaps to fill, as {source, target, via, path_confidence}.

        observer="optimus" (default): OPTIMUS composition holes (A->B->C, no A->C).
        observer="conjecture": ORACLE's proactive ConjectureEngine — six structural
            generators (composition, structural_hole, fiber, temporal, yoneda, and
            semantic when embeddings are present). Strictly broader than OPTIMUS;
            runs embedding-free via surface_candidates().
        """
        if self.observer == "conjecture":
            try:
                return self._observe_conjecture()
            except Exception:
                logger.exception("conjecture observe failed; falling back to OPTIMUS")
        return OptimusEngine(self.category, max_depth=self.max_depth).find_structural_gaps()

    def _observe_conjecture(self) -> List[Dict[str, Any]]:
        from oracle.conjecture import ConjectureEngine

        engine = ConjectureEngine.from_category(
            self.category, embeddings=self._resolve_embeddings()
        )
        pair_sources = engine.surface_candidates()

        # Index 2-hop paths once so we can attach a `via` + composite confidence
        # (matching OPTIMUS's gap shape) to candidates that have a mechanistic spine.
        gaps: List[Dict[str, Any]] = []
        for (source, target), provenance in pair_sources.items():
            via, path_conf = self._best_spine(source, target)
            if via is None:
                # No 2-hop spine (e.g. fiber / yoneda / temporal candidate): seed a
                # modest confidence that rewards multi-generator support (breadth).
                via = "+".join(sorted(set(provenance)))
                path_conf = min(0.6, 0.4 + 0.05 * (len(set(provenance)) - 1))
            gaps.append({
                "source": source,
                "target": target,
                "via": via,
                "path_confidence": path_conf,
                "generators": sorted(set(provenance)),
            })

        gaps.sort(key=lambda g: g["path_confidence"], reverse=True)
        return gaps

    def _resolve_embeddings(self):
        """Resolve the embeddings backend for semantic proposals.

        None  -> embedding-free (default; structural generators only).
        "auto"-> build a real EmbeddingsEngine and FIT it on the LIVE graph each
                 observe, so the soft-Yoneda structural vectors track graph growth.
                 This activates the semantic candidate generator — the continuous
                 proposal layer — on the proposal side only; the gates still verify.
        <engine> -> use as given.
        """
        if self._embeddings == "auto":
            from data.embeddings import EmbeddingsEngine
            return EmbeddingsEngine().fit(self.category)
        return self._embeddings

    def _best_spine(self, source: str, target: str) -> Tuple[Optional[str], float]:
        """Best 2-hop intermediate source->B->target and its composite confidence."""
        best_via: Optional[str] = None
        best_conf = 0.0
        for m1 in self.category.morphisms_from(source):
            if m1.target in (source, target):
                continue
            for m2 in self.category.morphisms_from(m1.target):
                if m2.target == target:
                    conf = float(m1.confidence) * float(m2.confidence)
                    if conf > best_conf:
                        best_conf, best_via = conf, m1.target
        return best_via, best_conf

    # ---------------- one cycle ----------------

    async def step(self, *, max_fills: int = 10) -> IterationReport:
        gaps = self._observe()
        report = IterationReport(gaps_found=len(gaps))
        for gap in gaps[:max_fills]:
            report.fills.append(await self._fill_gap(gap))
        return report

    async def _fill_gap(self, gap: Dict[str, Any]) -> FillResult:
        source, target, via = gap["source"], gap["target"], gap["via"]
        conf = float(gap.get("path_confidence", 0.5))

        # ---- design (OPERADUM) + predict (PRONOIA) ----
        operadum_verdict, route_str = "n/a", ""
        pronoia_gain, pronoia_honest = 0.0, True
        if self._designer is not None:
            operadum_verdict, designed = self._designer.operadum_verdict(source, target)
            if designed:
                route_str = designed
            routes = self._designer.candidate_routes(source, target)
            winner, pronoia_gain, pronoia_honest = self._designer.pronoia_rank(
                source, target, routes
            )
            if winner:
                route_str = " -> ".join([source] + [e[1] for e in winner])

            # OPERADUM says it can't be built at all → don't synthesize a phantom edge.
            if operadum_verdict in ("IMPOSSIBLE", "ILL_TYPED_GAP"):
                return FillResult(source, target, via, conf,
                                  capability=f"{source}_to_{target}",
                                  operadum_verdict=operadum_verdict,
                                  pronoia_gain=pronoia_gain, pronoia_honest=pronoia_honest,
                                  loaded=False, cog_verdict="skipped", kept=False,
                                  route=route_str, note="OPERADUM: not buildable")

        # ---- build (HOST): hot-load a plugin for the winning capability ----
        result = await self._extender.implement_missing_primitive(
            source=source, target=target, relation=self.relation, confidence=conf,
            evidence={"loop": "self_improvement", "via": via, "route": route_str,
                      "operadum": operadum_verdict, "pronoia_gain": pronoia_gain},
            auto_load=True,
        )
        capability = result.get("spec", {}).get("name", f"{source}_to_{target}")
        loaded = bool(result.get("loaded"))
        if not loaded:
            issues = result.get("verification", {}).get("issues", [])
            return FillResult(source, target, via, conf, capability, operadum_verdict,
                              pronoia_gain, pronoia_honest, loaded=False,
                              cog_verdict="not_loaded", kept=False, route=route_str,
                              note="; ".join(issues))

        # ---- ground (EXECUTABLE SYNTHESIS): build a real composite and run it ----
        # The plugin wrote a structural edge; now turn it into a working function.
        executed: Optional[bool] = None
        runtime_verified: Optional[bool] = None
        synth = self._synth.synthesize(source, target)
        if synth.executable:
            executed = synth.executed
            runtime_verified = synth.verified
            if synth.verified:
                # Upgrade the structural edge to the verified, runnable composite.
                self._synth.install(source, target, self.relation, synth)
            else:
                # We synthesized a capability that does NOT actually compute the
                # claimed composite. That is a real failure — don't keep a lie.
                await self.host.unload_capability(capability)
                self._remove_edge(source, target)
                return FillResult(source, target, via, conf, capability, operadum_verdict,
                                  pronoia_gain, pronoia_honest, loaded=True,
                                  cog_verdict="skipped", kept=False, route=route_str,
                                  note=f"runtime check failed: {synth.note}",
                                  executed=executed, runtime_verified=runtime_verified)

        # ---- judge (COG) ----
        cog_verdict = "PENDING"
        if self._cog is not None:
            cog_verdict = self._cog.verdict(source, target, self.relation, conf)

        # ---- remember-gate (HONESTY): is the claim grounded in committed evidence? ----
        # COG says the claim is well-formed; the honesty gate says it isn't fabricated.
        # Both must hold to let it persist. Route text (the mechanism) is the rationale.
        honesty = self._honesty.check_claim(
            self.category, source, target, self.relation,
            claim=self._supporting_claim(source, target),
        )

        kept = (cog_verdict != "REJECT") and honesty.honest
        if not kept:
            await self.host.unload_capability(capability)
            self._remove_edge(source, target)

        note = synth.note
        if not honesty.honest:
            note = f"{honesty.reason}; {note}"
        return FillResult(source, target, via, conf, capability, operadum_verdict,
                          pronoia_gain, pronoia_honest, loaded=True,
                          cog_verdict=cog_verdict, kept=kept, route=route_str,
                          note=note, grounding=honesty.grounding,
                          executed=executed, runtime_verified=runtime_verified)

    def _supporting_claim(self, source: str, target: str) -> Optional[str]:
        """The rationale for edge source->target, as the actual supporting path
        serialized in the SAME vocabulary as the committed evidence. A real
        mechanism reuses known edges (high grounding); a fabricated edge has no
        supporting path, so the claim degrades to the bare edge (low grounding)."""
        path = self._find_path(source, target)
        if not path:
            return None
        return "\n".join(
            f"{m.source} {m.name} {m.target} {round(float(m.confidence), 2)}"
            for m in path
        )

    def _find_path(self, source: str, target: str) -> List[Any]:
        """Shortest morphism path source->...->target (excludes the candidate
        edge itself, i.e. the just-written self.relation edge)."""
        best: List[Any] = []

        def dfs(node: str, path: List[Any], seen: set):
            nonlocal best
            if best or len(path) > self.max_depth + 1:
                return
            for m in self.category.morphisms_from(node):
                if m.target in seen:
                    continue
                if m.source == source and m.target == target and m.name == self.relation:
                    continue  # don't let the candidate ground itself
                if m.target == target:
                    best = path + [m]
                    return
                dfs(m.target, path + [m], seen | {m.target})

        dfs(source, [], {source})
        return best

    def _remove_edge(self, source: str, target: str) -> None:
        for m in list(self.category.morphisms()):
            if m.source == source and m.target == target and m.name == self.relation:
                remover = getattr(self.category, "remove_morphism", None)
                if callable(remover):
                    remover(m.id)

    # ---------------- run to convergence ----------------

    async def run(self, *, max_iterations: int = 5, max_fills: int = 10) -> List[IterationReport]:
        history: List[IterationReport] = []
        for i in range(max_iterations):
            report = await self.step(max_fills=max_fills)
            history.append(report)
            logger.info("iteration %d: %d gaps, %d kept", i, report.gaps_found, report.kept)
            if report.kept == 0:
                break
        return history


# ══════════════════════════════════════════════════════════════════════════════
# Demo
# ══════════════════════════════════════════════════════════════════════════════

def _seed_demo_category() -> Category:
    """Seed with EXECUTABLE morphisms (real str->str functions), so a filled gap
    is an actual composite the loop can build, run, and verify — not a stub."""
    cat = Category(db_path=":memory:")
    cat.connect("parse", "search", name="emits", confidence=0.8, fn=lambda s: s.strip())
    cat.connect("search", "index", name="feeds", confidence=0.9, fn=lambda s: s.lower())
    cat.connect("index", "store", name="writes", confidence=0.85, fn=lambda s: s.replace(" ", "_"))
    return cat


async def _demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # observer=optimus (default) or conjecture (ORACLE's proactive engine).
    # Override with: KOMPOSOS_OBSERVER=conjecture python -m core.loop
    observer = os.environ.get("KOMPOSOS_OBSERVER", "optimus")
    loop = SelfImprovementLoop(category=_seed_demo_category(), observer=observer)

    print(f"host backend : {getattr(loop.host, 'backend', '?')}")
    print(f"design engines: {'OPERADUM+PRONOIA' if loop.design_enabled else 'OFF'}")
    print(f"observe      : {loop.observer}")
    print(f"start        : {len(loop.category.morphisms())} morphisms\n")

    history = await loop.run(max_iterations=5)

    for i, rep in enumerate(history):
        print(f"iteration {i}: {rep.gaps_found} holes, {rep.kept} kept")
        for f in rep.fills:
            flag = "kept" if f.kept else "ROLLED BACK"
            run = "—" if f.executed is None else ("ran+verified" if f.runtime_verified else "FAILED")
            grnd = "—" if f.grounding is None else f"{f.grounding:.2f}"
            print(f"   {f.source:>6} -> {f.target:<6}  "
                  f"OPERADUM={f.operadum_verdict:<9} "
                  f"EXEC={run:<12} "
                  f"HONESTY={grnd:<5} "
                  f"COG={f.cog_verdict:<6} [{flag}]")

    print(f"\nend          : {len(loop.category.morphisms())} morphisms")
    print(f"capabilities : {loop.host.capabilities_available}")

    # Proof of grounding: the loop didn't just assert search->store exists — it
    # built a working function. Invoke it directly from the graph.
    for m in loop.category.morphisms_from("search"):
        if m.target == "store" and m.is_callable:
            probe = "Hello World "
            print(f"\nrun built capability  search->store('{probe}') = '{m(probe)}'  "
                  f"(= probe.lower().replace(' ','_'), the verified composite)")
            break


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
