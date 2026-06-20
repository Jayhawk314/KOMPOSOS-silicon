# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Hook System: Structural Events in the Categorical Runtime

Hooks fire on categorical events -- when the structure of the category
changes. Inspired by Orion's insight: hooks are structural, not just
callbacks. They are morphisms in the meta-category of the runtime itself.

Events:
  "object_added"    -- An object was added to the category
  "object_removed"  -- An object was removed from the category
  "morphism_added"  -- A morphism was added
  "morphism_removed"-- A morphism was removed
  "composed"        -- Two morphisms were composed
  "path_found"      -- A path was discovered between objects
  "bulk_loaded"     -- A bulk load operation completed
"""

from __future__ import annotations
from typing import Callable, Dict, List, Any
from collections import defaultdict


# All recognized event types
EVENTS = frozenset({
    "object_added",
    "object_removed",
    "morphism_added",
    "morphism_removed",
    "composed",
    "path_found",
    "bulk_loaded",
})


class HookRegistry:
    """
    Registry for categorical event hooks.

    Hooks fire synchronously in registration order when structural
    events occur in a Category.

    Usage:
        hooks = HookRegistry()
        hooks.on("morphism_added", lambda morphism: print(f"New: {morphism.name}"))
        hooks.fire("morphism_added", morphism=some_morphism)
    """

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)

    def on(self, event: str, fn: Callable) -> None:
        """
        Register a hook for an event.

        Args:
            event: Event name (see EVENTS).
            fn: Callable to invoke when the event fires.
                Receives keyword arguments specific to the event.
        """
        self._hooks[event].append(fn)

    def off(self, event: str, fn: Callable) -> bool:
        """
        Unregister a hook.

        Args:
            event: Event name.
            fn: The callable to remove.

        Returns:
            True if the hook was found and removed, False otherwise.
        """
        hooks = self._hooks.get(event, [])
        try:
            hooks.remove(fn)
            return True
        except ValueError:
            return False

    def fire(self, event: str, **kwargs: Any) -> None:
        """
        Fire all hooks for an event.

        Hooks run synchronously in registration order.
        If a hook raises, it propagates (fail-fast).

        Args:
            event: Event name.
            **kwargs: Event-specific data passed to each hook.
        """
        for fn in self._hooks.get(event, []):
            fn(**kwargs)

    def clear(self, event: str = None) -> None:
        """
        Clear hooks.

        Args:
            event: If given, clear hooks for this event only.
                   If None, clear all hooks.
        """
        if event is not None:
            self._hooks.pop(event, None)
        else:
            self._hooks.clear()

    @property
    def count(self) -> int:
        """Total number of registered hooks across all events."""
        return sum(len(hooks) for hooks in self._hooks.values())
