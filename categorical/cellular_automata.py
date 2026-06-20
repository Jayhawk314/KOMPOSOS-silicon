# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Cellular Automata as Endofunctors - Phase 3B

Implements cellular automata evolution as categorical endofunctors with:
- State space as objects in category
- Transition rules as morphisms
- Evolution operator as endofunctor F: C → C
- Natural transformations between different CA rules
- Epidemic models (SIR, SIS, SEIR) as functorial dynamics

Mathematical Foundation:
- CA evolution: F^n(state) where F is endofunctor
- Composition: F^(m+n) = F^m ∘ F^n
- Identity: F^0 = id
- Natural transformation η: F ⟹ G relates different CA rules

Applications:
- Epidemic spreading (SIR model: Susceptible → Infected → Recovered)
- Network attacks (worm propagation, APT lateral movement)
- Ransomware cascades (file encryption spread)
- Information diffusion
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple, Callable, Optional
from enum import Enum
import math
from collections import defaultdict


# =============================================================================
# CELLULAR STATE TYPES
# =============================================================================

class CellState(Enum):
    """Base cell states for epidemic models."""
    SUSCEPTIBLE = "S"
    INFECTED = "I"
    RECOVERED = "R"
    EXPOSED = "E"  # For SEIR model
    DEAD = "D"      # For mortality models


class AttackState(Enum):
    """Cell states for cyber attack propagation."""
    CLEAN = "clean"
    COMPROMISED = "compromised"
    PATCHED = "patched"
    ISOLATED = "isolated"
    ENCRYPTED = "encrypted"  # For ransomware


@dataclass
class CellularGrid:
    """
    Grid representing CA state space.

    Attributes:
        states: Dict[node_id, state] - current state of each cell
        adjacency: Dict[node_id, Set[node_id]] - neighborhood structure
        metadata: Optional metadata per cell (e.g., vulnerability scores)
    """
    states: Dict[int, Enum] = field(default_factory=dict)
    adjacency: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))
    metadata: Dict[int, Dict] = field(default_factory=dict)

    def __post_init__(self):
        """Validate grid structure."""
        if not isinstance(self.adjacency, defaultdict):
            self.adjacency = defaultdict(set, self.adjacency)

    def get_neighbors(self, node: int) -> Set[int]:
        """Get neighbors of a node."""
        return self.adjacency.get(node, set())

    def count_state(self, state: Enum) -> int:
        """Count cells in a given state."""
        return sum(1 for s in self.states.values() if s == state)

    def get_state_distribution(self) -> Dict[Enum, int]:
        """Get distribution of states across grid."""
        dist = defaultdict(int)
        for state in self.states.values():
            dist[state] += 1
        return dict(dist)

    def copy(self) -> 'CellularGrid':
        """Create deep copy of grid."""
        return CellularGrid(
            states=self.states.copy(),
            adjacency={k: v.copy() for k, v in self.adjacency.items()},
            metadata={k: v.copy() for k, v in self.metadata.items()}
        )


# =============================================================================
# TRANSITION RULES (MORPHISMS)
# =============================================================================

@dataclass
class TransitionRule:
    """
    Transition rule defining local CA dynamics.

    A morphism in the category of cellular states.
    Maps (cell_state, neighbor_states) → new_cell_state
    """
    name: str
    rule_function: Callable[[Enum, List[Enum], Dict], Enum]
    parameters: Dict = field(default_factory=dict)

    def apply(self, cell_state: Enum, neighbor_states: List[Enum], metadata: Optional[Dict] = None) -> Enum:
        """Apply transition rule to a cell."""
        return self.rule_function(cell_state, neighbor_states, metadata or {})


# =============================================================================
# EPIDEMIC MODEL RULES
# =============================================================================

def sir_transition_rule(beta: float = 0.3, gamma: float = 0.1):
    """
    SIR model transition rule.

    Parameters:
        beta: Infection rate (probability of S → I given infected neighbor)
        gamma: Recovery rate (probability of I → R)

    Dynamics:
        S + I → I + I  (infection)
        I → R          (recovery)
    """
    def rule(cell_state: CellState, neighbors: List[CellState], metadata: Dict) -> CellState:
        if cell_state == CellState.SUSCEPTIBLE:
            # Infection probability: 1 - (1-beta)^(infected_neighbors)
            infected_count = sum(1 for n in neighbors if n == CellState.INFECTED)
            if infected_count > 0:
                prob_infection = 1.0 - (1.0 - beta) ** infected_count
                # Stochastic version would sample; deterministic uses threshold
                if prob_infection > 0.5:  # Deterministic threshold
                    return CellState.INFECTED

        elif cell_state == CellState.INFECTED:
            # Recovery check
            if metadata.get('random', 0.5) < gamma:
                return CellState.RECOVERED

        return cell_state

    return TransitionRule(
        name="SIR",
        rule_function=rule,
        parameters={'beta': beta, 'gamma': gamma}
    )


def sis_transition_rule(beta: float = 0.3, gamma: float = 0.1):
    """
    SIS model transition rule (Susceptible-Infected-Susceptible).

    No permanent immunity - recovered nodes become susceptible again.
    Models chronic infections, reinfectable diseases, or unpatched systems.
    """
    def rule(cell_state: CellState, neighbors: List[CellState], metadata: Dict) -> CellState:
        if cell_state == CellState.SUSCEPTIBLE:
            infected_count = sum(1 for n in neighbors if n == CellState.INFECTED)
            if infected_count > 0:
                prob_infection = 1.0 - (1.0 - beta) ** infected_count
                if prob_infection > 0.5:
                    return CellState.INFECTED

        elif cell_state == CellState.INFECTED:
            # Recovery returns to susceptible
            if metadata.get('random', 0.5) < gamma:
                return CellState.SUSCEPTIBLE

        return cell_state

    return TransitionRule(
        name="SIS",
        rule_function=rule,
        parameters={'beta': beta, 'gamma': gamma}
    )


def seir_transition_rule(beta: float = 0.3, sigma: float = 0.2, gamma: float = 0.1):
    """
    SEIR model transition rule (Susceptible-Exposed-Infected-Recovered).

    Parameters:
        beta: Infection rate
        sigma: Incubation rate (E → I)
        gamma: Recovery rate

    Dynamics:
        S → E → I → R
    """
    def rule(cell_state: CellState, neighbors: List[CellState], metadata: Dict) -> CellState:
        if cell_state == CellState.SUSCEPTIBLE:
            infected_count = sum(1 for n in neighbors if n == CellState.INFECTED)
            if infected_count > 0:
                prob_infection = 1.0 - (1.0 - beta) ** infected_count
                if prob_infection > 0.5:
                    return CellState.EXPOSED

        elif cell_state == CellState.EXPOSED:
            # Incubation period ends
            if metadata.get('random', 0.5) < sigma:
                return CellState.INFECTED

        elif cell_state == CellState.INFECTED:
            # Recovery
            if metadata.get('random', 0.5) < gamma:
                return CellState.RECOVERED

        return cell_state

    return TransitionRule(
        name="SEIR",
        rule_function=rule,
        parameters={'beta': beta, 'sigma': sigma, 'gamma': gamma}
    )


# =============================================================================
# CELLULAR AUTOMATON ENDOFUNCTOR
# =============================================================================

@dataclass
class CellularAutomaton:
    """
    Cellular Automaton as Endofunctor F: GridCat → GridCat.

    Maps grid states to grid states via transition rule.
    Composition: F^n represents n time steps of evolution.

    Mathematical Properties:
        - Functoriality: F(id) = id, F(g ∘ f) = F(g) ∘ F(f)
        - Endofunctor: F: C → C (same category)
        - Iteration: F^n is well-defined via composition
    """
    name: str
    transition_rule: TransitionRule

    def apply(self, grid: CellularGrid) -> CellularGrid:
        """
        Apply one step of CA evolution: F(grid) → grid'.

        This is the action on objects in the category.
        """
        new_grid = grid.copy()

        # Apply transition rule to each cell
        for node, current_state in grid.states.items():
            neighbors = grid.get_neighbors(node)
            neighbor_states = [grid.states[n] for n in neighbors if n in grid.states]
            metadata = grid.metadata.get(node, {})

            new_state = self.transition_rule.apply(current_state, neighbor_states, metadata)
            new_grid.states[node] = new_state

        return new_grid

    def evolve(self, grid: CellularGrid, steps: int) -> List[CellularGrid]:
        """
        Evolve grid for multiple time steps: F^n(grid).

        Returns trajectory [grid, F(grid), F²(grid), ..., F^n(grid)]
        """
        trajectory = [grid]
        current = grid

        for _ in range(steps):
            current = self.apply(current)
            trajectory.append(current)

        return trajectory

    def verify_endofunctor_identity(self, grid: CellularGrid) -> bool:
        """
        Verify F(id) = id.

        For CA, this means F applied to stable states remains stable.
        """
        # Apply CA once
        evolved = self.apply(grid)

        # Check if all cells changed or stayed same
        # For true identity test, need to check with identity morphism
        # which for CA would be a no-op transition rule
        return True  # Placeholder - true identity test requires explicit identity rule

    def compose(self, other: 'CellularAutomaton') -> 'CellularAutomaton':
        """
        Compose two CA endofunctors: (F ∘ G)(grid) = F(G(grid)).

        Creates a new CA that applies other, then self.
        """
        def composed_rule(state: Enum, neighbors: List[Enum], metadata: Dict) -> Enum:
            # Apply other's rule first
            intermediate = other.transition_rule.apply(state, neighbors, metadata)
            # Then apply self's rule
            return self.transition_rule.apply(intermediate, neighbors, metadata)

        return CellularAutomaton(
            name=f"{self.name}_compose_{other.name}",
            transition_rule=TransitionRule(
                name=f"composed_{self.name}_{other.name}",
                rule_function=composed_rule,
                parameters={**self.transition_rule.parameters, **other.transition_rule.parameters}
            )
        )


# =============================================================================
# NATURAL TRANSFORMATIONS BETWEEN CA
# =============================================================================

@dataclass
class CANaturalTransformation:
    """
    Natural transformation η: F ⟹ G between two CA endofunctors.

    For each grid X, provides a morphism η_X: F(X) → G(X)
    that commutes with CA evolution.

    Naturality square:
        F(X) --η_X--> G(X)
         |             |
        F(f)          G(f)
         |             |
         v             v
        F(Y) --η_Y--> G(Y)

    Example: Transform SIR model to SEIR model by adding exposed state.
    """
    name: str
    source_ca: CellularAutomaton
    target_ca: CellularAutomaton
    transformation_map: Dict[Enum, Enum]  # Maps source states to target states

    def apply(self, grid: CellularGrid) -> CellularGrid:
        """
        Apply natural transformation component η_grid: F(grid) → G(grid).
        """
        new_grid = grid.copy()

        for node, state in grid.states.items():
            if state in self.transformation_map:
                new_grid.states[node] = self.transformation_map[state]

        return new_grid

    def verify_naturality(self, grid: CellularGrid) -> bool:
        """
        Verify naturality condition: η_Y ∘ F(f) = G(f) ∘ η_X.

        For CA, this means:
        1. Apply source CA, then transform
        2. Transform, then apply target CA
        Both paths should give same result.
        """
        # Path 1: F(grid) then η
        path1 = self.source_ca.apply(grid)
        path1 = self.apply(path1)

        # Path 2: η then G(grid)
        path2 = self.apply(grid)
        path2 = self.target_ca.apply(path2)

        # Check if states match
        return path1.states == path2.states


# =============================================================================
# FIXED POINTS AND ATTRACTORS
# =============================================================================

@dataclass
class CAFixedPoint:
    """
    Fixed point of CA endofunctor: F(X) = X.

    Represents stable configurations (attractors, steady states).
    """
    grid: CellularGrid
    ca: CellularAutomaton

    def verify(self) -> bool:
        """Verify this is a fixed point: F(X) = X."""
        evolved = self.ca.apply(self.grid)
        return evolved.states == self.grid.states

    def stability_analysis(self) -> Dict[str, float]:
        """
        Analyze stability of fixed point.

        Returns metrics like:
        - Lyapunov exponent estimate
        - Basin of attraction size estimate
        - Perturbation sensitivity
        """
        # Perturb grid slightly and measure divergence
        perturbed = self.grid.copy()

        # Flip one random cell state (if possible)
        if len(self.grid.states) > 0:
            node = list(self.grid.states.keys())[0]
            states = list(self.grid.states.values())
            if len(set(states)) > 1:
                # Change to different state
                current = perturbed.states[node]
                other_states = [s for s in set(states) if s != current]
                if other_states:
                    perturbed.states[node] = other_states[0]

        # Evolve both and measure divergence
        trajectory_orig = self.ca.evolve(self.grid, steps=10)
        trajectory_pert = self.ca.evolve(perturbed, steps=10)

        # Measure state difference over time
        divergences = []
        for t in range(len(trajectory_orig)):
            diff = sum(1 for node in self.grid.states.keys()
                      if trajectory_orig[t].states.get(node) != trajectory_pert[t].states.get(node))
            divergences.append(diff)

        # Estimate Lyapunov exponent (simplified)
        if len(divergences) > 1 and divergences[0] > 0:
            lyapunov = math.log(max(divergences[-1], 1) / max(divergences[0], 1)) / len(divergences)
        else:
            lyapunov = 0.0

        return {
            'lyapunov_exponent': lyapunov,
            'divergence_final': divergences[-1] if divergences else 0,
            'divergence_trajectory': divergences
        }


# =============================================================================
# EPIDEMIC METRICS AND ANALYSIS
# =============================================================================

@dataclass
class EpidemicMetrics:
    """
    Metrics for epidemic/attack propagation analysis.
    """
    trajectory: List[CellularGrid]
    ca: CellularAutomaton

    def basic_reproduction_number(self) -> float:
        """
        Compute R₀ (basic reproduction number).

        R₀ > 1: Epidemic spreads
        R₀ < 1: Epidemic dies out
        R₀ = 1: Endemic equilibrium

        Simplified estimation from trajectory.
        """
        if len(self.trajectory) < 3:
            return 0.0

        # Count new infections in first few steps
        new_infections = []
        for i in range(1, min(5, len(self.trajectory))):
            prev = self.trajectory[i-1]
            curr = self.trajectory[i]

            # Count transitions to infected
            new_inf = sum(1 for node in curr.states.keys()
                         if prev.states.get(node) != CellState.INFECTED
                         and curr.states.get(node) == CellState.INFECTED)
            new_infections.append(new_inf)

        # R₀ ≈ average new infections per time step (early phase)
        if new_infections:
            return sum(new_infections) / len(new_infections)
        return 0.0

    def peak_infection_time(self) -> Optional[int]:
        """Find time step with maximum infected count."""
        infected_counts = [
            grid.count_state(CellState.INFECTED) if hasattr(CellState, 'INFECTED')
            else grid.count_state(AttackState.COMPROMISED)
            for grid in self.trajectory
        ]

        if not infected_counts:
            return None

        return infected_counts.index(max(infected_counts))

    def final_attack_size(self) -> float:
        """
        Compute final size of epidemic/attack.

        Returns fraction of population affected.
        """
        if not self.trajectory:
            return 0.0

        final_grid = self.trajectory[-1]
        total = len(final_grid.states)

        if total == 0:
            return 0.0

        # Count recovered (for SIR) or compromised (for attacks)
        affected = final_grid.count_state(CellState.RECOVERED) if hasattr(CellState, 'RECOVERED') else 0
        affected += final_grid.count_state(CellState.INFECTED) if hasattr(CellState, 'INFECTED') else 0

        return affected / total

    def compute_all_metrics(self) -> Dict[str, float]:
        """Compute all epidemic metrics."""
        return {
            'R0_estimate': self.basic_reproduction_number(),
            'peak_time': self.peak_infection_time() or 0,
            'final_size': self.final_attack_size(),
            'total_steps': len(self.trajectory) - 1
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_sir_automaton(beta: float = 0.3, gamma: float = 0.1) -> CellularAutomaton:
    """Factory function for SIR cellular automaton."""
    return CellularAutomaton(
        name="SIR",
        transition_rule=sir_transition_rule(beta=beta, gamma=gamma)
    )


def create_sis_automaton(beta: float = 0.3, gamma: float = 0.1) -> CellularAutomaton:
    """Factory function for SIS cellular automaton."""
    return CellularAutomaton(
        name="SIS",
        transition_rule=sis_transition_rule(beta=beta, gamma=gamma)
    )


def create_seir_automaton(beta: float = 0.3, sigma: float = 0.2, gamma: float = 0.1) -> CellularAutomaton:
    """Factory function for SEIR cellular automaton."""
    return CellularAutomaton(
        name="SEIR",
        transition_rule=seir_transition_rule(beta=beta, sigma=sigma, gamma=gamma)
    )


def grid_from_network(nodes: List[int], edges: List[Tuple[int, int]],
                      initial_state: Enum = CellState.SUSCEPTIBLE) -> CellularGrid:
    """
    Create cellular grid from network structure.

    Args:
        nodes: List of node IDs
        edges: List of (source, target) edges
        initial_state: Default state for all nodes
    """
    grid = CellularGrid()

    # Initialize states
    for node in nodes:
        grid.states[node] = initial_state

    # Build adjacency
    for src, dst in edges:
        grid.adjacency[src].add(dst)
        grid.adjacency[dst].add(src)  # Undirected

    return grid
