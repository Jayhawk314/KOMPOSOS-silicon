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

## Honest boundary

This is **EDA-workflow ground truth** (real tool output with full, hashed design
context), not a lab measurement of fabricated silicon. Both designs above are real and
fully attested; the `45_gcd` run closes the structural-vs-real-timing cross-mapping the
project was built to test.
