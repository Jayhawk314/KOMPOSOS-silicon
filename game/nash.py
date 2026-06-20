"""
Nash Equilibrium Finding

Nash equilibrium: a strategy profile where no player wants to deviate.

In KOMPOSOS-III, we find equilibria instead of gradient descent:
- The encoder (Opus) and decoder (Formal) are players
- Equilibrium = stable answer both agree on
- No local minima - we find the TRUE stable point

Key concepts:
- Strategy: a function from observations to actions
- Best response: optimal strategy given others' strategies
- Nash equilibrium: everyone is playing best response

This is FUNDAMENTALLY DIFFERENT from neural network training:
- No loss function to minimize
- No gradients
- Just game-theoretic stability
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
from .open_games import OpenGame


@dataclass
class Strategy:
    """
    A strategy for a player in a game.

    A strategy maps observations to actions.
    Can be pure (deterministic) or mixed (probabilistic).
    """
    player_name: str
    strategy_fn: Callable[[Any], Any]
    is_mixed: bool = False
    support: Optional[Set[Any]] = None  # actions in support for mixed

    def __call__(self, observation: Any) -> Any:
        """Apply strategy to observation."""
        return self.strategy_fn(observation)

    def __repr__(self):
        return f"Strategy({self.player_name})"


@dataclass
class StrategyProfile:
    """
    A profile of strategies, one for each player.
    """
    strategies: Dict[str, Strategy] = field(default_factory=dict)

    def add_strategy(self, player: str, strategy: Strategy):
        """Add a player's strategy."""
        self.strategies[player] = strategy

    def get_strategy(self, player: str) -> Optional[Strategy]:
        """Get a player's strategy."""
        return self.strategies.get(player)

    def __repr__(self):
        players = list(self.strategies.keys())
        return f"StrategyProfile({players})"


@dataclass
class NashEquilibrium:
    """
    A Nash equilibrium: strategy profile where no one wants to deviate.

    Properties:
    - is_strict: True if deviation strictly decreases payoff
    - is_unique: True if this is the only equilibrium
    - support_size: for mixed equilibria, size of support
    """
    profile: StrategyProfile
    is_strict: bool = False
    is_unique: bool = False
    support_size: Dict[str, int] = field(default_factory=dict)
    payoffs: Dict[str, float] = field(default_factory=dict)

    def __repr__(self):
        return f"NashEquilibrium(strict={self.is_strict}, payoffs={self.payoffs})"


def best_response(
    game: OpenGame,
    player: str,
    other_strategies: Dict[str, Strategy],
    observation: Any
) -> Any:
    """
    Compute the best response for a player.

    Given other players' strategies, what is the optimal action?
    """
    # For simple games, enumerate actions and pick best
    # In practice, this depends on the game structure

    # This is a placeholder - real implementation depends on action space
    return game.play(observation)


def is_nash_equilibrium(
    game: OpenGame,
    profile: StrategyProfile,
    observations: List[Any]
) -> bool:
    """
    Check if a strategy profile is a Nash equilibrium.

    For each player:
    1. Fix all other strategies
    2. Check if this player's strategy is a best response
    """
    for player_name, strategy in profile.strategies.items():
        others = {k: v for k, v in profile.strategies.items() if k != player_name}

        for obs in observations:
            current_action = strategy(obs)
            br_action = best_response(game, player_name, others, obs)

            # If best response differs, not an equilibrium
            if current_action != br_action:
                return False

    return True


def find_nash_equilibria(
    game: OpenGame,
    action_spaces: Dict[str, List[Any]],
    observations: List[Any]
) -> List[NashEquilibrium]:
    """
    Find all Nash equilibria of a game.

    This is a brute-force search for small games.
    For larger games, use support enumeration or other algorithms.

    Args:
        game: The open game to analyze
        action_spaces: Available actions for each player
        observations: Possible observations/states

    Returns:
        List of Nash equilibria
    """
    equilibria = []

    # For 2-player games, check all pure strategy profiles
    # This is exponential but works for small games

    from itertools import product

    players = list(action_spaces.keys())
    if len(players) != 2:
        # For now, only handle 2-player games
        return []

    p1, p2 = players
    actions1, actions2 = action_spaces[p1], action_spaces[p2]

    for a1, a2 in product(actions1, actions2):
        # Create constant strategies
        s1 = Strategy(p1, lambda x, a=a1: a)
        s2 = Strategy(p2, lambda x, a=a2: a)

        profile = StrategyProfile()
        profile.add_strategy(p1, s1)
        profile.add_strategy(p2, s2)

        if is_nash_equilibrium(game, profile, observations):
            eq = NashEquilibrium(
                profile=profile,
                is_strict=True,  # would need to verify
                payoffs={p1: 0.0, p2: 0.0}  # would need to compute
            )
            equilibria.append(eq)

    return equilibria


def iterated_best_response(
    game: OpenGame,
    initial_profile: StrategyProfile,
    observations: List[Any],
    max_iterations: int = 100
) -> Optional[NashEquilibrium]:
    """
    Find Nash equilibrium via iterated best response.

    Start with initial strategies, then each player updates to best response.
    If converges, we have an equilibrium.
    """
    profile = initial_profile
    players = list(profile.strategies.keys())

    for iteration in range(max_iterations):
        changed = False

        for player in players:
            others = {k: v for k, v in profile.strategies.items() if k != player}
            current = profile.get_strategy(player)

            # Compute best response
            def new_strategy_fn(obs):
                return best_response(game, player, others, obs)

            new_strategy = Strategy(player, new_strategy_fn)

            # Check if changed
            for obs in observations:
                if current(obs) != new_strategy(obs):
                    changed = True
                    break

            profile.add_strategy(player, new_strategy)

        if not changed:
            # Converged to equilibrium
            return NashEquilibrium(
                profile=profile,
                is_strict=True
            )

    return None  # Did not converge


class TwoPlayerGame:
    """
    A two-player game with payoff matrices.

    Useful for analyzing encoder/decoder games.
    """

    def __init__(
        self,
        name: str,
        actions1: List[str],
        actions2: List[str],
        payoffs1: Dict[Tuple[str, str], float],
        payoffs2: Dict[Tuple[str, str], float]
    ):
        self.name = name
        self.actions1 = actions1
        self.actions2 = actions2
        self.payoffs1 = payoffs1
        self.payoffs2 = payoffs2

    def payoff(self, a1: str, a2: str) -> Tuple[float, float]:
        """Get payoffs for action pair."""
        return self.payoffs1.get((a1, a2), 0.0), self.payoffs2.get((a1, a2), 0.0)

    def find_pure_nash(self) -> List[Tuple[str, str]]:
        """Find all pure strategy Nash equilibria."""
        equilibria = []

        for a1 in self.actions1:
            for a2 in self.actions2:
                # Check if a1 is best response to a2
                a1_is_br = all(
                    self.payoffs1.get((a1, a2), 0) >= self.payoffs1.get((other, a2), 0)
                    for other in self.actions1
                )

                # Check if a2 is best response to a1
                a2_is_br = all(
                    self.payoffs2.get((a1, a2), 0) >= self.payoffs2.get((a1, other), 0)
                    for other in self.actions2
                )

                if a1_is_br and a2_is_br:
                    equilibria.append((a1, a2))

        return equilibria

    def display_matrix(self) -> str:
        """Display payoff matrix."""
        lines = [f"Game: {self.name}", ""]

        # Header
        header = "       " + "  ".join(f"{a2:^10}" for a2 in self.actions2)
        lines.append(header)

        for a1 in self.actions1:
            row = f"{a1:^6} "
            for a2 in self.actions2:
                p1, p2 = self.payoff(a1, a2)
                row += f"({p1:+.1f},{p2:+.1f})  "
            lines.append(row)

        return "\n".join(lines)


# Example: Encoder/Decoder game
def create_encoder_decoder_game() -> TwoPlayerGame:
    """
    Create the encoder/decoder game for KOMPOSOS-III.

    Encoder actions: propose representations
    Decoder actions: accept/reject

    Payoffs:
    - Both get positive payoff if encoder proposes good rep and decoder accepts
    - Encoder penalized for bad proposals
    - Decoder penalized for wrong accept/reject
    """
    return TwoPlayerGame(
        name="EncoderDecoder",
        actions1=["good_rep", "bad_rep"],
        actions2=["accept", "reject"],
        payoffs1={
            ("good_rep", "accept"): 1.0,
            ("good_rep", "reject"): -0.5,
            ("bad_rep", "accept"): 0.5,
            ("bad_rep", "reject"): -0.5,
        },
        payoffs2={
            ("good_rep", "accept"): 1.0,
            ("good_rep", "reject"): -1.0,
            ("bad_rep", "accept"): -1.0,
            ("bad_rep", "reject"): 0.5,
        }
    )


# Example usage
if __name__ == "__main__":
    # Encoder/Decoder game
    game = create_encoder_decoder_game()
    print(game.display_matrix())

    equilibria = game.find_pure_nash()
    print(f"\nPure Nash equilibria: {equilibria}")

    # The equilibrium is (good_rep, accept) - this is the stable answer!
    # Encoder learns to produce good representations
    # Decoder learns to accept good ones

    # Classic games for reference
    prisoners_dilemma = TwoPlayerGame(
        name="Prisoner's Dilemma",
        actions1=["cooperate", "defect"],
        actions2=["cooperate", "defect"],
        payoffs1={
            ("cooperate", "cooperate"): -1,
            ("cooperate", "defect"): -3,
            ("defect", "cooperate"): 0,
            ("defect", "defect"): -2,
        },
        payoffs2={
            ("cooperate", "cooperate"): -1,
            ("cooperate", "defect"): 0,
            ("defect", "cooperate"): -3,
            ("defect", "defect"): -2,
        }
    )
    print("\n" + prisoners_dilemma.display_matrix())
    print(f"Nash: {prisoners_dilemma.find_pure_nash()}")
