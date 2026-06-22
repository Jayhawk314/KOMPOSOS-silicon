# Silicon Tool Boundary

This note answers the "unused math" question from the handoff. ("Boundary" here means an
**import-discipline boundary** — which modules the validated tool path is allowed to pull in —
not a commercial product line. The goal is a useful, receipt-backed tool, not a company; see
`docs/VALUE.md`.)

## The validated tool path

The validated capability is the reliability co-design report:

```powershell
python -m domains.silicon.agent_tools --def <design>.def --spef <design>.spef --lef <cells.lef> reliability
```

That path is intentionally small:

- `reliability.py` assembles the report.
- `hotspot.py` ranks mature-node physical-stress tiles and EM-risk nets from parsed DEF/SPEF/LEF data.
- `codesign_loop.py` proves the proposed action's EM gain vs resistance cost.
- `interconnect.py` and `materials_grounding.py` provide cited metal facts and HonestyGate grounding.
- `trust_layer.py` and `ml_hotspot.py` are adjacent product proof points: a black-box proposal gate and a held-out learned proposer.

The import boundary is enforced by `tests/test_silicon_product_boundary.py`: importing the tool's entry points must not import the dormant substrate engines listed below.

## Dormant Relative To The Validated Path

These root folders remain part of the broader KOMPOSOS substrate, but they are not the source of the validated silicon reliability result:

| Path | Current role on the validated path |
|---|---|
| `oracle/` | Dormant for reliability. Do not use oracle strategies as verdicts. |
| `zfc/` | Dormant for reliability. No silicon claim currently needs proof narration. |
| `hott/`, `cubical/` | Dormant for reliability. No path/identity machinery is on the product path. |
| `game/` | Dormant for reliability. No power/timing/area open-game objective is validated yet. |
| `operadum/` / PRONOIA | Dormant for reliability. Only use if a verified before/after action earns a measured receipt. |
| `cog/` | Used by older material-verdict tests, not by the product report. |
| `topology/` | Used by cross-artifact cohomology experiments, not by the reliability report. |
| `geometry/` | Used by corridor/partition/scoreboard tools, not imported by the reliability report. |
| `categorical/` | Used by n-ary net and tile/Kan tools, not imported by the reliability report. |
| `bridges/` | Substrate/plugin support, not part of the silicon tool path. |

## Rule

Do not bolt dormant engines onto the validated path for optics. Wire one in only when it:

1. answers a concrete silicon question,
2. can be checked against real tool output or cited physical data,
3. beats a simpler baseline or provides a necessary receipt,
4. keeps the evidence tier honest.

The current validated value is narrower and stronger: a mature-node reliability layer that finds IR/EM stress, connects it to cited materials actions, and proves the tradeoff with a receipt.
