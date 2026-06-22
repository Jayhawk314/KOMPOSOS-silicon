# Roadmap — from "claimed" to "delivered + seen"

Companion to `docs/VALUE.md`. Each item closes a gap that doc admits, or gets the value in
front of the right eyes. Recommended order: **1 → 4 → 5 → 2 → 6 → 3.**

## Part A — Make the value credible (close the admitted gaps)

- [x] **1. Light up the `measured` tier (the #1 credibility unlock).** ✅ DONE (2026-06-21)
  Ran real OpenROAD STA on **orfs_gcd** (`sta_flows/orfs_gcd_netdelay_sta.tcl`, Docker), ingested
  the tool's own per-net interconnect delay at the `measured` tier (attested `tool`, hashed
  netlist/Liberty/SDC receipt), and validated cheap structure against it: **wirelength ρ +0.845,
  fanout +0.709, control −0.05, 545 nets.** Now lit on TWO real designs (45_gcd +0.65, orfs_gcd
  +0.845). `tests/test_silicon_tau_scoreboard.py` guards it. *Remaining: IR-drop/power timing
  reports still proxy — same recipe extends them.*

- [x] **2. Show coherence on a REAL divergence (not "all clear").** ✅ DONE (2026-06-21)
  Ungated with data we already held: the ORFS intermediate netlists. `stage_coherence(synthesis,
  final)` runs the engine on two real flow stages of one design (logically equivalent per the
  flow's own LEC, structurally different). Result: **490/572 nets (86%) preserved with identical
  connectivity; the 137 divergent nets localize to the cells the flow inserted — `CLKBUF_X3`
  clock buffers, `BUF_X1/X2/X4` hold/fanout buffers.** `tests/test_silicon_fidelity_coherence.py`
  guards it. *Honest scope: this is structural what-changed localization between equivalent
  stages, not bug-finding; a true cross-tool fault still needs a design that contains one.*

- [ ] **3. Numeric cross-check the conflict finder vs OpenMPL.**
  We matched OpenMPL's conflict *rule*; we haven't matched its output *numbers*. Build OpenMPL,
  run its decomposer on the same metal, confirm our localized conflicts match.
  *Turns "same rule" → "same answer as the reference tool."*
  Effort: high — gated on a C++/Boost build.

## Part B — Make the value seen (the actual goal: eyes on the work)

- [x] **4. One clean entry point + a 3-minute README.** ✅ DONE (2026-06-21)
  `domains/silicon/api.py`: `analyze(def, spef, lef) -> SiliconReport` (triage + chiplet seam,
  evidence-tiered) with a CLI (`python -m domains.silicon.api <def>`). `domains/silicon/README.md`:
  3-minute front door — 30-second no-download demo on the committed sample, the measured +0.845
  result, the "disproved my own hypotheses" honesty hook. Root README points at it.
  `tests/test_silicon_api.py` (3, runs on the committed fixture).

- [x] **5. A short honest writeup / post — lead with the failures.** ✅ DONE (2026-06-21)
  `docs/WRITEUP.md` — a publishable first-person post that opens with the two disproved
  hypotheses (curvature is design-dependent per-net; timing slack isn't structurally
  predictable), then the verification-first idea, the measured +0.845 result, the coherence +
  trust-gate checks, honest boundaries, and the 30-second demo. Every claim tied to a run; the
  curvature claim corrected to match observed numbers (gcd +0.64 / 45_gcd +0.16). *Remaining:
  actually post it (that's #6).*

- [ ] **6. Aim it at the receptive audience.**
  Applied category theory (Topos / ACT), trustworthy/verifiable-AI ("safeguarded AI"), and the
  open-EDA (OpenROAD) community — people who notice and recommend. Value isn't "met" until the
  right person sees it. Effort: low; closes the loop on the goal.
