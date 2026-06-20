# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
The OPERADUM -> KOMPOSOS Round-Trip

Closes the loop from master spec S13: OPERADUM designs, KOMPOSOS audits.

    design  = wright.synthesize(spec)        # OPERADUM builds it
    graph   = compile_to_komposos(design)    # operations -> morphisms
    verdict = KomposVerifier().verify(...)    # KOMPOSOS interprets/verifies it

The verifier reconstructs the design as a categorical structure and checks two
things KOMPOSOS would check:

  1. Structure preservation -- every operation became a morphism, and there is
     a categorical path from each design input object to the target object. The
     base engine can "follow" the route OPERADUM built.

  2. Round-trip soundness -- the categorical confidence KOMPOSOS computes by
     composing the morphism graph equals the homomorphic image of OPERADUM's
     own resource accounting: product(confidences) == cost_to_confidence(total
     cost). Because each reaction's confidence is exp(-lambda * cost) and the
     additive monoid sums costs, this is an exact monoid homomorphism
     (additive cost -> multiplicative confidence). It is the *theorem* behind
     "both engines agree on the same structure."

KOMPOSOS itself is cartesian and multiplicative; we mirror its Category.compose
(g.f confidence = f.confidence * g.confidence) in a dependency-free MiniCategory
so the round-trip always runs, and use the real KOMPOSOS-IV Category when its
path is provided.
"""

from __future__ import annotations
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.operad import Operad
from ..core.types import Composite
from ..core.enrichment import ResourceError
from .komposos_bridge import compile_to_komposos, cost_to_confidence, MorphismGraph


# ===================================================================
# MiniCategory -- the relevant slice of KOMPOSOS-IV's Category
# ===================================================================

class MiniCategory:
    """
    A dependency-free multiplicative-quantale category mirroring
    KOMPOSOS-IV's Category: composition multiplies confidences, and a path's
    weight is the product of its edge confidences (higher = better).
    """

    def __init__(self, name: str = "operadum_roundtrip"):
        self.name = name
        self.objects: set[str] = set()
        # adjacency: source colour -> list of (target, confidence, morphism name)
        self._adj: Dict[str, List[Tuple[str, float, str]]] = defaultdict(list)

    def add(self, obj: str) -> None:
        self.objects.add(obj)

    def connect(self, source: str, target: str, name: str, confidence: float) -> None:
        self.add(source); self.add(target)
        self._adj[source].append((target, confidence, name))

    def compose_path(self, source: str, target: str) -> Optional[float]:
        """Best (highest-confidence) categorical path source -> target, by
        multiplicative composition. None if no path exists."""
        if source == target:
            return 1.0
        best: Dict[str, float] = {source: 1.0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for nxt, conf, _name in self._adj.get(node, []):
                w = best[node] * conf
                if w > best.get(nxt, -1.0):
                    best[nxt] = w
                    queue.append(nxt)
        return best.get(target)


# ===================================================================
# Verdicts and verifier
# ===================================================================

@dataclass
class RoundTripResult:
    """The outcome of verifying an OPERADUM design through KOMPOSOS."""
    verdict: str                       # AGREE / HOLLOW / REJECT (COG-style)
    structure_preserved: bool
    sound: bool                        # confidences match the homomorphism
    composed_confidence: float
    expected_confidence: float
    engine: str                        # "komposos" or "mini"
    detail: str = ""

    @property
    def agrees(self) -> bool:
        return self.verdict == "AGREE"

    def __str__(self) -> str:
        return (f"[{self.verdict}] engine={self.engine} "
                f"composed={self.composed_confidence:.4f} "
                f"expected={self.expected_confidence:.4f} "
                f"({'sound' if self.sound else 'lossy'})")


class KomposVerifier:
    """
    Verifies that a design, compiled to a morphism graph, is categorically
    sound -- the constructive payoff of keeping both engines symmetric-monoidal
    at the bottom.
    """

    def __init__(self, lam: float = 0.05, tol: float = 1e-9,
                 komposos_path: Optional[str] = None):
        self.lam = lam
        self.tol = tol
        self.komposos_path = komposos_path   # if set, attempt the real KOMPOSOS

    def verify(self, comp: Composite, operad: Operad) -> RoundTripResult:
        graph = compile_to_komposos(comp, operad, self.lam)
        engine = self._ingest(graph)

        # 1. Structure preservation: a categorical path input -> output exists.
        cat = MiniCategory()
        for m in graph.morphisms:
            for c in m["input_colours"]:
                cat.connect(c, m["target"], m["name"], m["confidence"])
        inputs = list(dict.fromkeys(comp.open_inputs()))
        root = comp.output
        if inputs:
            paths = {i: cat.compose_path(i, root) for i in inputs}
            structure_ok = all(p is not None for p in paths.values())
        else:
            structure_ok = root in graph.objects   # closed design produces root

        # 2. Round-trip soundness: composed confidence == homomorphic image.
        try:
            total_cost = comp.cost(operad.monoid)
            expected = cost_to_confidence(total_cost, self.lam)
        except ResourceError:
            # Resource-unsound design: nothing for KOMPOSOS to agree with.
            return RoundTripResult("REJECT", False, False, 0.0, 0.0, engine,
                                   "design is resource-unsound")
        composed = 1.0
        for m in graph.morphisms:
            composed *= m["confidence"]
        sound = math.isclose(composed, expected, rel_tol=0.0, abs_tol=self.tol)

        if structure_ok and sound:
            verdict = "AGREE"
        elif structure_ok:
            verdict = "HOLLOW"   # follows structurally, but resource map is lossy
        else:
            verdict = "REJECT"

        return RoundTripResult(
            verdict=verdict,
            structure_preserved=structure_ok,
            sound=sound,
            composed_confidence=composed,
            expected_confidence=expected,
            engine=engine,
            detail=(f"path(s) {inputs} -> {root} "
                    f"{'found' if structure_ok else 'MISSING'}; "
                    f"homomorphism {'holds' if sound else 'lossy under '+operad.monoid.name}"),
        )

    # ---------------- engine ingestion ----------------

    def _ingest(self, graph: MorphismGraph) -> str:
        """Build the category in the real KOMPOSOS if available, else MiniCategory.

        Returns the engine name actually used. The verdict logic above is
        engine-independent; this proves the graph is *ingestible* by the real
        base engine when present.
        """
        if not self.komposos_path:
            return "mini"
        try:
            import sys
            if self.komposos_path not in sys.path:
                sys.path.insert(0, self.komposos_path)
            from core.category import Category  # KOMPOSOS-IV fused runtime
            cat = Category("operadum_roundtrip")
            for obj in graph.objects:
                cat.add(obj)
            for m in graph.morphisms:
                cat.connect(m["source"], m["target"], name=m["name"],
                            confidence=m["confidence"])
            return "komposos"
        except Exception:
            return "mini"
