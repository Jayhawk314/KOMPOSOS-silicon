# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Forge Core -- the outer shell (Layer 1)

The plugin framework that hosts OPERADUM, mirror of Orion (KOMPOSOS-IV's host).
Forge owns the event bus, the capability registry, and the plugin lifecycle. It
knows nothing about operads -- domain content and the operadic runtime are
plugins inside it.

Capability DI: a plugin that `requires` 'component_store' starts only once
another plugin `provides` it. Forge starts plugins in dependency order and
refuses to start if a requirement can never be satisfied.
"""

from __future__ import annotations
from typing import Any, Dict, List

from .events import EventBus
from .plugin import Plugin


class CapabilityError(RuntimeError):
    """Raised when required capabilities cannot be satisfied."""


class Forge:
    """The plugin host: bus + capability registry + lifecycle."""

    def __init__(self, name: str = "forge"):
        self.name = name
        self.bus = EventBus()
        self._plugins: List[Plugin] = []
        self._started: List[Plugin] = []
        self._caps: Dict[str, Any] = {}

    # ---------------- registration ----------------

    def register(self, plugin: Plugin) -> "Forge":
        """Register a plugin (does not start it). Chainable."""
        plugin.bind(self)
        self._plugins.append(plugin)
        return self

    def capability(self, name: str) -> Any:
        """Resolve a started capability by name (None if absent)."""
        return self._caps.get(name)

    def has(self, name: str) -> bool:
        return name in self._caps

    def emit(self, topic: str, **data: Any) -> None:
        self.bus.emit(topic, **data)

    # ---------------- lifecycle ----------------

    def start(self) -> "Forge":
        """Start all registered plugins in dependency order.

        Repeatedly start any plugin whose requirements are already provided,
        registering its capabilities, until none remain or no progress is made.
        Unsatisfiable requirements raise CapabilityError -- the dual of Orion's
        "a plugin requiring X only starts if one provides X".
        """
        pending = [p for p in self._plugins if p not in self._started]
        progressed = True
        while pending and progressed:
            progressed = False
            for plugin in list(pending):
                if all(self.has(req) for req in plugin.requires):
                    plugin.on_start()
                    for cap_name, cap in plugin.capabilities().items():
                        self._caps[cap_name] = cap
                    self._started.append(plugin)
                    pending.remove(plugin)
                    progressed = True
                    self.emit("plugin.started", plugin=plugin.name,
                              provides=list(plugin.capabilities().keys()))
        if pending:
            unmet = {
                p.name: [r for r in p.requires if not self.has(r)] for p in pending
            }
            raise CapabilityError(f"unsatisfied capability requirements: {unmet}")
        return self

    def stop(self) -> None:
        """Stop started plugins in reverse order."""
        for plugin in reversed(self._started):
            plugin.on_stop()
            self.emit("plugin.stopped", plugin=plugin.name)
        self._started.clear()
        self._caps.clear()

    # ---------------- introspection ----------------

    @property
    def plugins(self) -> List[str]:
        return [p.name for p in self._plugins]

    @property
    def started(self) -> List[str]:
        return [p.name for p in self._started]

    @property
    def capabilities_available(self) -> List[str]:
        return list(self._caps.keys())
