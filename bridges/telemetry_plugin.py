# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Runtime Telemetry Collector (Ruliad Engine)

Tracks what capabilities actually do at runtime so the system can observe itself.

What to collect:
- Capability co-occurrence: which plugins fire together in workflows
- Error co-location: which plugin boundaries produce errors
- Performance traces: latency per plugin per workflow
- Event co-subscription: which plugins listen to the same events
- Composition frequency: which capability chains get used most

Key point: Store telemetry AS a Category. Then OPTIMUS and the
InfinityCosmos can operate on it directly.

Usage:
    telemetry = TelemetryPlugin(core, category=Category(db_path="telemetry.db"))
    # Automatically collects signals as plugins fire
    # Later: use telemetry.category as input to CapabilityGraphBuilder
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .category import Category

logger = logging.getLogger(__name__)


class TelemetryPlugin:
    """
    Collect runtime signals for architectural self-observation.

    This plugin intercepts all Orion events and records:
    - Which plugin handled what event
    - How long it took
    - Whether it produced errors
    - Which other plugins were active in the same time window

    All telemetry is stored AS a Category, making it available to
    OPTIMUS, InfinityCosmos, and the ArchitecturalAdvisor.
    """

    def __init__(
        self,
        core,
        category: "Category",
        name: str = "telemetry",
        window_size: float = 5.0,
    ):
        """
        Args:
            core: Orion Core instance.
            category: Category to store telemetry data.
            name: Plugin name.
            window_size: Time window (seconds) for co-occurrence tracking.
        """
        self.core = core
        self.category = category
        self.name = name
        self.window_size = window_size

        # Co-occurrence tracking: which plugins fire together
        self.co_occurrence: Dict[tuple, int] = defaultdict(int)
        self.error_log: List[Dict[str, Any]] = []
        self.latency_log: List[Dict[str, Any]] = []
        self.event_log: List[Dict[str, Any]] = []

        # Active plugin tracking within time windows
        self._active_plugins: Dict[str, float] = {}  # plugin_name -> last_active_time
        self._event_buffer: List[Dict[str, Any]] = []  # Recent events for co-occurrence

    async def on_start(self):
        """Plugin startup."""
        logger.info(f"TelemetryPlugin started (window={self.window_size}s)")

    async def on_stop(self):
        """Plugin shutdown - log final statistics."""
        logger.info(
            f"TelemetryPlugin stopping. "
            f"Events: {len(self.event_log)}, "
            f"Errors: {len(self.error_log)}, "
            f"Co-occurrences: {len(self.co_occurrence)}"
        )

    async def on_event(self, event):
        """
        Intercept all events for telemetry collection.

        This should be registered as a catch-all event handler.
        """
        plugin_name = event.data.get("_plugin", "unknown")
        event_name = event.name
        timestamp = time.time()

        # Track active plugins
        self._active_plugins[plugin_name] = timestamp

        # Clean up stale entries (outside window)
        cutoff = timestamp - self.window_size
        self._active_plugins = {
            k: v for k, v in self._active_plugins.items()
            if v > cutoff
        }

        # Record co-occurrences: all pairs of active plugins
        active = list(self._active_plugins.keys())
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                pair = tuple(sorted([a, b]))
                self.co_occurrence[pair] += 1

        # Store as morphism: plugin --handles--> event
        self.category.connect(
            plugin_name, event_name,
            name=f"handles_{plugin_name}_{event_name}",
            confidence=1.0,
            metadata={
                "latency": 0,  # Will be updated on completion
                "count": 1,
                "timestamp": timestamp,
            }
        )

        # Log the event
        self.event_log.append({
            "plugin": plugin_name,
            "event": event_name,
            "timestamp": timestamp,
        })

    async def on_error(self, event):
        """Record error boundaries."""
        self.error_log.append({
            "source_plugin": event.data.get("plugin", "unknown"),
            "error": str(event.data.get("error", "unknown")),
            "timestamp": time.time(),
        })

        # Store as error morphism
        plugin_name = event.data.get("plugin", "unknown")
        self.category.connect(
            plugin_name, f"error_{plugin_name}",
            name=f"error_{len(self.error_log)}",
            confidence=0.1,  # Low confidence = bad
            metadata={
                "relation": "error",
                "error": str(event.data.get("error", "unknown")),
            }
        )

    async def trace_latency(self, plugin_name: str, event_name: str, elapsed: float):
        """
        Record latency for a plugin handling an event.

        Call this from other plugins' handlers:
            start = time.monotonic()
            result = await self.do_work()
            elapsed = time.monotonic() - start
            await telemetry.trace_latency(self.name, event_name, elapsed)
        """
        self.latency_log.append({
            "plugin": plugin_name,
            "event": event_name,
            "latency": elapsed,
            "timestamp": time.time(),
        })

        # Update the morphism with latency info
        mor_name = f"handles_{plugin_name}_{event_name}"
        existing = self.category.get_morphism(f"{mor_name}:{plugin_name}->{event_name}")
        if existing:
            existing.metadata["latency"] = elapsed
            existing.metadata["count"] = existing.metadata.get("count", 0) + 1

        # Also connect plugin -> plugin with inverse latency as confidence
        # (faster = higher confidence)
        inv_latency = 1.0 / (1.0 + elapsed)
        self.category.connect(
            plugin_name, event_name,
            name=f"fast_{plugin_name}_{event_name}",
            confidence=inv_latency,
            metadata={"relation": "performance", "latency": elapsed},
        )

    def co_occurrence_matrix(self) -> Dict[str, Dict[str, int]]:
        """
        Which plugins fire together in the same workflow?

        Returns:
            {plugin_a: {plugin_b: count, ...}, ...}
        """
        matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for (a, b), count in self.co_occurrence.items():
            matrix[a][b] = count
            matrix[b][a] = count
        return dict(matrix)

    def error_boundaries(self) -> List[Dict[str, Any]]:
        """
        Which plugin boundaries produce the most errors?

        Returns:
            List of {"plugin": str, "error_count": int, "errors": [...]}
        """
        by_plugin: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"plugin": "", "error_count": 0, "errors": []}
        )
        for err in self.error_log:
            plugin = err["source_plugin"]
            by_plugin[plugin]["plugin"] = plugin
            by_plugin[plugin]["error_count"] += 1
            by_plugin[plugin]["errors"].append(err["error"])

        return sorted(by_plugin.values(), key=lambda x: -x["error_count"])

    def performance_summary(self) -> Dict[str, float]:
        """
        Average latency per plugin.

        Returns:
            {plugin_name: avg_latency_seconds}
        """
        by_plugin: Dict[str, List[float]] = defaultdict(list)
        for entry in self.latency_log:
            by_plugin[entry["plugin"]].append(entry["latency"])

        return {
            plugin: sum(latencies) / len(latencies)
            for plugin, latencies in by_plugin.items()
        }

    def top_co_occurrences(self, n: int = 20) -> List[Dict[str, Any]]:
        """
        Top N plugin co-occurrence pairs.

        Returns:
            List of {"plugin_a": str, "plugin_b": str, "count": int}
        """
        sorted_pairs = sorted(
            self.co_occurrence.items(), key=lambda x: -x[1]
        )[:n]
        return [
            {"plugin_a": a, "plugin_b": b, "count": count}
            for (a, b), count in sorted_pairs
        ]
