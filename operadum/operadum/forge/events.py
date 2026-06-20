# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Forge Event Bus -- the outer shell's pub/sub

Mirror of Orion's event bus (KOMPOSOS-IV's plugin host). The bus carries
lifecycle and design events between Forge plugins; it knows nothing about
operads. Synchronous and in registration order -- deterministic and easy to
reason about; a handler may itself emit (re-entrant).
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable, Dict, List, Tuple


class EventBus:
    """In-process pub/sub. `subscribe` to a topic, `emit` to fan out."""

    def __init__(self, keep_history: bool = True):
        self._subs: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[Tuple[str, Dict[str, Any]]] = []
        self._keep_history = keep_history

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subs[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable) -> bool:
        handlers = self._subs.get(topic, [])
        try:
            handlers.remove(handler)
            return True
        except ValueError:
            return False

    def emit(self, topic: str, **data: Any) -> None:
        """Fire all handlers subscribed to `topic`, in registration order."""
        if self._keep_history:
            self._history.append((topic, dict(data)))
        for handler in list(self._subs.get(topic, [])):
            handler(**data)

    def history(self) -> List[Tuple[str, Dict[str, Any]]]:
        return list(self._history)

    @property
    def topics(self) -> List[str]:
        return list(self._subs.keys())
