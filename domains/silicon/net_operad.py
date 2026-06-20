# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Colored-operad semantics for multi-pin silicon nets.

A DEF net is one n-ary relation over all of its terminals. It is not intrinsically a
collection of unrelated binary edges. The flow-geometry algorithms still require a
graph, so this module keeps the n-ary operation as the source of truth and exposes an
explicit driver-star projection for those algorithms.

When LEF identifies an OUTPUT pin, the projection is direction-aware and invariant to
DEF connection order. Without LEF, the operation remains canonical but the graph
projection is labeled `def_order_fallback`.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from categorical.operads import ColoredOperad, Operation


Terminal = Tuple[str, str, str, str]  # instance, pin, graph node, role


def net_operation(bridge, net) -> Operation:
    """Build one canonical n-ary operation for a parsed DEF net."""
    driver_index = bridge._driver_index(net)
    direction_source = bridge.driver_source(net)
    known_driver = direction_source == "lef_output"

    projection_inst, projection_pin = net.conns[driver_index]
    projection_node = bridge._node(projection_inst, projection_pin)
    terminals: List[Terminal] = []
    for index, (inst, pin) in enumerate(net.conns):
        role = "driver" if known_driver and index == driver_index else (
            "sink" if known_driver else "terminal")
        terminals.append((inst, pin, bridge._node(inst, pin), role))
    terminals.sort(key=lambda terminal: (terminal[0], terminal[1], terminal[2]))

    return Operation(
        name=f"net::{net.name}",
        arity=len(terminals),
        output_type="net_signal",
        input_types=[f"{terminal[3]}_signal" for terminal in terminals],
        data={
            "net": net.name,
            "use": net.use or "SIGNAL",
            "terminals": terminals,
            "driver": ((projection_inst, projection_pin, projection_node)
                       if known_driver else None),
            "projection_driver": (projection_inst, projection_pin, projection_node),
            "projection_assumption": direction_source,
            "cap_pf": bridge.caps.get(net.name),
        },
    )


def build_net_operad(bridge) -> ColoredOperad:
    """Build the colored operad of all signal nets accepted by a bridge."""
    operad = ColoredOperad(
        f"{bridge.name}_nets",
        colors={"terminal_signal", "driver_signal", "sink_signal", "net_signal"},
    )
    for net in sorted(bridge.signal_nets, key=lambda item: item.name):
        operad.add_operation(net_operation(bridge, net))
    return operad


def project_operation(operation: Operation) -> List[Tuple[str, str]]:
    """Project an n-ary net operation to driver->sink graph edges."""
    driver = operation.data["projection_driver"][2]
    sinks = sorted({terminal[2] for terminal in operation.data["terminals"]
                    if terminal[2] != driver})
    return [(driver, sink) for sink in sinks]


def arity_histogram(operad: ColoredOperad) -> Dict[int, int]:
    histogram: Dict[int, int] = {}
    for operation in operad.operations.values():
        histogram[operation.arity] = histogram.get(operation.arity, 0) + 1
    return dict(sorted(histogram.items()))
