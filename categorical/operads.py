# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Operads: N-ary Composition

Operads generalize categories from binary composition (f after g) to n-ary
composition (plug n things into n slots). An operad O has:
  - Operations O(n) for each arity n >= 0
  - Partial composition: circ_i inserts one operation into slot i of another
  - Identity: the 1-ary identity operation

Key axioms (0-indexed, as implemented):
  1. Sequential associativity:
     f circ_i (g circ_j h) = (f circ_i g) circ_{i+j} h
     (inserting into a slot that came from g)
  2. Parallel associativity:
     (f circ_i g) circ_{j+n-1} h = (f circ_j h) circ_i g   for i < j
     (inserting into two different slots of f; n = arity of g)
  3. Identity: id circ_0 f = f = f circ_i id for all slots i
  4. Equivariance: permuting inputs commutes with composition (symmetric operads)

  The 1-indexed versions (Loday & Vallette):
    Sequential: (f circ_i g) circ_{i+j-1} h = f circ_i (g circ_j h)
    Parallel:   (f circ_i g) circ_{j+n-1} h = (f circ_j h) circ_i g   for i < j

Categories are operads where every operation has arity 1.
The jump from 1-ary to n-ary lets us model:
  - Multi-input functions (not just chains)
  - Tree-shaped compositions (not just linear)
  - Parallel structure (multiple inputs processed simultaneously)

Mathematical basis:
  - May, "The Geometry of Iterated Loop Spaces" (1972) — original definition
  - Loday & Vallette, "Algebraic Operads" (2012) — modern reference
  - Leinster, "Higher Operads, Higher Categories" (2004)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict


@dataclass
class Operation:
    """
    An n-ary operation in an operad.

    An operation with arity n takes n inputs and produces one output.
    The types track what each slot accepts and what the operation produces.
    """
    name: str
    arity: int                     # number of inputs (n >= 0)
    output_type: str               # what this operation produces
    input_types: List[str]         # what each slot accepts (length = arity)
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.input_types) != self.arity:
            raise ValueError(
                f"Operation {self.name}: arity {self.arity} but "
                f"{len(self.input_types)} input types given"
            )

    def __hash__(self):
        return hash((self.name, self.arity))

    def __eq__(self, other):
        if isinstance(other, Operation):
            return self.name == other.name and self.arity == other.arity
        return False

    def __repr__(self):
        inputs = ", ".join(self.input_types)
        return f"{self.name}({inputs}) -> {self.output_type}"


@dataclass
class OperadicComposition:
    """
    Result of composing operations via partial composition circ_i.

    Records: outer operation, which inner operations were plugged in,
    at which positions, and the resulting composed operation.
    """
    outer: str              # outer operation name
    inner: List[str]        # inner operation names (one per filled slot)
    positions: List[int]    # which slot each inner was plugged into
    result: Operation       # the composed operation


class Operad:
    """
    An operad: operations with arities and partial composition.

    This is the n-ary generalization of a category. Where a category
    has Hom(A, B) with binary composition, an operad has O(n) with
    tree-shaped composition.
    """

    def __init__(self, name: str):
        self.name = name
        self.operations: Dict[str, Operation] = {}
        self.compositions: List[OperadicComposition] = []
        self._by_arity: Dict[int, List[str]] = defaultdict(list)

    def add_operation(self, op: Operation) -> None:
        """Add an operation to the operad."""
        self.operations[op.name] = op
        self._by_arity[op.arity].append(op.name)

    def get_by_arity(self, n: int) -> List[Operation]:
        """Get all operations of arity n."""
        return [self.operations[name] for name in self._by_arity.get(n, [])]

    def identity_operation(self, type_name: str) -> Operation:
        """
        The 1-ary identity operation for a type.

        id_X : X -> X, the operation that does nothing.
        This is the operadic unit: id circ_1 f = f = f circ_i id.
        """
        id_name = f"id_{type_name}"
        if id_name not in self.operations:
            op = Operation(
                name=id_name,
                arity=1,
                output_type=type_name,
                input_types=[type_name],
                data={"is_identity": True}
            )
            self.add_operation(op)
        return self.operations[id_name]

    def compose(self, outer_name: str, inners: Dict[int, str]) -> Operation:
        """
        Partial composition: plug inner operations into slots of outer.

        Given outer f with arity n and inner g_i at slot i:
          (f circ_i g)(x_1, ..., x_{arity(g)}, ...) =
            f(x_1, ..., g(x_{slot_start}, ..., x_{slot_end}), ...)

        The result arity = outer.arity - |filled_slots| + sum(inner arities).
        Each filled slot is replaced by all the inputs of the inner operation.

        Args:
            outer_name: Name of the outer operation
            inners: Dict mapping slot_index -> inner operation name

        Returns:
            The composed operation
        """
        if outer_name not in self.operations:
            raise ValueError(f"Unknown operation: {outer_name}")

        outer = self.operations[outer_name]

        for slot, inner_name in inners.items():
            if inner_name not in self.operations:
                raise ValueError(f"Unknown operation: {inner_name}")
            if slot < 0 or slot >= outer.arity:
                raise ValueError(
                    f"Slot {slot} out of range for {outer_name} "
                    f"(arity {outer.arity})"
                )

        # Handle identity shortcut
        if outer.data.get("is_identity") and 0 in inners:
            return self.operations[inners[0]]

        all_identity = all(
            self.operations[n].data.get("is_identity")
            for n in inners.values()
        )
        if all_identity and len(inners) == outer.arity:
            return outer

        # Build the composed operation
        # Process slots left-to-right, replacing filled slots with inner inputs
        new_input_types = []
        for i in range(outer.arity):
            if i in inners:
                inner = self.operations[inners[i]]
                # Type check: inner output must match slot type
                if inner.output_type != outer.input_types[i]:
                    raise TypeError(
                        f"Type mismatch at slot {i}: "
                        f"{outer.input_types[i]} expected, "
                        f"{inner.output_type} produced by {inner.name}"
                    )
                new_input_types.extend(inner.input_types)
            else:
                new_input_types.append(outer.input_types[i])

        # Build name
        parts = []
        for slot in sorted(inners.keys()):
            parts.append(f"{inners[slot]}@{slot}")
        composed_name = f"{outer_name}[{', '.join(parts)}]"

        result = Operation(
            name=composed_name,
            arity=len(new_input_types),
            output_type=outer.output_type,
            input_types=new_input_types,
            data={
                "composed_from": outer_name,
                "inners": dict(inners),
                "is_identity": False,
            }
        )

        self.add_operation(result)

        composition = OperadicComposition(
            outer=outer_name,
            inner=[inners[s] for s in sorted(inners.keys())],
            positions=sorted(inners.keys()),
            result=result,
        )
        self.compositions.append(composition)

        return result

    def compose_all(self, outer_name: str, inners: List[str]) -> Operation:
        """
        Compose all slots at once.

        Convenience: inners[i] goes into slot i.
        inners must have length = outer.arity.
        """
        if outer_name not in self.operations:
            raise ValueError(f"Unknown operation: {outer_name}")

        outer = self.operations[outer_name]
        if len(inners) != outer.arity:
            raise ValueError(
                f"{outer_name} has arity {outer.arity} but "
                f"{len(inners)} inners given"
            )

        slot_map = {i: name for i, name in enumerate(inners)}
        return self.compose(outer_name, slot_map)

    def find_decompositions(self, op_name: str,
                            max_depth: int = 3) -> List[OperadicComposition]:
        """
        Find ways to decompose an operation into smaller ones.

        Searches for existing compositions that produce an operation
        with the same type signature as the target.
        """
        if op_name not in self.operations:
            return []

        target = self.operations[op_name]
        results = []

        # Look through all possible outers
        for outer in self.operations.values():
            if outer.name == op_name:
                continue
            if outer.output_type != target.output_type:
                continue
            if outer.arity == 0:
                continue

            # Try to find inners that fill all slots and match target inputs
            self._search_decomposition(
                target, outer, {}, 0, results, max_depth
            )

        return results

    def _search_decomposition(
        self,
        target: Operation,
        outer: Operation,
        filled: Dict[int, str],
        current_slot: int,
        results: List[OperadicComposition],
        depth: int,
    ):
        """Recursive search for valid decompositions."""
        if depth <= 0:
            return

        if current_slot == outer.arity:
            # All slots filled — check if result matches target signature
            try:
                result = self.compose(outer.name, filled)
                if (result.arity == target.arity and
                        result.input_types == target.input_types and
                        result.output_type == target.output_type):
                    results.append(OperadicComposition(
                        outer=outer.name,
                        inner=[filled[s] for s in range(outer.arity)],
                        positions=list(range(outer.arity)),
                        result=result,
                    ))
            except (TypeError, ValueError):
                pass
            return

        slot_type = outer.input_types[current_slot]
        # Try each operation that outputs the right type
        for candidate in self.operations.values():
            if candidate.output_type == slot_type:
                filled[current_slot] = candidate.name
                self._search_decomposition(
                    target, outer, filled, current_slot + 1,
                    results, depth - 1,
                )
        # Also try leaving this slot unfilled (partial composition)
        # but only if we're looking for partial decompositions
        if current_slot in filled:
            del filled[current_slot]

    def check_associativity(self, outer_name: str, mid_name: str,
                            inner_name: str,
                            slot_outer: int, slot_mid: int) -> bool:
        """
        Verify the sequential associativity axiom (0-indexed):

          f circ_i (g circ_j h) = (f circ_i g) circ_{i+j} h

        This is the key operadic axiom: composing inside-out or
        outside-in gives the same result when h goes into a slot of g.

        1-indexed equivalent: (f circ_i g) circ_{i+j-1} h = f circ_i (g circ_j h)

        Args:
            outer_name: f (the outermost operation)
            mid_name: g (the middle operation)
            inner_name: h (the innermost operation)
            slot_outer: i (0-indexed slot in f where g goes)
            slot_mid: j (0-indexed slot in g where h goes)

        Returns:
            True if the axiom holds (both orders give same result)
        """
        try:
            # Left: f circ_i (g circ_j h)
            mid_composed = self.compose(mid_name, {slot_mid: inner_name})
            left = self.compose(outer_name, {slot_outer: mid_composed.name})

            # Right: (f circ_i g) circ_{i+j} h
            # When g is inserted at slot i of f, g's slot j becomes
            # slot i + j in the composed operation (0-indexed)
            outer_mid = self.compose(outer_name, {slot_outer: mid_name})
            adjusted_slot = slot_outer + slot_mid
            right = self.compose(outer_mid.name, {adjusted_slot: inner_name})

            # Compare type signatures
            return (left.arity == right.arity and
                    left.input_types == right.input_types and
                    left.output_type == right.output_type)
        except (ValueError, TypeError):
            return False

    def check_parallel_associativity(self, f_name: str,
                                     g_name: str, h_name: str,
                                     slot_i: int, slot_j: int) -> bool:
        """
        Verify the parallel associativity axiom (0-indexed):

          (f circ_i g) circ_{j+n-1} h = (f circ_j h) circ_i g

        where n = arity(g), and i < j (two different slots of f).

        This says: inserting g at slot i and h at slot j of f
        gives the same result regardless of order. The index shift
        j+n-1 accounts for g expanding slot i into n slots.

        Args:
            f_name: f (the outer operation, arity >= 2)
            g_name: g (goes into slot i)
            h_name: h (goes into slot j)
            slot_i: i (0-indexed, must be < slot_j)
            slot_j: j (0-indexed, must be > slot_i)

        Returns:
            True if the axiom holds
        """
        if slot_i >= slot_j:
            raise ValueError(f"Parallel requires slot_i < slot_j, got {slot_i} >= {slot_j}")

        try:
            g = self.operations[g_name]
            n = g.arity

            # Left: (f circ_i g) circ_{j+n-1} h
            fg = self.compose(f_name, {slot_i: g_name})
            left = self.compose(fg.name, {slot_j + n - 1: h_name})

            # Right: (f circ_j h) circ_i g
            fh = self.compose(f_name, {slot_j: h_name})
            right = self.compose(fh.name, {slot_i: g_name})

            return (left.arity == right.arity and
                    left.input_types == right.input_types and
                    left.output_type == right.output_type)
        except (ValueError, TypeError):
            return False

    def __repr__(self):
        return (f"Operad({self.name}, "
                f"|ops|={len(self.operations)}, "
                f"|compositions|={len(self.compositions)})")


class OperadMorphism:
    """
    A morphism between operads (preserves arities and composition).

    An operad morphism F: O -> P maps:
    - Operations: F(f) in P for each f in O
    - Preserves arities: arity(F(f)) = arity(f)
    - Preserves composition: F(f circ_i g) = F(f) circ_i F(g)
    - Preserves identity: F(id) = id
    """

    def __init__(self, source: Operad, target: Operad,
                 operation_map: Dict[str, str]):
        """
        Args:
            source: Source operad O
            target: Target operad P
            operation_map: Maps operation names in O to operation names in P
        """
        self.source = source
        self.target = target
        self.operation_map = dict(operation_map)

    def is_valid(self) -> bool:
        """
        Check if this is a valid operad morphism.

        Verifies:
        1. All source operations are mapped
        2. Arities are preserved
        3. Output types are preserved
        """
        for op_name, op in self.source.operations.items():
            if op_name not in self.operation_map:
                return False

            target_name = self.operation_map[op_name]
            if target_name not in self.target.operations:
                return False

            target_op = self.target.operations[target_name]
            if target_op.arity != op.arity:
                return False

        return True

    def apply(self, op_name: str) -> Optional[Operation]:
        """Map an operation from source to target."""
        if op_name not in self.operation_map:
            return None
        target_name = self.operation_map[op_name]
        return self.target.operations.get(target_name)

    def __repr__(self):
        return f"OperadMorphism({self.source.name} -> {self.target.name})"


# =============================================================================
# Colored Operads (typed operads)
# =============================================================================

class ColoredOperad(Operad):
    """
    A colored (typed/multi-sorted) operad.

    In a colored operad, the "colors" are types and operations
    have typed inputs and outputs. This is already captured by
    Operation.input_types and output_type, but ColoredOperad
    additionally tracks the set of colors and enforces type
    discipline more strictly.
    """

    def __init__(self, name: str, colors: Optional[Set[str]] = None):
        super().__init__(name)
        self.colors: Set[str] = colors or set()

    def add_color(self, color: str) -> None:
        """Register a new color (type)."""
        self.colors.add(color)

    def add_operation(self, op: Operation) -> None:
        """Add an operation, registering any new colors."""
        self.colors.add(op.output_type)
        for t in op.input_types:
            self.colors.add(t)
        super().add_operation(op)

    def operations_by_profile(self, input_types: List[str],
                              output_type: str) -> List[Operation]:
        """Find all operations with a given type profile."""
        results = []
        for op in self.operations.values():
            if (op.input_types == input_types and
                    op.output_type == output_type):
                results.append(op)
        return results

    def __repr__(self):
        return (f"ColoredOperad({self.name}, "
                f"|colors|={len(self.colors)}, "
                f"|ops|={len(self.operations)})")


# =============================================================================
# Bridge: Category -> Operad
# =============================================================================

def operad_from_category(cat) -> Operad:
    """
    Build an operad from a Category.

    Every category is an operad where all operations have arity 1.
    Morphisms f: A -> B become 1-ary operations with input_type=[A]
    and output_type=B.

    This is the canonical embedding Cat -> Operad.
    """
    from .category import Category

    operad = Operad(f"Operad({cat.name})")

    # Support both KOMPOSOS-IV Category (morphisms() method)
    # and legacy Category (morphisms dict)
    if hasattr(cat, 'morphisms') and callable(cat.morphisms):
        morphisms = cat.morphisms()
    else:
        morphisms = cat.morphisms.values()

    for mor in morphisms:
        # Support both legacy .data and KOMPOSOS-IV .metadata
        mor_data = getattr(mor, 'data', getattr(mor, 'metadata', {}))
        # Support both object and string source/target
        src_name = mor.source.name if hasattr(mor.source, 'name') else mor.source
        tgt_name = mor.target.name if hasattr(mor.target, 'name') else mor.target
        if mor_data and mor_data.get("is_identity"):
            operad.identity_operation(src_name)
        else:
            op = Operation(
                name=mor.name,
                arity=1,
                output_type=tgt_name,
                input_types=[src_name],
                data=dict(mor_data) if isinstance(mor_data, dict) else {},
            )
            operad.add_operation(op)

    return operad
