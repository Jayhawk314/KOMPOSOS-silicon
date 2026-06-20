# Real OpenSTA `report_checks` reproducer (measured-tier timing evidence)

These TCL flows run **real OpenSTA** on the `gcd_sky130hd` design bundled inside the
`openroad/opensta` Docker image, producing genuine `report_checks` output that the
silicon STA pipeline (`domains/silicon/sta.py`) ingests as **`measured`-tier** evidence.

The report `.txt` outputs and staged design files live under
`domains/silicon/data/sta_gcd/` (gitignored, regenerable). These flows + this README
are the committed, reproducible record.

## Run it

```bash
docker pull openroad/opensta:latest            # OpenSTA 2.6.2 (verified 2026-06-20)

OUT="$PWD/domains/silicon/data/sta_gcd"
mkdir -p "$OUT"
cp domains/silicon/sta_flows/*.tcl "$OUT"/

# Stage the bundled design out of the image, then run both flows.
MSYS_NO_PATHCONV=1 docker run --rm -v "$OUT:/work" --entrypoint sh openroad/opensta:latest -c '
  cp /OpenSTA/examples/gcd_sky130hd.v /OpenSTA/examples/gcd_sky130hd.sdc \
     /OpenSTA/examples/sky130hd_tt.lib.gz /OpenSTA/examples/gcd_sky130hd.spef /work/
  /OpenSTA/app/sta -no_init -exit /work/gcd_sky130hd.tcl       > /work/gcd_sky130hd.report_checks.txt
  /OpenSTA/app/sta -no_init -exit /work/gcd_sky130hd_tight.tcl > /work/gcd_sky130hd.tight.report_checks.txt
'
```

Note: `sta` is not on PATH inside the image; invoke it as `/OpenSTA/app/sta`
(the image entrypoint). `MSYS_NO_PATHCONV=1` stops Git Bash mangling `/work`.

## Ingest

```bash
python -m domains.silicon.agent_tools \
  --sta domains/silicon/data/sta_gcd/gcd_sky130hd.report_checks.txt \
  --sta-source tool \
  --sta-netlist domains/silicon/data/sta_gcd/gcd_sky130hd.v \
  --sta-liberty domains/silicon/data/sta_gcd/sky130hd_tt.lib.gz \
  --sta-sdc     domains/silicon/data/sta_gcd/gcd_sky130hd.sdc \
  sta
```

→ `"status": "measured"`, `evidence_eligible: true`, with hashed receipts for the
report, netlist, Liberty, and SDC.

## Results (OpenSTA 2.6.2, 2026-06-20)

| Flow | Clock | Worst slack | Violating endpoints | Verdict |
|---|---|---:|---:|---|
| `gcd_sky130hd.tcl`       | 5 ns (period) | **+0.0648 ns** | 0 / 53  | meets timing |
| `gcd_sky130hd_tight.tcl` | 1 ns (5× tighter) | **−3.9352 ns** | 52 / 53 | real violations |

Both reports parse to 53 timing paths and qualify as `measured` evidence.

### Artifact hashes (sha256)

```
21e8fbef…1af1e  gcd_sky130hd.report_checks.txt        (relaxed, meets)
8f4453b0…477c65  gcd_sky130hd.tight.report_checks.txt  (tight, 52 violations)
923acdd2…44067   gcd_sky130hd.v        (gate netlist)
210e56be…a5889   sky130hd_tt.lib.gz    (Liberty, typical corner)
d0551fcb…61a69   gcd_sky130hd.sdc      (constraints)
775b5110…9135b   gcd_sky130hd.spef     (parasitics)
```

## Matched cross-mapping scoreboard — `45_gcd` (OpenROAD STA on our own DEF)

The `gcd_sky130hd` run above populates the measured tier but ships **no DEF**, so its
critical nets can't be mapped onto a layout we hold. To run the actual
structural-triage-vs-real-timing scoreboard we need a design where we hold **both** a
DEF and a matched `report_checks`. We get that by running **OpenROAD STA directly on a
DEF we already have** (`45_gcd.def`, a placed Nangate45 gcd): the report's instance
names are then *identical by construction* to what `netlist_bridge` parses from the same
DEF, so `critical_nets()` maps report → layout with zero name guesswork.

```bash
docker pull openroad/orfs:latest    # OpenROAD 26Q2 (binary at
                                    # /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad)
OUT="$PWD/domains/silicon/data/sta_45gcd"; mkdir -p "$OUT"
cp domains/silicon/data/openlane/Nangate45.lef "$OUT"/
cp domains/silicon/data/openlane/45_gcd.def    "$OUT"/
cp domains/silicon/data/openlane/45_gcd.spefok "$OUT"/45_gcd.spef
cp domains/silicon/sta_flows/45_gcd_openroad_sta.tcl domains/silicon/sta_flows/45_gcd.sdc "$OUT"/
# nangate45 Liberty comes from the opensta image:
docker run --rm -v "$OUT:/out" --entrypoint sh openroad/opensta:latest \
  -c 'cp /OpenSTA/examples/nangate45_typ.lib.gz /out/'
# run STA on the DEF (NOTE: do NOT source env.sh — it exits the shell; call the binary directly):
MSYS_NO_PATHCONV=1 docker run --rm -v "$OUT:/work" \
  --entrypoint /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad \
  openroad/orfs:latest -no_init -exit /work/45_gcd_openroad_sta.tcl \
  > "$OUT/45_gcd.report_checks.txt" 2> "$OUT/45_gcd.sta.log"

# score: structural predictors vs real per-net negative slack
python -m domains.silicon.agent_tools \
  --def $OUT/45_gcd.def --spef $OUT/45_gcd.spef --lef $OUT/Nangate45.lef \
  --sta $OUT/45_gcd.report_checks.txt --sta-source tool \
  --sta-netlist $OUT/45_gcd.def --sta-liberty $OUT/nangate45_typ.lib.gz --sta-sdc $OUT/45_gcd.sdc \
  score
```

### Result (OpenROAD 26Q2, clock 0.3 ns, 2026-06-20)

`sta`: 53 paths, **48 violating endpoints**, worst slack **−0.7169 ns**, `status:
measured`; **106 critical nets mapped onto DEF nets** (real cross-mapping, e.g.
`dpath.a_lt_b$in1[1]`).

`score` vs `sta_negative_slack` (308 nets, 106 on violating paths) — **PASS**, shuffle
control +0.020:

| Predictor | Spearman ρ |
|---|---:|
| **driver_area** | **+0.343** |
| sink_area | +0.246 |
| neg_curvature | +0.160 |
| degree | +0.111 |
| fanout | −0.037 |
| wirelength | −0.003 |

**Honest reading:**
- The signal is **real but modest** (best ρ +0.34, control +0.02). `prec@10 ≈ 0` for all
  predictors: there is a monotone rank trend, but the structural signals do **not**
  pinpoint the sharpest top-10 critical nets.
- **`driver_area` is partly circular** — synthesis upsizes drivers *on* critical paths,
  so cell drive-strength is partly an *output* of timing optimization, not a pure
  a-priori topological feature. The cleanest purely-structural signal is
  **`neg_curvature` (+0.16)**.
- **`fanout` predicts capacitance, not timing.** In the earlier SPEF scoreboard fanout
  was the *strongest* predictor of SPEF capacitance (≈+0.57); here it is ≈0 vs timing
  criticality. Load and timing-criticality are genuinely different targets — a useful,
  falsified-the-naive-expectation result.

### Artifact hashes (sha256)

```
d2be5422…b0b83  45_gcd.report_checks.txt   (OpenROAD STA, 48 violations)
0d1f1110…ac7803  45_gcd.def                 (netlist / placement context)
7ee6c11d…00f7ef  nangate45_typ.lib.gz       (Liberty)
9e27a687…db60a4  45_gcd.sdc                 (constraints, 0.3 ns clock)
264512161…d5683c  45_gcd.spef                (parasitics)
caa4e9b4…d43a7   Nangate45.lef              (tech+cell LEF)
```

## Self-minted layout — full ORFS RTL→GDSII flow (`orfs_gcd`)

The two runs above use layouts we *downloaded*. This one we **mint ourselves**: the full
open RTL→GDSII flow (Yosys synth → floorplan → place → CTS → route → finish) on
`gcd_nangate45`, the project's long-deferred "mint our own layout" capability (the
plan's "EIA-930 download" equivalent), now unblocked since Docker/OpenROAD work.

```bash
docker pull openroad/orfs:latest    # OpenROAD 26Q2 + Yosys 0.64, bundles nangate45 platform
OUT="$PWD/domains/silicon/data/orfs_gcd"; mkdir -p "$OUT"
# run the flow (NOTE: env.sh works under bash -l, NOT sh; it sets PATH for openroad/yosys)
docker run --rm -v "$OUT:/work" --entrypoint bash openroad/orfs:latest -lc '
  source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1
  cd /OpenROAD-flow-scripts/flow
  make DESIGN_CONFIG=designs/nangate45/gcd/config.mk
  cp -r results/nangate45/gcd/* /work/results/  # 6_final.def/.v/.spef/.sdc/.gds + odb
  cp -r reports/nangate45/gcd/* /work/reports/'
# then STA on the self-minted, routed layout (see orfs_gcd_sta.tcl) and score it:
cp domains/silicon/sta_flows/orfs_gcd.sdc domains/silicon/sta_flows/orfs_gcd_sta.tcl "$OUT"/
docker run --rm -v "$OUT:/work" --entrypoint bash openroad/orfs:latest -lc '
  source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1
  cp /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib /work/
  openroad -no_init -exit /work/orfs_gcd_sta.tcl > /work/6_final.report_checks.txt'

python -m domains.silicon.agent_tools \
  --def $OUT/results/base/6_final.def --spef $OUT/results/base/6_final.spef \
  --lef domains/silicon/data/openlane/Nangate45.lef \
  --sta $OUT/6_final.report_checks.txt --sta-source tool \
  --sta-netlist $OUT/results/base/6_final.v \
  --sta-liberty $OUT/NangateOpenCellLibrary_typical.lib --sta-sdc $OUT/orfs_gcd.sdc \
  score
```

### Result (OpenROAD 26Q2, self-minted, clock 0.40 ns, 2026-06-20) — the scoreboard FAILS

Self-minted gcd: 1065 placed+routed cells; the flow met timing at 0.46 ns *at the edge*
(worst slack +0.01 ns, fmax 2254 MHz). At a tightened 0.40 ns: 42/53 violating
endpoints, **177 critical nets mapped**, `status: measured`. But the violating slacks
are **tightly clustered** — worst −0.0396 ns, all within [−0.040, −0.009], **stdev
0.010 ns**. `score` vs `sta_negative_slack` (621 nets): **FAIL**, every predictor
|ρ|<0.15 (best `sink_area` +0.061, shuffle −0.019).

| Predictor | neg_curvature | degree | fanout | wirelength | driver_area | sink_area |
|---|---:|---:|---:|---:|---:|---:|
| ρ | −0.100 | −0.066 | −0.141 | +0.021 | +0.016 | +0.061 |

**Why this matters (the honest, important finding):** timing-driven place/route/resize
**deliberately equalizes slack** across paths — that is what convergence *means*. On a
cleanly optimized design the criticality variance collapses (stdev 0.010 ns), so there
is no structural signal left for a cheap predictor to exploit. The +0.34 we saw on the
downloaded `45_gcd` held because that layout was *less* slack-balanced. So:
**structural triage predicts timing criticality only on un-converged layouts; on a
fully optimized one it is falsified.** This is exactly why the architecture forbids a
proposal from standing in for a verdict — here the structural proposal would have
over-claimed, and the measured STA receipt caught it. The receipt earned its keep.

### Artifact hashes (sha256)

```
37c22362…410ccb  6_final.report_checks.txt   (OpenROAD STA, self-minted, 42 violations)
a01f4463…0f6601  6_final.def                  (self-minted routed layout)
0f9971dd…7902e   6_final.v                    (self-minted gate netlist)
19c1add7…c244ed  6_final.spef                 (self-minted parasitics)
8d540a4d…4e9b1   NangateOpenCellLibrary_typical.lib  (platform Liberty used)
4a935f17…61bf57  orfs_gcd.sdc                 (constraints, 0.40 ns clock)
```

## Honest boundary

This is **EDA-workflow ground truth** (real tool output with full, hashed design
context), not a lab measurement of fabricated silicon. All three designs are real and
fully attested. Together they give the honest verdict the project was built to test:
structural triage shows a **modest** correlation with measured timing on a less-balanced
layout (`45_gcd`, driver_area +0.34) and is **falsified** on a cleanly optimized one
(`orfs_gcd`, all |ρ|<0.15) — because timing-driven optimization erases the structural
signal. Measured verification is what distinguishes the two cases.
