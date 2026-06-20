# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Proof Bridge -- Connects ProofGraph to the Dual-Engine System.

Loads a proof graph (propositions and proof steps) into the
Category so both CAT and ZFC engines can verify it.

Integration points:
    ProofNode  (proposition)  ->  Object
    ProofEdge  (proof step)   ->  Morphism
    DualEngineBridge          validates relationships
    System 3                  learns which proof patterns resolve

Architecture:

    ProofGraph
         | load_proof_graph
    Category
         |
     StoreAdapter
      /        \
    CAT        ZFC
  (System 2)  (System 1)
      \        /
    DualEngineBridge
         |
      System 3
     (Meta Kan)

Usage:
    from proof.conjecture_engine import build_riemann_hypothesis_graph
    from zfc.proof_bridge import ProofGraphBridge

    graph = build_riemann_hypothesis_graph()
    pb = ProofGraphBridge(graph, domain="riemann_hypothesis")

    # Validate all existing proof steps
    results = pb.validate_all()

    # Discover and validate conjectures
    conjectures = pb.discover_and_validate(top_k=10)

    # See proof health
    print(pb.health_report())

Duck-typed: works with any graph object that has .nodes (iterable)
and .edges (iterable). Nodes need .statement, .status.value,
.confidence, .metadata. Edges need .source, .target, .proof_method,
.justification, .confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.category import Category
from core.types import Object, Morphism

from .store_adapter import StoreAdapter
from .bridge import DualEngineBridge, DualResult
from .meta_kan import DeltaType, Resolution
from .proof_engine import Proof, ProofStep, StepMethod, ZFCVerifier
from .logic import atom, const, Model
from .universe import Universe, zfset, relation as mk_relation


# ================================================================
# Load function
# ================================================================

def load_proof_graph(graph: Any, category: Category) -> None:
    """
    Load a ProofGraph into a Category.

    Each node (proposition) becomes an Object (type="Proposition").
    Each edge (proof step) becomes a Morphism (name=proof_method).

    Duck-typed: accepts any object with .nodes and .edges matching
    the ProofGraph interface.
    """
    objects = []
    for node in graph.nodes:
        status_val = "pending"
        if hasattr(node, 'status') and node.status is not None:
            status_val = getattr(node.status, 'value', str(node.status))

        metadata = {}
        if hasattr(node, 'metadata') and node.metadata:
            metadata = dict(node.metadata)
        metadata["status"] = status_val
        metadata["confidence"] = getattr(node, 'confidence', 0.0)

        objects.append(Object(
            name=node.statement,
            type_name="Proposition",
            metadata=metadata,
        ))

    morphisms = []
    for edge in graph.edges:
        morphisms.append(Morphism(
            name=edge.proof_method,
            source=edge.source.statement,
            target=edge.target.statement,
            metadata={
                "justification": getattr(edge, 'justification', ''),
            },
            confidence=getattr(edge, 'confidence', 0.0),
        ))

    if objects or morphisms:
        category.bulk_add(objects, morphisms)


# ================================================================
# ConjectureResult
# ================================================================

@dataclass
class ConjectureResult:
    """Result of validating a proof conjecture through the dual engine."""
    source: str
    target: str
    reason: str
    suggested_method: str
    confidence: float
    dual_result: DualResult
    generators: List[str] = field(default_factory=list)

    @property
    def delta_type(self) -> DeltaType:
        return self.dual_result.delta_type


# ================================================================
# ProofVerificationResult
# ================================================================

@dataclass
class ProofVerificationResult:
    """Result of verifying a single proof step through ZFC + CAT."""
    step_name: str
    method: StepMethod
    zfc_ok: bool
    zfc_reason: str
    cat_ok: bool
    cat_reason: str
    confidence: float
    delta: str  # "VALID" / "HOLLOW" / "ORPHAN" / "REJECT"


# ================================================================
# ProofGraphBridge
# ================================================================

class ProofGraphBridge:
    """
    Connects a ProofGraph to the DualEngineBridge.

    Loads the graph into a category, builds both engines, and provides
    methods to validate edges, conjectures, and generate reports.

    For existing edges (already in the graph):
        Both engines see the data -> expect AGREE for all loaded edges.
        Disagreement signals a structural problem.

    For conjectures (not yet in the graph):
        AGREE  = both engines derive it (strong conjecture)
        ORPHAN = ZFC derives but no CAT path (true but unconnected)
        HOLLOW = CAT path exists but no ZFC axiom (structural only)
        REJECT = neither engine supports it (weak conjecture)
    """

    def __init__(
        self,
        graph: Any,
        domain: str = "mathematics",
        category: Optional[Category] = None,
    ):
        self.graph = graph
        self.domain = domain
        self.category = category or Category(db_path=":memory:")

        # Load graph into category
        load_proof_graph(graph, self.category)

        # Build engines
        self.adapter = StoreAdapter(self.category)
        self.bridge = DualEngineBridge(self.adapter)

        # Track results
        self._edge_results: List[DualResult] = []
        self._conjecture_results: List[ConjectureResult] = []
        self._verification_results: List[ProofVerificationResult] = []

    # ----------------------------------------------------------------
    # Edge validation
    # ----------------------------------------------------------------

    def validate_edge(self, edge: Any) -> DualResult:
        """
        Validate a single proof edge through both engines.

        For edges loaded from the graph, both engines should agree
        (the data is in both the theory and the category).
        """
        result = self.bridge.query(
            source=edge.source.statement,
            target=edge.target.statement,
            relation=edge.proof_method,
            domain=self.domain,
        )
        self._edge_results.append(result)
        return result

    def validate_all(self) -> List[DualResult]:
        """Validate every edge in the proof graph."""
        self._edge_results.clear()
        for edge in self.graph.edges:
            self.validate_edge(edge)
        return list(self._edge_results)

    # ----------------------------------------------------------------
    # Conjecture validation
    # ----------------------------------------------------------------

    def validate_conjecture(self, conjecture: Any) -> ConjectureResult:
        """
        Validate a proof conjecture through both engines.

        The conjecture's source->target may not exist as a direct
        edge. The engines check if it's derivable:
        - ZFC: is there logical entailment?
        - CAT: is there a composable path?
        """
        dual = self.bridge.query(
            source=conjecture.source.statement,
            target=conjecture.target.statement,
            relation=getattr(conjecture, 'suggested_method', 'proof'),
            domain=self.domain,
        )

        cr = ConjectureResult(
            source=conjecture.source.statement,
            target=conjecture.target.statement,
            reason=getattr(conjecture, 'reason', ''),
            suggested_method=getattr(conjecture, 'suggested_method', 'proof'),
            confidence=getattr(conjecture, 'confidence', 0.5),
            dual_result=dual,
            generators=getattr(conjecture, 'generators', []),
        )
        self._conjecture_results.append(cr)
        return cr

    def validate_conjectures(
        self,
        conjectures: List[Any],
    ) -> List[ConjectureResult]:
        """Validate a list of conjectures."""
        return [self.validate_conjecture(c) for c in conjectures]

    def discover_and_validate(self, top_k: int = 20) -> List[ConjectureResult]:
        """
        Run the ProofConjectureEngine, then validate results.

        Imports ProofConjectureEngine lazily to avoid hard dependency.
        """
        from proof.conjecture_engine import ProofConjectureEngine
        engine = ProofConjectureEngine()
        conjectures = engine.discover_lemmas(self.graph, top_k=top_k)
        return self.validate_conjectures(conjectures)

    # ----------------------------------------------------------------
    # Proof verification (real ZFC + CAT)
    # ----------------------------------------------------------------

    def _build_proof_model(self) -> Tuple:
        """
        Build Universe + Model containing only proved (conf>=1) edges.

        The model is the "ground truth" for ZFC verification:
        - Relations for conf=1 edges exist -> formulas satisfied
        - Relations for conf=0 edges missing -> formulas fail
        """
        V = Universe("proof_universe")
        for node in self.graph.nodes:
            V.add_set(zfset(node.statement))

        rel_pairs: Dict[str, List] = {}
        for edge in self.graph.edges:
            if getattr(edge, 'confidence', 0) >= 1.0:
                method = edge.proof_method
                rel_pairs.setdefault(method, []).append(
                    (edge.source.statement, edge.target.statement)
                )

        for name, pairs in rel_pairs.items():
            V.add_relation(mk_relation(name, pairs))

        return V, Model(universe=V)

    def verify(self) -> List[ProofVerificationResult]:
        """
        Verify proof edges through the real Proof engine.

        Builds a ZFC Model from conf=1 edges only, then runs each
        edge through ZFCVerifier (model check) + CATVerifier (type check).

        Result:
            conf=1 edges -> formula in model -> ZFC yes + CAT yes -> VALID
            conf=0 edges -> formula NOT in model -> ZFC no + CAT yes -> HOLLOW
        """
        V, M = self._build_proof_model()
        proof = Proof(name=self.domain)
        proof.zfc = ZFCVerifier(universe=V, model=M)

        self._verification_results.clear()
        for i, edge in enumerate(self.graph.edges):
            src = edge.source.statement
            tgt = edge.target.statement
            formula = atom(edge.proof_method, const(src), const(tgt))

            ps = ProofStep(
                id=f"step_{i:03d}",
                name=f"{src} -> {tgt}",
                method=StepMethod.REPLACEMENT,
                inputs=[],
                input_types=[],
                output_type=tgt,
                formula=formula,
                justification=getattr(edge, 'justification', ''),
                confidence=getattr(edge, 'confidence', 0.0),
            )
            proof.add_step(ps)

            if ps.zfc_valid and ps.cat_valid:
                delta = "VALID"
            elif ps.cat_valid and not ps.zfc_valid:
                delta = "HOLLOW"
            elif ps.zfc_valid and not ps.cat_valid:
                delta = "ORPHAN"
            else:
                delta = "REJECT"

            self._verification_results.append(ProofVerificationResult(
                step_name=f"{src} -> {tgt}",
                method=StepMethod.REPLACEMENT,
                zfc_ok=ps.zfc_valid,
                zfc_reason=ps.zfc_reason,
                cat_ok=ps.cat_valid,
                cat_reason=ps.cat_reason,
                confidence=getattr(edge, 'confidence', 0.0),
                delta=delta,
            ))

        return list(self._verification_results)

    # ----------------------------------------------------------------
    # Resolution (System 3 feedback)
    # ----------------------------------------------------------------

    def resolve_edge(
        self,
        edge: Any,
        resolution: Resolution,
        notes: str = "",
    ) -> None:
        """
        Record ground truth for a specific edge's episode.

        Finds the matching episode in System 3 by source/target/relation
        and marks it with the given resolution.
        """
        for eid, ep in list(self.bridge.system3.history.episodes.items()):
            if (ep.source == edge.source.statement and
                ep.target == edge.target.statement and
                ep.relation == edge.proof_method):
                self.bridge.resolve(eid, resolution, notes)
                return

    # ----------------------------------------------------------------
    # Analysis
    # ----------------------------------------------------------------

    @property
    def edge_results(self) -> List[DualResult]:
        return list(self._edge_results)

    @property
    def conjecture_results(self) -> List[ConjectureResult]:
        return list(self._conjecture_results)

    @property
    def orphans(self) -> List[DualResult]:
        """Edge results where ZFC says yes but CAT says no."""
        return [r for r in self._edge_results
                if r.delta_type == DeltaType.ORPHAN]

    @property
    def hollows(self) -> List[DualResult]:
        """Edge results where CAT says yes but ZFC says no."""
        return [r for r in self._edge_results
                if r.delta_type == DeltaType.HOLLOW]

    @property
    def agrees(self) -> List[DualResult]:
        """Edge results where both engines agree."""
        return [r for r in self._edge_results
                if r.delta_type == DeltaType.AGREE]

    @property
    def rejects(self) -> List[DualResult]:
        """Edge results where both engines reject."""
        return [r for r in self._edge_results
                if r.delta_type == DeltaType.REJECT]

    @property
    def verification_results(self) -> List[ProofVerificationResult]:
        """Results from verify() -- real dual-engine verification."""
        return list(self._verification_results)

    def health_report(self) -> str:
        """Generate a proof health report."""
        lines = []
        lines.append("Proof Graph Health Report")
        lines.append(f"Domain: {self.domain}")
        lines.append(f"Nodes: {len(self.graph.nodes)}")
        lines.append(f"Edges: {len(self.graph.edges)}")
        lines.append("")

        if self._edge_results:
            n_agree = len(self.agrees)
            n_orphan = len(self.orphans)
            n_hollow = len(self.hollows)
            n_reject = len(self.rejects)
            total = len(self._edge_results)

            lines.append(f"Edge Validation ({total} edges):")
            lines.append(
                f"  AGREE:  {n_agree:3d}"
                f"  ({100*n_agree/total:.0f}%)"
            )
            lines.append(
                f"  ORPHAN: {n_orphan:3d}"
                f"  ({100*n_orphan/total:.0f}%)"
                f" -- sound but disconnected"
            )
            lines.append(
                f"  HOLLOW: {n_hollow:3d}"
                f"  ({100*n_hollow/total:.0f}%)"
                f" -- connected but unsound"
            )
            lines.append(
                f"  REJECT: {n_reject:3d}"
                f"  ({100*n_reject/total:.0f}%)"
            )
            lines.append("")

            if n_hollow > 0:
                lines.append(
                    "HOLLOW edges (types fit but logic fails):"
                )
                for r in self.hollows:
                    lines.append(
                        f"  {r.source} -> {r.target} [{r.relation}]"
                    )
                lines.append("")

            if n_orphan > 0:
                lines.append(
                    "ORPHAN edges (true but disconnected):"
                )
                for r in self.orphans:
                    lines.append(
                        f"  {r.source} -> {r.target} [{r.relation}]"
                    )
                lines.append("")

        if self._conjecture_results:
            lines.append(
                f"Conjecture Validation"
                f" ({len(self._conjecture_results)}):"
            )
            by_delta: Dict[str, List[ConjectureResult]] = {}
            for cr in self._conjecture_results:
                dt = cr.delta_type.name
                by_delta.setdefault(dt, []).append(cr)
            for dt, crs in sorted(by_delta.items()):
                lines.append(f"  {dt}: {len(crs)}")
                for cr in crs[:3]:
                    lines.append(f"    {cr.source} -> {cr.target}")
            lines.append("")

        if self._verification_results:
            n_valid = sum(1 for r in self._verification_results if r.delta == "VALID")
            n_hollow = sum(1 for r in self._verification_results if r.delta == "HOLLOW")
            n_orphan = sum(1 for r in self._verification_results if r.delta == "ORPHAN")
            n_reject = sum(1 for r in self._verification_results if r.delta == "REJECT")
            total = len(self._verification_results)

            lines.append(f"Proof Verification ({total} steps):")
            lines.append(f"  VALID:  {n_valid:3d}  ({100*n_valid/total:.0f}%) -- proved")
            lines.append(f"  HOLLOW: {n_hollow:3d}  ({100*n_hollow/total:.0f}%) -- unproved")
            lines.append(f"  ORPHAN: {n_orphan:3d}  ({100*n_orphan/total:.0f}%)")
            lines.append(f"  REJECT: {n_reject:3d}  ({100*n_reject/total:.0f}%)")
            lines.append("")

            if n_hollow > 0:
                lines.append("HOLLOW steps (types compose but logic unproved):")
                for r in self._verification_results:
                    if r.delta == "HOLLOW":
                        lines.append(f"  {r.step_name} -- {r.zfc_reason}")
                lines.append("")

        lines.append(self.bridge.system3_report())

        return "\n".join(lines)
