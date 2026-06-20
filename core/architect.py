# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Architectural Self-Correction (Ruliad Engine + InfinityCosmos)

Combines the Ruliad Engine's self-observation with the ∞-cosmos framework
to find wrong boundaries, missing primitives, and redundant capabilities
at BOTH the 1-morphism level (OPTIMUS) AND the 2-cell level (∞-cosmos).

The self-correction loop from the Ruliad essay:
    observe -> identify wrong boundaries -> propose -> validate -> repeat

This uses:
- Telemetry data (runtime behavior)
- Git history (co-modification patterns)
- OPTIMUS on capability graph (factorization, structural holes)
- InfinityCosmos on capability graph (2-cell reasoning, fibrations, Yoneda)

Usage:
    advisor = ArchitecturalAdvisor(
        orion_core=core,
        telemetry_category=telem_cat,
        repo_path=".",
    )
    report = await advisor.analyze()

    for rec in report["recommendations"]:
        print(f"[{rec['type']}] {rec['description']} (conf={rec['confidence']:.2f})")
"""

from __future__ import annotations

import subprocess
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .category import Category


class GitArchitectureAnalyzer:
    """Extract architectural signals from git history."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def co_modification_matrix(self, since: str = "6 months ago") -> dict:
        """Which files/modules change together across commits?

        Returns: {("module_a", "module_b"): commit_count}
        """
        try:
            result = subprocess.run(
                ["git", "log", "--name-only", "--format=COMMIT_SEP",
                 f"--since={since}"],
                capture_output=True, text=True, cwd=self.repo_path,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {}

        commits = result.stdout.split("COMMIT_SEP")
        comod: Dict[tuple, int] = defaultdict(int)

        for commit in commits:
            files = [f.strip() for f in commit.strip().split("\n") if f.strip()]
            modules = set(self._file_to_module(f) for f in files)
            modules.discard(None)
            for a in modules:
                for b in modules:
                    if a < b:
                        comod[(a, b)] += 1

        return dict(comod)

    def abandoned_experiments(self, since: str = "6 months ago") -> list:
        """Find branches/commits that were reverted or abandoned."""
        try:
            result = subprocess.run(
                ["git", "log", "--diff-filter=D", "--name-only",
                 "--format=%H %s", f"--since={since}"],
                capture_output=True, text=True, cwd=self.repo_path,
                timeout=30,
            )
            return result.stdout.strip().split("\n")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def refactor_frequency(self) -> dict:
        """Which modules get refactored most? (proxy: rename/move operations)"""
        try:
            result = subprocess.run(
                ["git", "log", "--diff-filter=R", "--name-status", "--format="],
                capture_output=True, text=True, cwd=self.repo_path,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {}

        renames: Dict[str, int] = defaultdict(int)
        for line in result.stdout.strip().split("\n"):
            if line.startswith("R"):
                parts = line.split("\t")
                if len(parts) >= 3:
                    module = self._file_to_module(parts[2])
                    if module:
                        renames[module] += 1
        return dict(renames)

    def _file_to_module(self, filepath: str) -> Optional[str]:
        """Map a file path to its top-level module."""
        parts = filepath.replace("\\", "/").split("/")
        known_modules = (
            "core", "cog", "bridges", "categorical", "oracle",
            "domains", "topology", "geometry", "hott", "zfc",
            "cubical", "game", "data", "aimo", "orion_komposos_cog",
            "tests", "tools",
        )
        if len(parts) >= 2 and parts[0] in known_modules:
            return parts[0]
        if filepath.endswith(".py") and "/" not in filepath and "\\" not in filepath:
            return filepath.replace(".py", "")
        return None


class ArchitecturalAdvisor:
    """
    The self-correction loop from the Ruliad essay, enhanced with ∞-cosmos.

    observe -> identify wrong boundaries -> propose -> validate -> repeat

    Uses OPTIMUS for 1-morphism analysis and InfinityCosmos for 2-cell analysis.
    """

    def __init__(
        self,
        orion_core=None,
        telemetry_category: "Category" = None,
        repo_path: str = ".",
        category_factory=None,
        auto_correct: bool = False,
        approval_mode: str = "log",
    ):
        """
        Args:
            orion_core: Orion Core instance.
            telemetry_category: Category with telemetry data.
            repo_path: Path to git repository.
            category_factory: Callable that returns a fresh Category.
            auto_correct: If True, automatically act on recommendations.
            approval_mode: How to handle self-correction actions:
                - "log": Only log (safest)
                - "ask": Emit events for human approval
                - "auto": Automatically execute safe actions
        """
        self.orion = orion_core
        self.telemetry = telemetry_category
        self.git = GitArchitectureAnalyzer(repo_path)
        self.auto_correct = auto_correct
        self.approval_mode = approval_mode

        if category_factory:
            self.category_factory = category_factory
        else:
            from .category import Category
            self.category_factory = lambda: Category(db_path=":memory:")

        # Self-corrector for automatic action on findings
        self._self_corrector = None
        if auto_correct:
            from .self_corrector import SelfCorrector
            self._self_corrector = SelfCorrector(
                orion_core=orion_core,
                approval_mode=approval_mode,
            )

    async def analyze(self) -> Dict[str, Any]:
        """Run one cycle of architectural self-observation."""
        # 1. Build capability graph from all signal sources
        from .capability_graph import CapabilityGraphBuilder
        from .cosmos import InfinityCosmos

        builder = CapabilityGraphBuilder(
            self.orion, self.telemetry, self.category_factory
        )
        cap_graph = await builder.build()
        builder.add_git_signals(self.git.co_modification_matrix())

        # 2. Run OPTIMUS on the capability graph (1-morphism level)
        from .optimus import OptimusEngine
        engine = OptimusEngine(cap_graph, max_depth=3)

        # Structural holes = missing capabilities
        gaps = engine.find_structural_gaps()

        # Factorization = redundant capabilities
        refinement = engine.refine(max_steps=20, depth=2)

        # Yoneda = capabilities that should share an interface
        duplicates = []
        objects = list(cap_graph.objects())
        for i, a in enumerate(objects):
            for b in objects[i + 1:]:
                sim = engine.yoneda_similarity(a.name, b.name)
                if sim > 0.8:
                    duplicates.append({
                        "a": a.name, "b": b.name,
                        "similarity": sim,
                        "recommendation": f"{a.name} and {b.name} may be the same primitive"
                    })

        # 3. Run InfinityCosmos analysis (2-cell level)
        cosmos = InfinityCosmos(cap_graph, name="capability-cosmos")
        h2k = cosmos.homotopy_2_category()

        # 2-cell analysis: find capabilities with equivalent behavior
        two_cell_equivs = self._analyze_two_cells(cosmos, h2k)

        # Fibration analysis: find type-level patterns
        fibrations = cosmos.cartesian_fibrations()

        # 4. DUAL ENGINE VERIFICATION: ZFC + CAT verification of recommendations
        # This is the system observing its own reasoning
        dual_results, system3_insights = self._verify_with_dual_engine(
            cap_graph, gaps, duplicates, coupled
        )

        # Git coupling: capabilities that always change together
        comod = self.git.co_modification_matrix()
        coupled = [
            {"a": a, "b": b, "commits": count,
             "recommendation": f"{a} and {b} always change together -- missing shared primitive?"}
            for (a, b), count in sorted(comod.items(), key=lambda x: -x[1])[:10]
            if count > 5
        ]

        # Linear independence test
        from .independence import LinearIndependenceTest
        indep = LinearIndependenceTest(cap_graph)
        basis = indep.basis_analysis()

        return {
            "structural_gaps": gaps[:20],
            "factorization_improvements": refinement,
            "yoneda_duplicates": duplicates,
            "two_cell_equivalences": two_cell_equivs,
            "fibrations": {
                name: {
                    "objects": fib.total_objects,
                    "cartesian_lifts": fib.cartesian_lifts,
                }
                for name, fib in fibrations.items()
            },
            "git_coupling": coupled,
            "basis_analysis": basis,
            "dual_engine_verification": dual_results,
            "system3_insights": system3_insights,
            "recommendations": self._synthesize(
                gaps, duplicates, coupled, two_cell_equivs, fibrations, dual_results
            ),
            "statistics": {
                "capability_graph": builder.summary(),
                "cosmos": cosmos.statistics(),
                "git": {
                    "refactor_frequency": self.git.refactor_frequency(),
                    "abandoned_experiments": len(self.git.abandoned_experiments()),
                },
                "dual_engine": {
                    "episodes_recorded": len(system3_insights.get("episodes", [])),
                    "delta_distribution": system3_insights.get("delta_distribution", {}),
                }
            },
            "self_correction": await self._run_self_correction(
                gaps, duplicates, coupled, two_cell_equivs, fibrations, dual_results
            ) if self._self_corrector else None,
        }

    def _verify_with_dual_engine(
        self, cap_graph, gaps, duplicates, coupled
    ) -> tuple:
        """
        Verify recommendations using the ZFC/CAT dual engine with System 3.

        This is the system observing its own reasoning:
        - ZFC checks: Is this recommendation logically entailed?
        - CAT checks: Is this compositionally valid?
        - System 3 learns from disagreements to predict future ones.

        Returns:
            Tuple of (dual_results, system3_insights).
        """
        dual_results = []
        episodes_recorded = []

        try:
            from zfc.store_adapter import StoreAdapter
            # Use EvolvedDualEngineBridge for axiom-evolving verification
            from zfc.evolved_bridge import EvolvedDualEngineBridge

            # Build the evolved dual engine from the capability graph
            adapter = StoreAdapter(cap_graph)

            # Get System 3 oracle if available (from bridge's internal system3)
            # EvolvedDualEngineBridge will auto-mine axioms from any existing episodes
            bridge = EvolvedDualEngineBridge(
                category=cap_graph,
                auto_mine=True,
                min_support=3,  # Low threshold for architectural recommendations
            )

            # Verify each gap through the evolved dual engine
            for gap in gaps[:10]:  # Top 10 gaps
                source = gap.get("source", "")
                target = gap.get("target", "")
                relation = gap.get("via", "requires")

                if source and target:
                    result = bridge.query(
                        source, target, relation,
                        domain="architectural_recommendation",
                        record=True,
                    )
                    dual_results.append({
                        "source": source,
                        "target": target,
                        "relation": relation,
                        "delta_type": result.delta_type.name,
                        "zfc_says": result.zfc_says,
                        "zfc_confidence": result.zfc_confidence,
                        "cat_says": result.cat_says,
                        "cat_confidence": result.cat_confidence,
                        "meta_prediction": (
                            result.meta_prediction.predicted_delta.name
                            if result.meta_prediction else None
                        ),
                        "evolved_axioms": (
                            result.evidence.get("evolved_axioms", {})
                            if result.evidence else {}
                        ),
                    })
                    episodes_recorded.append({
                        "source": source,
                        "target": target,
                        "delta_type": result.delta_type.name,
                    })

        except Exception as e:
            # Dual engine not fully available — record the issue
            dual_results.append({
                "error": str(e),
                "note": "Dual engine verification skipped (dependencies not available)",
            })

        # System 3 insights
        system3_insights = {
            "episodes": episodes_recorded,
            "delta_distribution": {},
        }

        # Compute delta distribution from recorded episodes
        delta_counts = {}
        for ep in episodes_recorded:
            delta = ep.get("delta_type", "UNKNOWN")
            delta_counts[delta] = delta_counts.get(delta, 0) + 1
        system3_insights["delta_distribution"] = delta_counts

        return dual_results, system3_insights

    async def _run_self_correction(
        self, gaps, duplicates, coupled, two_cell_equivs, fibrations, dual_results
    ) -> Dict[str, Any]:
        """
        Run self-correction on analysis findings.

        This is the system acting on what it observes.
        """
        if not self._self_corrector:
            return {"status": "disabled"}

        # Build recommendations from all analysis sources
        recommendations = self._synthesize(
            gaps, duplicates, coupled, two_cell_equivs, fibrations, dual_results
        )

        # Act on recommendations
        result = await self._self_corrector.act_on_recommendations(
            recommendations,
            auto_execute=self.auto_correct,
        )

        return result

    def _analyze_two_cells(self, cosmos, h2k) -> List[Dict[str, Any]]:
        """Analyze 2-cells for capability equivalence."""
        equivalences = []

        # Find 2-cells with high confidence similarity
        for cell_name, cell in h2k.two_cells.items():
            similarity = cell.data.get("confidence_similarity", 0)
            if similarity > 0.7:
                equivalences.append({
                    "two_cell": cell_name,
                    "source": cell.source_morphism,
                    "target": cell.target_morphism,
                    "similarity": similarity,
                    "recommendation": (
                        f"{cell.source_morphism} and {cell.target_morphism} "
                        f"are 2-cell equivalent (similarity={similarity:.2f}). "
                        f"Consider merging or sharing interface."
                    ),
                })

        return sorted(equivalences, key=lambda e: -e["similarity"])

    def _synthesize(
        self, gaps, duplicates, coupled, two_cell_equivs, fibrations, dual_results=None
    ) -> List[Dict[str, Any]]:
        """Turn raw signals into actionable recommendations."""
        dual_results = dual_results or []
        recs = []

        for gap in gaps[:5]:
            recs.append({
                "type": "missing_primitive",
                "description": (
                    f"No direct {gap['source']}->{gap['target']} capability. "
                    f"Currently requires going through {gap['via']}. "
                    f"Consider adding a direct capability."
                ),
                "confidence": gap["path_confidence"],
            })

        for dup in duplicates:
            recs.append({
                "type": "redundant_capability",
                "description": (
                    f"{dup['a']} and {dup['b']} are structurally equivalent "
                    f"(Yoneda similarity {dup['similarity']:.2f}). "
                    f"Consider merging or sharing an interface."
                ),
                "confidence": dup["similarity"],
            })

        for equiv in two_cell_equivs[:5]:
            recs.append({
                "type": "two_cell_equivalence",
                "description": equiv["recommendation"],
                "confidence": equiv["similarity"],
            })

        for coup in coupled:
            recs.append({
                "type": "wrong_boundary",
                "description": (
                    f"{coup['a']} and {coup['b']} are modified together in "
                    f"{coup['commits']} commits. A shared primitive may be missing."
                ),
                "confidence": min(coup["commits"] / 20, 1.0),
            })

        for fib_name, fib in fibrations.items():
            if fib["cartesian_lifts"]:
                recs.append({
                    "type": "fibration_pattern",
                    "description": (
                        f"Fibration '{fib_name}' has {len(fib['cartesian_lifts'])} "
                        f"cartesian lifts across {len(fib['objects'])} objects. "
                        f"This is a recurring pattern that could be abstracted."
                    ),
                    "confidence": 0.7,
                })

        # Dual engine insights: recommendations verified through ZFC+CAT
        for dr in dual_results:
            if "error" in dr:
                continue  # Skip errors

            delta = dr.get("delta_type", "UNKNOWN")
            if delta == "ORPHAN":
                # ZFC says yes, CAT says no — logically forced but geometrically unsound
                recs.append({
                    "type": "dual_engine_orphan",
                    "description": (
                        f"{dr['source']}->{dr['target']} is logically entailed "
                        f"(ZFC conf={dr['zfc_confidence']:.2f}) but structurally "
                        f"unsupported (CAT conf={dr['cat_confidence']:.2f}). "
                        f"System 3 predicts: {dr.get('meta_prediction', 'unknown')}. "
                        f"This suggests a missing structural bridge."
                    ),
                    "confidence": dr.get("zfc_confidence", 0.5),
                })
            elif delta == "HOLLOW":
                # CAT says yes, ZFC says no — compositionally valid but logically baseless
                recs.append({
                    "type": "dual_engine_hollow",
                    "description": (
                        f"{dr['source']}->{dr['target']} is compositionally valid "
                        f"(CAT conf={dr['cat_confidence']:.2f}) but not logically "
                        f"entailed (ZFC conf={dr['zfc_confidence']:.2f}). "
                        f"This is a novel discovery — geometrically real, logically baseless. "
                        f"System 3 predicts: {dr.get('meta_prediction', 'unknown')}."
                    ),
                    "confidence": dr.get("cat_confidence", 0.5),
                })
            elif delta == "AGREE":
                # Both agree — high confidence recommendation
                recs.append({
                    "type": "dual_engine_agree",
                    "description": (
                        f"{dr['source']}->{dr['target']} is verified by both "
                        f"ZFC (conf={dr['zfc_confidence']:.2f}) and "
                        f"CAT (conf={dr['cat_confidence']:.2f}). "
                        f"High confidence recommendation."
                    ),
                    "confidence": max(dr.get("zfc_confidence", 0), dr.get("cat_confidence", 0)),
                })

        return sorted(recs, key=lambda r: -r["confidence"])
