"""
KOMPOSOS-III Game Engine (Layer D)

Game-theoretic foundations:
- Open games as categorical morphisms
- Nash equilibrium finding (not gradient descent)
- Backward induction from goals
- Encoder/Decoder minimax game
"""

from .open_games import OpenGame, OpenGameCategory
from .nash import Strategy, NashEquilibrium, find_nash_equilibria

__all__ = [
    "OpenGame",
    "OpenGameCategory",
    "Strategy",
    "NashEquilibrium",
    "find_nash_equilibria",
]
