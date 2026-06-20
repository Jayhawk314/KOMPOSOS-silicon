# KOMPOSOS‑V

A self‑improving, **honest‑by‑construction** reasoning engine built on category
theory. The bet: **structure substitutes for scale.** Instead of a large model,
KOMPOSOS‑V composes six small categorical engines so that every capability it
keeps is *built, executed, verified, grounded, and measured* — each one comes
with a checkable receipt you can trust without trusting the system.

This is the **integration repo**: the first place all six engines live together,
over one shared `Category`.

> **Docs:** `docs/SILICON_PLAN.md` (the active project) · `CLAUDE.md` (working rules
> & invariants) · `MEMORY.md` (decisions & state) · `docs/SESSIONS.md` (work log).

## What we're building now: silicon co‑design

The substrate has a chosen vertical — **semiconductor co‑design** (`domains/silicon/`).
It takes a chip's *materials* and its *layout/netlist*, runs categorical + sheaf +
flow‑geometry analysis over them, and emits an **honest, receipt‑backed waste ledger
and action portfolio** — never a hollow claim, all on a laptop, offline after data
download.

It's mostly **integration, not invention**: a working semiconductor material engine
already exists in `KOMPOSOS-IV-CHEM` (5 scorers, heterostructure analysis, an inverse
"Crystal Dreamer" designer), and the full analysis pipeline pattern (sheaf coherence
→ Ricci/Fiedler flow geometry → tiered waste ledger → local‑agent CLI) already exists
in `KOMPOSOS-GRID`. We port both onto this substrate; the one genuinely new piece is a
`netlist_bridge` that turns real chip layout (DEF/SPEF/netlist) into a `Category`.

**Read `docs/SILICON_PLAN.md` for the data sources, roadmap, and target layout.**

---

## The six engines

| Engine | Where | Verb | One line |
|---|---|---|---|
| **KOMPOSOS** | `core/`, `oracle/`, `categorical/` | interpret | enriched category: stores relations, verifies, factors |
| **OPERADUM** | `operadum/` | construct | coloured operad: synthesizes artifacts satisfying a spec |
| **PRONOIA** | `operadum/pronoia/` | predict | non‑LLM stack: VSA→sheaf→MDL→SCM→Tsetlin→**honesty** |
| **COG** | `cog/` | judge | 5‑tier gate → AGREE / ORPHAN / HOLLOW / REJECT |
| **OPTIMUS** | `core/optimus.py`, `optimus_core.py` | self‑refine | categorical gradient descent over the graph |
| **komposos_kg** | `komposos_kg/` | remember | verified KG memory (write‑gate + honesty‑gate) |

Supporting math lives in `categorical/` (Kan extensions, operads, topos, Gray),
`topology/` (persistent homology/sheaves), `hott/` + `cubical/` (paths/identity),
`zfc/` (the logic narrator / dual engine), `geometry/`, and `game/`.

---

## The self‑improvement loop

`core/loop.py` runs one cycle over the shared `Category`:

```
OPTIMUS / ConjectureEngine   observe : surface structural gaps (missing edges)
OPERADUM                     design  : synthesize + type/resource‑verify a route
PRONOIA                      predict : rank routes by MDL gain + honesty grounding
ExecutableSynthesizer        ground  : build the composite, RUN it, verify coherence
HonestyGate                  remember: persist only if grounded in committed evidence
COG                          judge   : AGREE / ORPHAN / HOLLOW / REJECT
```

A kept edge is therefore a **function that was built, executed on real input,
checked for path‑coherence, grounded against existing evidence, and judged** —
not a claim. Anything that fails any gate is rolled back and removed.

```powershell
python -m core.loop                              # run the loop (optimus observer)
$env:KOMPOSOS_OBSERVER="conjecture"; python -m core.loop   # proactive observer
```

---

## Measurement: the scoreboard

`core/scoreboard.py` is a falsifiable benchmark: hide known edges, run the loop,
and score whether it recovers real structure **without inventing** edges that
shouldn't exist.

```powershell
python -m core.scoreboard                         # recall / precision / F1, PASS/FAIL
python -m core.scoreboard --observer conjecture --embeddings auto
```

Full structure scores 1.0 / 1.0 (PASS); remove a supporting edge and recall
drops to 0 (FAIL). The number tracks reality.

---

## The oracle (prediction organ)

`oracle/` holds the prediction strategies. The runtime registry is
`oracle.strategies.create_all_strategies(category, embeddings)` (**21 strategies**:
Kan, composition, horn‑filling, structural‑hole, Yoneda, topos, operadic,
geometric, conjecture‑gap, …). COG's Tier‑4 runs all of them; adding a strategy
there auto‑enrolls it. `CategoricalOracle` is the orchestrator
(strategies → merge → sheaf‑coherence → game‑select → learn).

---

## The continuous layer (embeddings)

`data/embeddings.py` is a real, dependency‑light backend: deterministic feature
hashing with a `fit(category)` **soft‑Yoneda** structural embedding (objects with
the same morphism profile land near each other). Optional `model=` upgrades to
sentence‑transformers. Embeddings are a **proposal‑side prior only** — they
propose candidate edges; the symbolic layer verifies. (See `CLAUDE.md`.)

---

## Quickstart

```powershell
pip install numpy            # core loop/oracle/scoreboard are numpy + stdlib
python -m core.loop          # watch the loop build & verify capabilities
python -m core.scoreboard    # measure it
python -m pytest tests/ -q   # 140 tests
```

`requirements.txt` also lists `streamlit`, `pandas`, and `esm` — these are only
needed for the optional UI and the protein/geometry heritage, not the core loop.

---

## Layout

| Path | Role |
|---|---|
| `core/` | shared `Category`, the loop, host, OPTIMUS, executable synthesis, honesty gate, scoreboard |
| `oracle/` | prediction strategies + `create_all_strategies` registry + `ConjectureEngine` |
| `categorical/` | Kan extensions, operads, topos, Gray categories — the engine room |
| `cog/` | the 5‑tier verdict engine |
| `operadum/` | OPERADUM (construct) + PRONOIA (predict, incl. honesty) — own sub‑package |
| `zfc/` | the logic narrator / dual engine |
| `topology/` `hott/` `cubical/` `geometry/` `game/` | supporting math |
| `data/` | embeddings backend + persistence helpers |
| `tests/` | 140 tests — laws and behaviour |

---

## Status

Core loop, oracle, embeddings, grounding, honesty gate, and scoreboard are real
and tested. The substrate's first serious vertical — **silicon co‑design**
(`domains/silicon/`) — is now built end‑to‑end at the synthetic/sample stage:

- **Rung 0** `synthetic.py` — Ricci congestion + Fiedler seam + coherence on a toy chip
- **Rung 1** `material_bridge.py` (+ `materials_data.py`, `scoring.py`) — 28 materials,
  5 scorers, heterostructure analysis, verdicts gated by **COG + HonestyGate**
- **Rung 2** `netlist_bridge.py` (+ `flow_geometry.py`) — real DEF/SPEF parsers,
  geometry on actual layout connectivity (committed sample; ready for OpenLane output)
- **Rung 3** `waste_ledger.py` + `agent_tools.py` — evidence‑tiered waste ledger,
  action portfolio, and a local‑agent CLI (`whatif --isolate <block>`)

Full suite **174 passing**. Next: the real OpenLane/SKY130 data download. See
`docs/SILICON_PLAN.md` (roadmap) and `docs/SESSIONS.md` (work log).

`domains/` also holds the earlier `circuits.py` (NAND→XOR self‑improvement demo) and
`numeric.py`.
