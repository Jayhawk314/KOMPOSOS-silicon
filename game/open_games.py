"""
Open Games - Compositional Game Theory

Open games are games that can be composed:
- Sequentially (play one, then another)
- In parallel (play simultaneously)

An open game G: (X, S) → (Y, R) has:
- X: input type (observations/context)
- S: output type (strategies/moves)
- Y: costate type (results from continuation)
- R: coutility type (payoffs returned to environment)

The key insight: Games are MORPHISMS in a symmetric monoidal category.
This means we can build complex games from simple ones compositionally.

In KOMPOSOS-III, the encoder/decoder closed loop IS an open game:
- Encoder (Opus): observes query, outputs representation
- Decoder (Formal): observes representation, outputs verification
- They play until Nash equilibrium (stable answer)

References:
- Hedges: "Compositional Game Theory" (2016)
- Ghani, Hedges, Winschel, Zahn: "Compositional Game Theory" (2018)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Tuple, List, Dict, Optional, Generic, TypeVar

X = TypeVar('X')  # Input/observation type
S = TypeVar('S')  # Strategy/move type
Y = TypeVar('Y')  # Costate/result type
R = TypeVar('R')  # Coutility/payoff type


@dataclass
class OpenGame(Generic[X, S, Y, R]):
    """
    An open game G: (X, S) → (Y, R)

    Components:
    - play: X → S (strategy selection given observations)
    - coplay: X × Y → R (coutility computation)

    The game takes observations X, produces moves S,
    receives results Y from the continuation,
    and returns payoffs R to the environment.
    """
    name: str

    # Type information
    input_type: Any      # X
    output_type: Any     # S
    costate_type: Any    # Y
    coutility_type: Any  # R

    # Game functions
    play: Callable[[Any], Any]           # X → S
    coplay: Callable[[Any, Any], Any]    # X × Y → R

    # Best response function (for equilibrium)
    best_response: Optional[Callable[[Any, Any], Any]] = None  # X × (S→Y) → S

    def __repr__(self):
        return f"OpenGame({self.name}: {self.input_type} → {self.output_type})"

    def evaluate(self, observation: X, continuation_result: Y) -> Tuple[S, R]:
        """
        Evaluate the game:
        1. Play: select strategy given observation
        2. Coplay: compute coutility given result
        """
        strategy = self.play(observation)
        coutility = self.coplay(observation, continuation_result)
        return strategy, coutility


class OpenGameCategory:
    """
    The symmetric monoidal category of open games.

    Objects: pairs (X, S) of types
    Morphisms: open games G: (X, S) → (Y, R)

    Composition: sequential play
    Tensor product: parallel play
    """

    def compose(self, g1: OpenGame, g2: OpenGame) -> OpenGame:
        """
        Sequential composition: g2 ∘ g1

        Play g1 first, then g2.
        The output of g1 feeds into g2.
        """
        def composed_play(x):
            s1 = g1.play(x)
            return g2.play(s1)

        def composed_coplay(x, r):
            # Work backwards: get g2's coutility
            s1 = g1.play(x)
            y = g2.coplay(s1, r)
            # Then g1's coutility
            return g1.coplay(x, y)

        return OpenGame(
            name=f"{g2.name}∘{g1.name}",
            input_type=g1.input_type,
            output_type=g2.output_type,
            costate_type=g2.costate_type,
            coutility_type=g1.coutility_type,
            play=composed_play,
            coplay=composed_coplay
        )

    def tensor(self, g1: OpenGame, g2: OpenGame) -> OpenGame:
        """
        Parallel composition: g1 ⊗ g2

        Play g1 and g2 simultaneously.
        """
        def tensor_play(x):
            # x = (x1, x2)
            x1, x2 = x
            s1 = g1.play(x1)
            s2 = g2.play(x2)
            return (s1, s2)

        def tensor_coplay(x, y):
            x1, x2 = x
            y1, y2 = y
            r1 = g1.coplay(x1, y1)
            r2 = g2.coplay(x2, y2)
            return (r1, r2)

        return OpenGame(
            name=f"{g1.name}⊗{g2.name}",
            input_type=(g1.input_type, g2.input_type),
            output_type=(g1.output_type, g2.output_type),
            costate_type=(g1.costate_type, g2.costate_type),
            coutility_type=(g1.coutility_type, g2.coutility_type),
            play=tensor_play,
            coplay=tensor_coplay
        )

    def identity(self, obj_type: Any) -> OpenGame:
        """
        Identity game: pass through unchanged.
        """
        return OpenGame(
            name=f"id_{obj_type}",
            input_type=obj_type,
            output_type=obj_type,
            costate_type=obj_type,
            coutility_type=obj_type,
            play=lambda x: x,
            coplay=lambda x, y: y
        )

    def counit(self, obj_type: Any) -> OpenGame:
        """
        Counit: terminal game that produces nothing.
        """
        return OpenGame(
            name=f"counit_{obj_type}",
            input_type=obj_type,
            output_type=None,
            costate_type=None,
            coutility_type=obj_type,
            play=lambda x: None,
            coplay=lambda x, y: x
        )


# Utility functions for creating common games

def decision_game(
    name: str,
    observation_type: Any,
    action_type: Any,
    utility_fn: Callable[[Any, Any], float]
) -> OpenGame:
    """
    Create a simple decision game.

    The player observes X, chooses action A,
    and receives utility based on (observation, action).
    """
    def play(obs):
        # Default: return None (to be replaced by strategy)
        return None

    def coplay(obs, result):
        # Result contains the action taken
        if result is not None:
            return utility_fn(obs, result)
        return 0.0

    return OpenGame(
        name=name,
        input_type=observation_type,
        output_type=action_type,
        costate_type=action_type,  # sees the action
        coutility_type=float,
        play=play,
        coplay=coplay
    )


def constant_game(name: str, value: Any) -> OpenGame:
    """
    A game that always outputs a constant value.
    """
    return OpenGame(
        name=name,
        input_type=Any,
        output_type=type(value),
        costate_type=None,
        coutility_type=None,
        play=lambda _: value,
        coplay=lambda _, __: None
    )


def lens_game(
    name: str,
    get: Callable[[Any], Any],
    put: Callable[[Any, Any], Any]
) -> OpenGame:
    """
    Create a game from a lens (get/put pair).

    This connects open games to lenses/optics.
    """
    return OpenGame(
        name=name,
        input_type="S",  # source
        output_type="A",  # focus
        costate_type="B",  # updated focus
        coutility_type="T",  # updated source
        play=get,
        coplay=put
    )


# String diagram representation

class StringDiagram:
    """
    String diagram representation of open games.

    In string diagrams:
    - Wires = types
    - Boxes = games
    - Composition = connect wires
    """

    def __init__(self):
        self.boxes: List[OpenGame] = []
        self.wires: List[Tuple[str, str]] = []

    def add_game(self, game: OpenGame, position: Tuple[int, int] = (0, 0)):
        """Add a game box to the diagram."""
        self.boxes.append(game)

    def connect(self, source_game: str, source_port: str,
                target_game: str, target_port: str):
        """Connect two game ports with a wire."""
        self.wires.append((f"{source_game}.{source_port}",
                          f"{target_game}.{target_port}"))

    def to_ascii(self) -> str:
        """Render as ASCII art."""
        lines = []
        for game in self.boxes:
            lines.append(f"┌─────────────────┐")
            lines.append(f"│ {game.name:^15} │")
            lines.append(f"│ {game.input_type} → {game.output_type} │")
            lines.append(f"└─────────────────┘")
            lines.append("        │")
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    # Create a simple decision game
    def utility(obs, action):
        # Payoff depends on matching action to observation
        return 1.0 if action == obs else 0.0

    game1 = decision_game("Choose", "Observation", "Action", utility)
    print(f"Game 1: {game1}")

    # Create another game
    game2 = decision_game("Verify", "Action", "Result", lambda a, r: float(r))
    print(f"Game 2: {game2}")

    # Compose them
    cat = OpenGameCategory()
    composed = cat.compose(game1, game2)
    print(f"Composed: {composed}")

    # Parallel
    parallel = cat.tensor(game1, game2)
    print(f"Parallel: {parallel}")

    # String diagram
    diagram = StringDiagram()
    diagram.add_game(game1)
    diagram.add_game(game2)
    print("\nString diagram:")
    print(diagram.to_ascii())
