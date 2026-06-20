# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Gate-level structural Verilog ingestion and DEF identity crosswalk."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


Endpoint = Tuple[str, str]


@dataclass
class VerilogInstance:
    name: str
    cell: str
    connections: Dict[str, str] = field(default_factory=dict)


@dataclass
class VerilogNetlist:
    module: str
    ports: Dict[str, str]
    nets: Set[str]
    instances: Dict[str, VerilogInstance]

    def endpoints_by_net(self) -> Dict[str, Set[Endpoint]]:
        endpoints: Dict[str, Set[Endpoint]] = {}
        for instance in self.instances.values():
            for pin, net in instance.connections.items():
                if _is_constant(net):
                    continue
                endpoints.setdefault(net, set()).add((instance.name, pin))
        for port in self.ports:
            if port in endpoints:
                endpoints[port].add(("PIN", port))
        return endpoints


@dataclass(frozen=True)
class NetIdentity:
    logical_net: str
    physical_net: str
    endpoints: Tuple[Endpoint, ...]

    @property
    def renamed(self) -> bool:
        return self.logical_net != self.physical_net


@dataclass
class NetlistCrosswalk:
    module: str
    matches: List[NetIdentity]
    logical_only: List[str]
    physical_only: List[str]
    missing_instances: List[str]
    extra_instances: List[str]
    cell_mismatches: List[Tuple[str, str, str]]

    @property
    def exact(self) -> bool:
        return not any((self.logical_only, self.physical_only,
                        self.missing_instances, self.extra_instances,
                        self.cell_mismatches))

    def to_dict(self) -> Dict[str, object]:
        return {
            "module": self.module,
            "exact": self.exact,
            "matched_nets": len(self.matches),
            "renamed_nets": sum(match.renamed for match in self.matches),
            "matches": [{"logical": match.logical_net,
                         "physical": match.physical_net,
                         "renamed": match.renamed,
                         "endpoints": list(match.endpoints)}
                        for match in self.matches],
            "logical_only": self.logical_only,
            "physical_only": self.physical_only,
            "missing_instances": self.missing_instances,
            "extra_instances": self.extra_instances,
            "cell_mismatches": [{"instance": inst, "logical": logical,
                                 "physical": physical}
                                for inst, logical, physical in self.cell_mismatches],
        }


def _clean_identifier(token: str) -> str:
    token = token.strip()
    return token[1:] if token.startswith("\\") else token


def _is_constant(expression: str) -> bool:
    return bool(re.match(r"^(?:\d+)?'[bBoOdDhH][0-9a-fA-FxXzZ_]+$", expression))


def _declaration_names(body: str) -> List[str]:
    body = re.sub(r"\[[^]]+\]", " ", body)
    body = re.sub(r"\b(?:wire|logic|reg|signed|unsigned)\b", " ", body)
    names = []
    for part in body.split(","):
        match = re.search(r"(\\\S+|[A-Za-z_$][\w$]*)\s*$", part.strip())
        if match:
            names.append(_clean_identifier(match.group(1)))
    return names


def parse_verilog(text: str) -> VerilogNetlist:
    """Parse structural gate-level Verilog with named instance connections."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\(\*.*?\*\)", "", text, flags=re.DOTALL)
    module_match = re.search(r"\bmodule\s+(\\\S+|[A-Za-z_$][\w$]*)", text)
    if not module_match:
        raise ValueError("No Verilog module declaration found")
    module = _clean_identifier(module_match.group(1))

    ports: Dict[str, str] = {}
    header = re.search(r"\bmodule\s+\S+\s*\((.*?)\)\s*;", text, re.DOTALL)
    current_direction = ""
    if header:
        for part in header.group(1).split(","):
            direction = re.search(r"\b(input|output|inout)\b", part)
            if direction:
                current_direction = direction.group(1)
            for name in _declaration_names(part):
                if current_direction:
                    ports[name] = current_direction

    nets: Set[str] = set(ports)
    for declaration in re.finditer(
            r"(?m)^\s*(input|output|inout|wire|logic)\b(.*?);", text):
        kind, body = declaration.group(1), declaration.group(2)
        for name in _declaration_names(body):
            nets.add(name)
            if kind in {"input", "output", "inout"}:
                ports[name] = kind

    instances: Dict[str, VerilogInstance] = {}
    reserved = {"module", "input", "output", "inout", "wire", "logic",
                "reg", "assign", "always", "endmodule"}
    pattern = re.compile(
        r"(?ms)^\s*([\\\w$]+)\s+(?:#\s*\(.*?\)\s*)?"
        r"([\\\w$]+)\s*\((.*?)\)\s*;")
    for match in pattern.finditer(text):
        cell, name, body = (_clean_identifier(match.group(i)) for i in (1, 2, 3))
        if cell in reserved:
            continue
        connections: Dict[str, str] = {}
        for connection in re.finditer(r"\.\s*(\\\S+|[\w$]+)\s*\(\s*([^()]*)\)", body):
            pin = _clean_identifier(connection.group(1))
            expression = re.sub(r"\s+", "", connection.group(2))
            if expression:
                connections[pin] = _clean_identifier(expression)
                nets.add(connections[pin])
        instances[name] = VerilogInstance(name, cell, connections)
    return VerilogNetlist(module, ports, nets, instances)


def load_verilog(path: str | Path) -> VerilogNetlist:
    return parse_verilog(Path(path).read_text(encoding="utf-8", errors="ignore"))


def build_crosswalk(logical: VerilogNetlist, bridge) -> NetlistCrosswalk:
    """Match logical and physical nets by terminal-set identity."""
    logical_endpoints = logical.endpoints_by_net()
    physical_endpoints = {
        net.name: set(net.conns) for net in bridge.signal_nets
    }
    physical_by_signature: Dict[frozenset, List[str]] = {}
    for name, endpoints in physical_endpoints.items():
        physical_by_signature.setdefault(frozenset(endpoints), []).append(name)

    matches: List[NetIdentity] = []
    used_physical: Set[str] = set()
    logical_only: List[str] = []
    for logical_name, endpoints in sorted(logical_endpoints.items()):
        candidates = [name for name in physical_by_signature.get(frozenset(endpoints), [])
                      if name not in used_physical]
        if not candidates:
            logical_only.append(logical_name)
            continue
        physical_name = sorted(candidates)[0]
        used_physical.add(physical_name)
        matches.append(NetIdentity(logical_name, physical_name,
                                   tuple(sorted(endpoints))))

    logical_instances = set(logical.instances)
    physical_instances = set(bridge.components)
    common = logical_instances & physical_instances
    cell_mismatches = sorted(
        (name, logical.instances[name].cell, bridge.components[name].cell)
        for name in common
        if logical.instances[name].cell != bridge.components[name].cell)
    return NetlistCrosswalk(
        module=logical.module,
        matches=matches,
        logical_only=logical_only,
        physical_only=sorted(set(physical_endpoints) - used_physical),
        missing_instances=sorted(logical_instances - physical_instances),
        extra_instances=sorted(physical_instances - logical_instances),
        cell_mismatches=cell_mismatches,
    )
