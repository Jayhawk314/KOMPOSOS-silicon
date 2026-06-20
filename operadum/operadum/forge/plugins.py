# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Forge Plugins -- the layers wired as capabilities

The OPERADUM layers exposed through Forge. Each is a thin Plugin that builds its
service in on_start and provides it as a capability. This is the spec's
architectural invariant #7 ("bridges are glue") made concrete:

  ComponentStorePlugin -> provides 'component_store'  (the Operad)
  WrightPlugin         -> provides 'synthesizer'      (requires component_store)
  DaedalusPlugin       -> provides 'search'           (requires component_store)
  PolytopePlugin       -> provides 'coherence'        (requires component_store)

Domain plugins remain *content* (operadum/domains) and are loaded into the
component store; these plugins are the *infrastructure* that operates on it.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from .plugin import Plugin
from ..core.operad import Operad
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from ..core.polytope import Polytope
from ..wright.engine import Wright
from ..daedalus_core import Daedalus


class ComponentStorePlugin(Plugin):
    """Provides the Operad (the component store) as a Forge capability."""

    name = "component_store"
    provides = ["component_store"]

    def __init__(self, store_name: str = "forge", monoid: ResourceMonoid = None):
        super().__init__()
        self.operad = Operad(store_name, monoid=monoid or ADDITIVE_COST)

    def capabilities(self) -> Dict[str, Any]:
        return {"component_store": self.operad}


class WrightPlugin(Plugin):
    """The synthesis write path. Requires a component store."""

    name = "wright"
    provides = ["synthesizer"]
    requires = ["component_store"]

    def __init__(self, max_depth: int = 6):
        super().__init__()
        self.max_depth = max_depth
        self.wright: Optional[Wright] = None

    def on_start(self) -> None:
        self.wright = Wright(self.capability("component_store"), max_depth=self.max_depth)

    def capabilities(self) -> Dict[str, Any]:
        return {"synthesizer": self.wright}


class DaedalusPlugin(Plugin):
    """Generative search. Requires a component store."""

    name = "daedalus"
    provides = ["search"]
    requires = ["component_store"]

    def __init__(self, max_depth: int = 8):
        super().__init__()
        self.max_depth = max_depth
        self.daedalus: Optional[Daedalus] = None

    def on_start(self) -> None:
        self.daedalus = Daedalus(self.capability("component_store"), max_depth=self.max_depth)

    def capabilities(self) -> Dict[str, Any]:
        return {"search": self.daedalus}


class PolytopePlugin(Plugin):
    """Higher coherence structure. Requires a component store."""

    name = "polytope"
    provides = ["coherence"]
    requires = ["component_store"]

    def __init__(self):
        super().__init__()
        self.polytope: Optional[Polytope] = None

    def on_start(self) -> None:
        self.polytope = Polytope(self.capability("component_store"))

    def capabilities(self) -> Dict[str, Any]:
        return {"coherence": self.polytope}
