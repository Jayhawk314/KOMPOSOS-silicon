# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
STA ground-truth ingestion — EDA timing evidence with explicit provenance.

OpenSTA / OpenROAD `report_checks` emits, per path, a Startpoint, an Endpoint, the
pins traversed, and a slack (negative = a timing violation). This module parses that
report and preserves its source identity so fixtures cannot masquerade as evidence:

  - per-endpoint worst slack            -> `measured` timing claims (top evidence tier)
  - per-net timing criticality          -> ground truth to validate structural triage:
                                           do the congested nets sit on the slow paths?

The committed fixture validates grammar and plumbing only. It is never promoted to a
`measured` ledger claim. In this project, a real design-matched STA report is top-tier
EDA workflow evidence, not a lab measurement of fabricated silicon.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


FIXTURE_MARKER = "KOMPOSOS-V silicon STA fixture"
REQUIRED_CONTEXT = ("netlist", "liberty", "constraints")


@dataclass
class TimingPath:
    startpoint: str
    endpoint: str
    slack: float
    pins: List[Tuple[str, str]] = field(default_factory=list)   # (inst, pin) traversed

    @property
    def violated(self) -> bool:
        return self.slack < 0


@dataclass(frozen=True)
class ArtifactReceipt:
    path: str
    sha256: str

    def to_dict(self) -> Dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class TimingReport:
    """Parsed paths plus enough source identity to enforce evidence policy."""

    paths: List[TimingPath]
    source_path: str
    source_kind: str              # `tool`, `fixture`, or `unverified`
    sha256: str
    tool: str = "OpenSTA/OpenROAD report_checks"
    context: Dict[str, ArtifactReceipt] = field(default_factory=dict)

    @property
    def missing_context(self) -> List[str]:
        return [name for name in REQUIRED_CONTEXT if name not in self.context]

    @property
    def is_evidence(self) -> bool:
        return self.source_kind == "tool" and not self.missing_context

    def provenance(self) -> Dict[str, object]:
        return {
            "path": self.source_path,
            "kind": self.source_kind,
            "sha256": self.sha256,
            "tool": self.tool,
            "evidence_eligible": self.is_evidence,
            "missing_context": self.missing_context,
            "context": {name: receipt.to_dict()
                        for name, receipt in sorted(self.context.items())},
        }


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def _slack(block: str) -> float | None:
    """Accept both common OpenSTA and legacy fixture slack layouts."""
    after = re.search(
        rf"\bslack\s*(?:\([^)]*\))?\s*({_NUMBER})", block, re.IGNORECASE)
    if after:
        return float(after.group(1))
    before = re.search(rf"({_NUMBER})\s+slack\b", block, re.IGNORECASE)
    return float(before.group(1)) if before else None


def parse_sta(text: str) -> List[TimingPath]:
    """Parse OpenSTA/OpenROAD `report_checks` into timing paths."""
    paths: List[TimingPath] = []
    # split into per-path blocks at each Startpoint:
    blocks = re.split(r"(?=^\s*Startpoint:)", text, flags=re.MULTILINE)
    for blk in blocks:
        sm = re.search(r"Startpoint:\s+(\S+)", blk)
        em = re.search(r"Endpoint:\s+(\S+)", blk)
        slack = _slack(blk)
        if not (sm and em) or slack is None:
            continue
        # Greedy instance group preserves hierarchical names such as core/u1/A.
        pins = [(i, p) for i, p in re.findall(
            r"\b([\w$\\.\[\]/]+)/([\w$\\.\[\]]+)\s+\(", blk)]
        paths.append(TimingPath(sm.group(1), em.group(1), slack, pins))
    return paths


def _receipt(path: str | Path) -> ArtifactReceipt:
    p = Path(path).resolve()
    raw = p.read_bytes()
    return ArtifactReceipt(str(p), hashlib.sha256(raw).hexdigest())


def load_sta(path: str | Path, source_kind: str = "unverified",
             context_paths: Optional[Dict[str, str | Path]] = None,
             tool: str = "OpenSTA/OpenROAD report_checks") -> TimingReport:
    """Load and hash a report; measured eligibility requires explicit attestation.

    The known fixture marker always wins and cannot be overridden. Other reports are
    `unverified` by default; callers must explicitly pass `source_kind="tool"` after
    establishing that the artifact came from the stated EDA flow.
    """
    if source_kind not in {"tool", "unverified"}:
        raise ValueError("source_kind must be 'tool' or 'unverified'")
    p = Path(path).resolve()
    raw = p.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    resolved_kind = "fixture" if FIXTURE_MARKER in text else source_kind
    context = {name: _receipt(context_path)
               for name, context_path in (context_paths or {}).items()
               if context_path is not None}
    return TimingReport(
        paths=parse_sta(text),
        source_path=str(p),
        source_kind=resolved_kind,
        sha256=hashlib.sha256(raw).hexdigest(),
        tool=tool,
        context=context,
    )


def worst_slack(paths: List[TimingPath]) -> float:
    return min((p.slack for p in paths), default=0.0)


def violating_endpoints(paths: List[TimingPath]) -> List[Tuple[str, float]]:
    """Endpoints with negative slack, worst first (real timing violations)."""
    worst: Dict[str, float] = {}
    for p in paths:
        if p.violated:
            worst[p.endpoint] = min(worst.get(p.endpoint, 0.0), p.slack)
    return sorted(worst.items(), key=lambda kv: kv[1])


def critical_nets(paths: List[TimingPath], bridge,
                  signal_only: bool = True) -> Dict[str, float]:
    """Map each timing path onto the nets it traverses; return {net: criticality}.

    criticality = max(-slack) over violating paths through the net (>=0; 0 = not on a
    violating path). Pin->net mapping uses the bridge's DEF connectivity.
    """
    allowed = ({net.name for net in bridge.signal_nets} if signal_only else None)
    pin_net: Dict[Tuple[str, str], str] = {}
    for net in bridge.nets:
        if allowed is not None and net.name not in allowed:
            continue
        for conn in net.conns:
            pin_net[conn] = net.name

    crit: Dict[str, float] = {}
    for p in paths:
        if not p.violated:
            continue
        sev = -p.slack
        for conn in p.pins:
            net = pin_net.get(conn)
            if net is not None:
                crit[net] = max(crit.get(net, 0.0), sev)
    return crit
