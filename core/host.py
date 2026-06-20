# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Host — the plugin-host seam for the self-improvement loop.

KOMPOSOS's self-correction loop (architect → self_corrector → plugin_generator)
needs a plugin host to *hot-load* the capabilities it generates: an event bus, a
capability registry, and a plugin lifecycle. Historically that host was Orion
(a third-party framework). This module makes the dependency a thin, swappable
**interface** instead:

    Host                      the API the loop needs (async, Orion-shaped)
    ForgeHost(Host)           backed by OPERADUM's own FORGE (operadum.forge)
    Plugin / on / hook        Orion-compatible plugin surface, no orion_core

`build_host()` returns a `ForgeHost` wrapping a real `operadum.forge.Forge` when
it is importable, else an equivalent native host with the same behaviour. Either
way the loop runs with **zero dependency on any external framework**. The day a
canonical Orion ships, write one more `Host` implementation and swap it at this
single seam — nothing else changes.

Why an adapter and not "just use Forge": the loop speaks Orion's async dialect
(`await host.emit(topic, {payload})`, `await host.register_plugin(p)`,
`await host.get_capability(name)`, `@on`-decorated async handlers receiving an
`Event`), while FORGE's bus is synchronous and kwargs-shaped. ForgeHost bridges
the two: it uses FORGE as the real bus + capability registry for native plugins,
and layers async/event-object delivery on top for Orion-style plugins.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# FORGE discovery (operadum.forge) — optional, lazy
# ══════════════════════════════════════════════════════════════════════════════

def _load_forge():
    """Return (Forge, ForgeEventBus) classes if OPERADUM's FORGE is importable, else (None, None)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    operadum_root = os.path.join(repo_root, "operadum")
    if operadum_root not in sys.path:
        sys.path.insert(0, operadum_root)
    try:
        from operadum.forge.core import Forge
        from operadum.forge.events import EventBus
        return Forge, EventBus
    except Exception as exc:  # pragma: no cover - depends on operadum presence
        logger.debug("FORGE unavailable, using native host bus: %s", exc)
        return None, None


# ══════════════════════════════════════════════════════════════════════════════
# Event + decorators — Orion-compatible plugin surface
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Event:
    """What an `@on`-decorated handler receives. `event.data` is the payload dict."""
    topic: str
    data: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:       # event["key"] convenience
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def on(topic: str) -> Callable:
    """Subscribe a plugin method to an event topic (Orion `@on` shape).

    The decorated method is called with a single `Event` argument when the host
    emits `topic`. The method may be sync or async.
    """
    def decorator(fn: Callable) -> Callable:
        fn._kompos_subscribe = (topic, "event")
        return fn
    return decorator


def hook(topic: str, priority: int = 10) -> Callable:
    """Register a prioritised lifecycle hook (Orion `@hook` shape).

    Like `on`, but hooks fire in ascending `priority` order before plain `on`
    subscribers. Useful for ordering structural side effects.
    """
    def decorator(fn: Callable) -> Callable:
        fn._kompos_subscribe = (topic, "hook")
        fn._kompos_priority = priority
        return fn
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# Plugin — base class for hosted capabilities (Orion/FORGE compatible)
# ══════════════════════════════════════════════════════════════════════════════

class Plugin:
    """Base class for host plugins.

    Compatible with both calling conventions found in the codebase:
      * FORGE style  — subclass sets class attrs ``name`` / ``provides`` / ``requires``.
      * Orion style  — ``super().__init__(core, name=..., provides=[...], ...)``
        (this is what `core.plugin_generator` emits).

    Lifecycle (`on_start`/`on_stop`) may be sync or async; the host awaits either.
    Capabilities default to ``{name: self}`` for every entry in ``provides`` so a
    generated plugin is resolvable by capability without extra boilerplate.
    """

    name: str = "plugin"
    provides: List[str] = []
    requires: List[str] = []

    def __init__(self, core: Optional["Host"] = None, **meta: Any):
        self.core: Optional["Host"] = core
        if "name" in meta:
            self.name = meta["name"]
        # Instance-level provides/requires override class attrs when supplied.
        if meta.get("provides") is not None:
            self.provides = list(meta["provides"])
        if meta.get("requires") is not None:
            self.requires = list(meta["requires"])
        self.version = meta.get("version", "0.1.0")
        self.description = meta.get("description", "")
        self.events_consumed = list(meta.get("events_consumed", []) or [])
        self.events_published = list(meta.get("events_published", []) or [])

    def bind(self, core: "Host") -> None:
        self.core = core

    async def emit(self, topic: str, data: Optional[Dict[str, Any]] = None, **kw: Any) -> None:
        assert self.core is not None, "plugin not bound to a Host"
        await self.core.emit(topic, data, **kw)

    async def capability(self, name: str) -> Any:
        assert self.core is not None, "plugin not bound to a Host"
        return await self.core.get_capability(name)

    # ---- lifecycle (override as needed) ----

    async def on_start(self) -> None:
        """Build the plugin's service. Required capabilities are available here."""

    async def on_stop(self) -> None:
        """Tear down. Called when the plugin/capability is unloaded."""

    def capabilities(self) -> Dict[str, Any]:
        """Services this plugin provides, keyed by capability name.

        Default: expose the plugin itself under each declared `provides` name.
        Override to expose a distinct service object.
        """
        return {cap: self for cap in self.provides}


# ══════════════════════════════════════════════════════════════════════════════
# Host — the seam interface
# ══════════════════════════════════════════════════════════════════════════════

class Host(ABC):
    """Async plugin host: event bus + capability registry + hot-load lifecycle.

    This is the only surface the self-improvement loop depends on. Implementations
    may be backed by FORGE, a native bus, or (later) a real Orion.
    """

    @abstractmethod
    async def register_plugin(self, plugin: Any) -> None:
        """Bind, start, and register a plugin's capabilities + event handlers (hot-load)."""

    @abstractmethod
    async def get_capability(self, name: str) -> Any:
        """Resolve a registered capability by name, or None."""

    @abstractmethod
    def has_capability(self, name: str) -> bool:
        ...

    @abstractmethod
    async def emit(self, topic: str, data: Optional[Dict[str, Any]] = None, **kw: Any) -> None:
        """Emit an event. Accepts Orion's positional-dict style and/or kwargs."""

    @abstractmethod
    async def unload_capability(self, name: str) -> bool:
        """Hot-unload the plugin providing `name` (calls on_stop, drops subscriptions)."""

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable, *, wants_event: bool = False) -> None:
        ...

    @property
    @abstractmethod
    def capabilities_available(self) -> List[str]:
        ...


# ══════════════════════════════════════════════════════════════════════════════
# ForgeHost — Host backed by OPERADUM's FORGE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class _Subscription:
    topic: str
    handler: Callable
    wants_event: bool
    is_async: bool
    priority: int = 10


class ForgeHost(Host):
    """A `Host` backed by OPERADUM's FORGE (or an equivalent native bus).

    FORGE owns the synchronous, kwargs-shaped bus used by native FORGE plugins;
    ForgeHost layers async + `Event`-object delivery on top for Orion-style
    plugins, and tracks per-plugin capabilities/subscriptions so they can be
    hot-unloaded.
    """

    def __init__(self, forge: Any = None, name: str = "kompos-host"):
        ForgeCls, EventBusCls = _load_forge()
        if forge is not None:
            self._forge = forge
        elif ForgeCls is not None:
            self._forge = ForgeCls(name=name)
        else:
            self._forge = None
            self._bus = EventBusCls() if EventBusCls else _NativeBus()
        if self._forge is not None:
            self._bus = self._forge.bus
        self.name = name
        self._caps: Dict[str, Any] = {}
        # capability name -> owning plugin (for unload)
        self._cap_owner: Dict[str, Any] = {}
        # plugin id -> list of (topic, wrapped_handler) registered on the bus
        self._plugin_subs: Dict[int, List[Tuple[str, Callable]]] = {}
        # our async/event subscriptions, separate from the sync kwargs bus
        self._async_subs: Dict[str, List[_Subscription]] = {}

    @property
    def backend(self) -> str:
        return "forge" if self._forge is not None else "native"

    # ---------------- capabilities ----------------

    async def get_capability(self, name: str) -> Any:
        return self._caps.get(name)

    def has_capability(self, name: str) -> bool:
        return name in self._caps

    @property
    def capabilities_available(self) -> List[str]:
        return list(self._caps.keys())

    def _register_capability(self, name: str, service: Any, owner: Any) -> None:
        self._caps[name] = service
        self._cap_owner[name] = owner
        if self._forge is not None:
            # Share with FORGE so native FORGE plugins can resolve it too.
            self._forge._caps[name] = service

    # ---------------- events ----------------

    def subscribe(self, topic: str, handler: Callable, *, wants_event: bool = False) -> None:
        is_async = inspect.iscoroutinefunction(handler)
        if wants_event:
            self._async_subs.setdefault(topic, []).append(
                _Subscription(topic, handler, True, is_async)
            )
        else:
            # plain kwargs subscriber -> the FORGE/native bus
            self._bus.subscribe(topic, handler)

    async def emit(self, topic: str, data: Optional[Dict[str, Any]] = None, **kw: Any) -> None:
        payload: Dict[str, Any] = {}
        if isinstance(data, dict):
            payload.update(data)
        elif data is not None:
            payload["value"] = data
        payload.update(kw)

        # 1. sync kwargs subscribers (native FORGE plugins) via the FORGE bus.
        try:
            self._bus.emit(topic, **payload)
        except TypeError:
            # a native handler with an incompatible signature — don't fail the emit
            logger.debug("native bus handler signature mismatch on %s", topic)

        # 2. our async / Event-object subscribers, hooks first (by priority).
        subs = sorted(
            self._async_subs.get(topic, []),
            key=lambda s: s.priority,
        )
        for sub in list(subs):
            evt = Event(topic, dict(payload))
            try:
                result = sub.handler(evt)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # a misbehaving subscriber must not break the loop
                logger.exception("subscriber for %s raised", topic)

    # ---------------- lifecycle / hot-load ----------------

    async def register_plugin(self, plugin: Any) -> None:
        """Hot-load a plugin: bind → on_start → register capabilities + @on handlers."""
        if hasattr(plugin, "bind"):
            try:
                plugin.bind(self)
            except Exception:
                logger.debug("plugin.bind failed; continuing", exc_info=True)
        else:
            setattr(plugin, "core", self)

        # start
        start = getattr(plugin, "on_start", None)
        if callable(start):
            res = start()
            if inspect.isawaitable(res):
                await res

        # wire @on / @hook handlers
        subs: List[Tuple[str, Callable]] = []
        for _, member in inspect.getmembers(plugin, predicate=callable):
            meta = getattr(member, "_kompos_subscribe", None)
            if meta is None:
                continue
            topic, kind = meta
            priority = getattr(member, "_kompos_priority", 10)
            is_async = inspect.iscoroutinefunction(member)
            sub = _Subscription(topic, member, True, is_async, priority)
            self._async_subs.setdefault(topic, []).append(sub)
            subs.append((topic, member))
        self._plugin_subs[id(plugin)] = subs

        # register capabilities
        caps = {}
        getter = getattr(plugin, "capabilities", None)
        if callable(getter):
            try:
                caps = getter() or {}
            except Exception:
                caps = {}
        if not caps:
            provides = getattr(plugin, "provides", None) or []
            caps = {name: plugin for name in provides}
        for cap_name, service in caps.items():
            self._register_capability(cap_name, service, plugin)

        await self.emit(
            "plugin.started",
            plugin=getattr(plugin, "name", repr(plugin)),
            provides=list(caps.keys()),
        )

    async def unload_capability(self, name: str) -> bool:
        owner = self._cap_owner.get(name)
        if owner is None:
            return False
        # stop the owner
        stop = getattr(owner, "on_stop", None)
        if callable(stop):
            res = stop()
            if inspect.isawaitable(res):
                await res
        # drop every capability owned by it
        owned = [c for c, o in self._cap_owner.items() if o is owner]
        for cap in owned:
            self._caps.pop(cap, None)
            self._cap_owner.pop(cap, None)
            if self._forge is not None:
                self._forge._caps.pop(cap, None)
        # drop its subscriptions
        for topic, handler in self._plugin_subs.pop(id(owner), []):
            lst = self._async_subs.get(topic, [])
            self._async_subs[topic] = [s for s in lst if s.handler is not handler]
        await self.emit("capability.unloaded", capability=name,
                        plugin=getattr(owner, "name", repr(owner)))
        return True


# ══════════════════════════════════════════════════════════════════════════════
# Native fallback bus (only used if FORGE's EventBus is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

class _NativeBus:
    """Minimal sync kwargs bus matching the subset of operadum.forge.EventBus we use."""

    def __init__(self):
        self._subs: Dict[str, List[Callable]] = {}

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def emit(self, topic: str, **data: Any) -> None:
        for handler in list(self._subs.get(topic, [])):
            handler(**data)


# ══════════════════════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════════════════════

def build_host(name: str = "kompos-host") -> Host:
    """Construct the default host for the self-improvement loop.

    Returns a `ForgeHost` backed by OPERADUM's real FORGE when importable, else a
    `ForgeHost` over a native bus. Both satisfy the `Host` interface, so the rest
    of the loop is agnostic to which one it got.
    """
    return ForgeHost(name=name)


__all__ = [
    "Host", "ForgeHost", "Plugin", "Event", "on", "hook", "build_host",
]
