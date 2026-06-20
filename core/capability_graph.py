# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Capability Graph Builder (Ruliad Engine)

Constructs a Category from Orion's plugin metadata so categorical strategies
can analyze the system's own architecture.

What goes in the graph:
- Objects = plugins (capabilities)
- Morphisms = dependency edges (requires/provides)
- Co-occurrence morphisms from telemetry (weighted by frequency)
- Git co-modification morphisms (weighted by commit count)
- Error morphisms (weighted negatively)

This enables OPTIMUS to run on the system's own architecture,
finding wrong boundaries, missing primitives, and redundant capabilities.

Usage:
    builder = CapabilityGraphBuilder(orion_core, telemetry_category=telem_cat)
    cap_graph = await builder.build()
    builder.add_git_signals(git_comod)

    # Now run OPTIMUS on the capability graph
    engine = OptimusEngine(cap_graph)
    gaps = engine.find_structural_gaps()
    refinement = engine.refine(max_steps=20, depth=2)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .category import Category


class CapabilityGraphBuilder:
    """
    Build a Category representing the system's own architecture.

    This is the Ruliad Engine's self-observation mechanism: the system
    constructs a categorical model of itself, then uses OPTIMUS to
    find improvements.
    """

    def __init__(
        self,
        orion_core=None,
        telemetry_category: "Category" = None,
        category_factory=None,
    ):
        """
        Args:
            orion_core: Orion Core instance (for plugin enumeration).
            telemetry_category: Category with telemetry data (from TelemetryPlugin).
            category_factory: Callable that returns a fresh Category instance.
                              Defaults to creating Category(db_path=":memory:").
        """
        self.orion = orion_core
        self.telemetry = telemetry_category

        if category_factory:
            self.category_factory = category_factory
        else:
            from .category import Category
            self.category_factory = lambda: Category(db_path=":memory:")

        self.graph = self.category_factory()
        self._built = False

    async def build(self) -> "Category":
        """
        Snapshot current architecture as a Category.

        Returns:
            Category representing the system's capability graph.
        """
        # Objects = capabilities
        plugins = await self._get_plugins()
        for plugin in plugins:
            plugin_name = self._plugin_name(plugin)
            provides = self._plugin_provides(plugin)
            self.graph.add(plugin_name, type_name="capability",
                           metadata={"provides": list(provides)})

        # Morphisms = declared dependencies (requires -> provides)
        for plugin in plugins:
            plugin_name = self._plugin_name(plugin)
            requires = self._plugin_requires(plugin)
            for required in requires:
                # Find who provides this
                for other in plugins:
                    if required in self._plugin_provides(other):
                        provider_name = self._plugin_name(other)
                        self.graph.connect(
                            plugin_name, provider_name,
                            name=f"requires_{required}",
                            confidence=1.0,
                            metadata={"relation": "requires", "capability": required}
                        )

        # Morphisms from telemetry (co-occurrence, weighted)
        if self.telemetry:
            for mor in self.telemetry.morphisms():
                self.graph.connect(
                    mor.source, mor.target,
                    name=f"cooccurs_{mor.name}",
                    confidence=mor.confidence,
                    metadata={"relation": "co_occurrence"}
                )

        self._built = True
        return self.graph

    def add_git_signals(self, git_comod: dict):
        """
        Add git co-modification signals to the capability graph.

        Args:
            git_comod: {("plugin_a", "plugin_b"): commit_count}
        """
        max_count = max(git_comod.values()) if git_comod else 1
        for (a, b), count in git_comod.items():
            self.graph.connect(
                a, b,
                name=f"git_comod_{a}_{b}",
                confidence=count / max_count,
                relation="git_co_modification",
                commits=count,
            )

    def add_error_signals(self, error_data: List[Dict[str, Any]]):
        """
        Add error boundary signals to the capability graph.

        Args:
            error_data: List of {"source_plugin": str, "error": str, "count": int}
        """
        for err in error_data:
            source = err["source_plugin"]
            self.graph.connect(
                source, source,  # Self-loop for error concentration
                name=f"errors_{source}",
                confidence=min(err["count"] / 100, 0.99),  # Cap at 0.99
                metadata={
                    "relation": "error_boundary",
                    "error": err["error"],
                    "count": err["count"],
                }
            )

    def add_performance_signals(self, perf_data: Dict[str, float]):
        """
        Add performance latency signals.

        Args:
            perf_data: {"plugin_name": avg_latency_seconds}
        """
        max_latency = max(perf_data.values()) if perf_data else 1
        for plugin, latency in perf_data.items():
            if plugin in self.graph._objects:
                self.graph.add(plugin, metadata={
                    **self.graph._objects[plugin].metadata,
                    "avg_latency": latency,
                    "latency_normalized": latency / max_latency,
                })

    async def _get_plugins(self):
        """Get list of plugins from Orion core."""
        if self.orion is None:
            # Return empty list if no orion core provided
            return []
        return await self.orion.list()

    def _plugin_name(self, plugin) -> str:
        """Extract plugin name."""
        if hasattr(plugin, 'name'):
            return plugin.name
        return str(plugin)

    def _plugin_provides(self, plugin) -> list:
        """Extract what the plugin provides."""
        if hasattr(plugin, 'provides'):
            return plugin.provides if plugin.provides else []
        return []

    def _plugin_requires(self, plugin) -> list:
        """Extract what the plugin requires."""
        if hasattr(plugin, 'requires'):
            return plugin.requires if plugin.requires else []
        return []

    def summary(self) -> Dict[str, Any]:
        """Get summary of the capability graph."""
        if not self._built:
            return {"status": "not_built"}

        return {
            "capabilities": len(self.graph.objects()),
            "dependencies": len([
                m for m in self.graph.morphisms()
                if m.metadata.get("relation") == "requires"
            ]),
            "co_occurrences": len([
                m for m in self.graph.morphisms()
                if m.metadata.get("relation") == "co_occurrence"
            ]),
            "git_links": len([
                m for m in self.graph.morphisms()
                if m.metadata.get("relation") == "git_co_modification"
            ]),
            "error_links": len([
                m for m in self.graph.morphisms()
                if m.metadata.get("relation") == "error_boundary"
            ]),
        }
