# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Hook System: Structural Events in the Operadic Runtime

The dual of KOMPOSOS-IV's core/hooks.py. Hooks fire when the *constructive*
structure of the operad changes -- a colour or operation is added, two
operations are composed, a design is realized. They are the structural
events that bridges (Forge plugins) listen to.

Events:
  "colour_added"       -- A colour (interface type) was added
  "colour_removed"     -- A colour was removed (cascades to its operations)
  "operation_added"    -- An operation (build rule) was added
  "operation_removed"  -- An operation was removed
  "composed"           -- Two operations/composites were plugged together
  "realized"           -- A composite was turned into an executable artifact
  "bulk_loaded"        -- A bulk load completed
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List
from collections import defaultdict


EVENTS = frozenset({
    "colour_added",
    "colour_removed",
    "operation_added",
    "operation_removed",
    "composed",
    "realized",
    "bulk_loaded",
})


class HookRegistry:
    """
    Registry for operadic event hooks.

    Hooks fire synchronously in registration order when structural events
    occur in an Operad. Mirror of KOMPOSOS's HookRegistry, dual events.

    Usage:
        hooks = HookRegistry()
        hooks.on("operation_added", lambda operation: print(operation.name))
        hooks.fire("operation_added", operation=some_op)
    """

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)

    def on(self, event: str, fn: Callable) -> None:
        """Register a hook for an event."""
        self._hooks[event].append(fn)

    def off(self, event: str, fn: Callable) -> bool:
        """Unregister a hook. Returns True if it was found and removed."""
        hooks = self._hooks.get(event, [])
        try:
            hooks.remove(fn)
            return True
        except ValueError:
            return False

    def fire(self, event: str, **kwargs: Any) -> None:
        """Fire all hooks for an event, synchronously, in registration order."""
        for fn in self._hooks.get(event, []):
            fn(**kwargs)

    def clear(self, event: str = None) -> None:
        """Clear hooks for one event, or all hooks if event is None."""
        if event is not None:
            self._hooks.pop(event, None)
        else:
            self._hooks.clear()

    @property
    def count(self) -> int:
        """Total number of registered hooks across all events."""
        return sum(len(hooks) for hooks in self._hooks.values())
