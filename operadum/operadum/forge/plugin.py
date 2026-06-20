# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Forge Plugin Base -- the DX layer

A plugin declares the capabilities it `provides` and `requires`, builds its
service in `on_start`, and exposes that service via `capabilities()`. Forge
starts plugins in dependency order: one that requires `component_store` only
starts once another has provided it (capability DI, mirror of Orion).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Forge


class Plugin:
    """Base class for Forge plugins. Subclass and set name/provides/requires."""

    #: Unique plugin name.
    name: str = "plugin"
    #: Capability names this plugin makes available to others.
    provides: List[str] = []
    #: Capability names this plugin needs before it can start.
    requires: List[str] = []

    def __init__(self):
        self.core: Optional["Forge"] = None

    def bind(self, core: "Forge") -> None:
        """Attach the owning Forge so the plugin can resolve capabilities/emit."""
        self.core = core

    def capability(self, name: str) -> Any:
        """Look up a capability provided by another (already-started) plugin."""
        assert self.core is not None, "plugin not bound to a Forge"
        return self.core.capability(name)

    def emit(self, topic: str, **data: Any) -> None:
        assert self.core is not None, "plugin not bound to a Forge"
        self.core.emit(topic, **data)

    # ---- lifecycle (override as needed) ----

    def on_start(self) -> None:
        """Build the plugin's service. Required capabilities are available here."""

    def on_stop(self) -> None:
        """Tear down. Called in reverse start order."""

    def capabilities(self) -> Dict[str, Any]:
        """The services this plugin provides, keyed by capability name. Called
        after on_start."""
        return {}
