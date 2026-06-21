# Math-folder inventory — READ FROM THE CODE, not docstrings

> Records what the CODE actually does (not the docstring), with an honest real/stub verdict,
> so the reading is not re-hand-waved each session. **Scope = the high-value files the user
> flagged, not all 60k lines** (user: "not every file will be useful, the ones I gave you
> above will help most").
>
> **Flagged set — COMPLETE, read in full (15 files):** hott/ (5), cubical/ (3), and the
> oracle coherence/horns/yoneda cluster (7): `horns.py`, `horns_retrodiction.py`,
> `horns_vs_composition.py`, `coherence.py`, `coherence_dial.py`, `coherence_specificity.py`,
> `yoneda_strategy.py`.
>
> **Headline:** the oracle cluster is **real, benchmarked, leak-controlled, and honest**
> (Tier A). The hott/cubical layer is a **faithful scaffold with stubbed computation** (Tier
> B) — its docstrings overclaim ("computational fillers") relative to the code.

## hott/ — 5 files, 1573 lines — READ IN FULL

| File | What the code actually does | Verdict |
|---|---|---|
| `identity.py` | `IdentityType`, `Path` (witness/provenance/**confidence∈[0,1]**, so enriched/fuzzy), `refl`/`sym`/`trans`(raises on endpoint mismatch)/`ap`, `PathOver` (dependent), `IdentitySystem` (registers paths, `compose_paths` through intermediates). | **Real but symbolic bookkeeping.** `IdentitySystem.are_equal` only checks whether a path object was registered (by `id()`), not a real equivalence decision. Composition/inversion are genuine. |
| `homotopy.py` | `PathHomotopyChecker`: shared **spine** = set-intersection of node-lists; union-find over **pairwise homotopy**; the "Einstein case" — a path through genuinely different content = DISTINCT, a same-spine-interval detour = HOMOTOPIC. | **Real working algorithm** (heuristic). The most usable HoTT file. Answers "are these multiple paths the same up to detours." |
| `geometric_homotopy.py` | `GeometricHomotopyChecker`: each node → curvature region (euclidean/spherical/hyperbolic) via `geometry.OllivierRicciCurvature.get_geometric_regions()`; path → geometry **signature** (simplified); compare by **Levenshtein**. | **Real — the genuine geometry↔homotopy bridge.** Two paths are geometrically homotopic iff same simplified geometry-signature. Falls back gracefully without geometry. |
| `path_induction.py` | `J`, `based_path_induction`, `transport`, `apd`, `path_rec`. | **Mostly STUB.** On `refl` they reduce correctly; on any non-trivial path `J`/`transport` return placeholder objects (`JResult`/`TransportResult`) — actual transport is **not computed**. |
| `__init__.py` | "Layer B" exports. | (re-exports) |

## cubical/ — 3 files, 844 lines — READ IN FULL

| File | What the code actually does | Verdict |
|---|---|---|
| `paths.py` | Faithful cubical **data model**: `PathType` (path as fn `I→A`, left/right/path_fn), `Square` (`I×I→A`, 4 boundaries + filler), `Cube`, `PartialElement` (defined faces = Kan input), `Interval`/`DimensionVar`/`Face`, `PathContext`. | **Structures faithful; interior content stubbed.** Interior eval = linear `_smooth_interp` (α=0.5) or symbolic string. The "curvature-aware interpolation" imports `geometry.ricci` but then explicitly falls back to linear. `find_path` uses `id()` keys. |
| `kan_ops.py` | `hcomp`, `hfill`, `comp`, `inv`, `transport`, `cong`, `fill_square`, `KanEngine`. | **Docstring OVERCLAIMS** ("actually compute fillers"). Reality: `hcomp` returns `wall.right`; `comp` interior returns `p.right` ("simplification"); `inv` "would need to flip t"; `transport` non-refl → symbolic `TransportedElement` ("would need to actually compute"). One real hook: `hfill`/`fill_square` interior → `core.hott_bridge._smooth_interp` (Ricci-aware) if present, else linear blend. |
| `__init__.py` | "Layer C" exports. | (re-exports) |

### Honest takeaway (hott + cubical)
- **Usable now:** homotopy-class detection (`homotopy.py`) and geometry-signature path comparison (`geometric_homotopy.py`). These are real algorithms.
- **Scaffold/stub:** the J-rule, Kan-filling, and transport-along-equivalence are tracked structurally but **not computed** for non-trivial paths. The "computational cubical engine" framing is aspirational relative to the code.
- **Implication for Track 3 coherence:** if EPE/DSA only needs "are these representations equivalent up to deformation," the homotopy/geometric-homotopy algorithms apply. If it needs real *transport* of guarantees along an equivalence, that computation must be built (or wired through `core.hott_bridge`) — it does not exist yet.

## oracle/ — the coherence/horns/yoneda cluster (7 flagged files) — READ IN FULL — Tier A (real)

| File | What the code actually does | Verdict |
|---|---|---|
| `horns.py` | Builds the nerve (dim≤2). `inner_horns`: every composable spine A→B→C, composite = `f_conf·g_conf` (multiplicative quantale), flags whether (a,c) is filled / a `treats` edge. `invertible_pairs`: edges with both directions → checks it's a quasi-category (inner-fillable) NOT a Kan complex. **`coherence_conflicts`**: endpoint pairs reached by ≥2 intermediates whose composites DISAGREE (one ≥hi, one ≤lo) = ambiguous filler. | **Real.** Clean simplicial machinery. Diagnostic only (not wired into scoring). |
| `horns_vs_composition.py` | From-scratch tie-corrected `auroc` (Mann-Whitney) + `spearman`. Compares horn-filling (any B) vs `CompositionStrategy` (curated B types) on the 44-treatment benchmark, leak-controlled (`remove_direct_labels`). | **Real.** Key finding in code: same type prior ⇒ horn-filling ≡ composition (Spearman≈1, equal AUROC); the prior only trims coverage. |
| `horns_retrodiction.py` | **Leave-one-`treats`-edge-out** CV (`skip_pair=held`, rebuild nerve, score held vs all negatives). Aggregators: max / noisy-OR over DISTINCT intermediates / noisy-OR discounted by IDF **degree-specificity** `s(B)=clamp(log(N/(1+deg))/log N)`. Reports AUROC/AUPRC/Hits@K/MRR vs leakage-free graph baselines. | **Real, rigorous.** The gold-standard discipline of the cluster: recover removed truth, report honestly when corroboration doesn't beat max (hub confounding). |
| `coherence_dial.py` | Corroboration aggregators (base=max, noisy_or, corr-bonus `+κ·tanh(strong−1)·(1−base)`); AUROC + avg-rank of the 44 positives; biggest movers; **single-driver counter-test** (if true treatments are single-driver, corroboration can't help). | **Real diagnostic.** Honest null stated. |
| `coherence_specificity.py` | IDF protein-specificity `spec(P)=log(N_dis/breadth)/log N_dis` + drug-promiscuity penalty `1/(1+0.5·log #dis)`. Tests spec-weighted aggregators vs base AUROC **0.9807**; Sunitinib (promiscuity offender) + Imatinib/Ruxolitinib (clean single-driver) case studies. | **Real diagnostic.** Fixes the hub/promiscuity confound that made raw noisy-OR hurt. |
| `coherence.py` | `SheafCoherenceChecker`: groups predictions by (src,tgt); contradiction detection via **antonym list / `not_`-`non_` negation / suspicious cycles**; filters the lower-confidence side; `adjust_confidences` boosts agreement (+0.05·count, cap +0.15) / penalizes disagreement (×0.8). Uses `EmbeddingsEngine` for relation similarity. | **Real but rule-based** ("agree on overlaps" as a filter), **proposal-side** (embeddings, invariant #2). NOT H¹ cohomology — that's `topology/persistent_sheaves.py`. |
| `yoneda_strategy.py` | `InferenceStrategy`. Yoneda fingerprint = `(neighbor, relation)→max confidence` (in+out), on a CLEAN subgraph (MEASURED+ESTABLISHED, direct Drug→Disease labels EXCLUDED). Weighted-Jaccard distance; predicts via similarity to known treaters. | **Real, leak-controlled.** "An object is its weighted relationship-profile" — the rigorous form of "structure substitutes." |

### Why this cluster matters for silicon (Track 3 coherence)
It's all ONE domain-agnostic pattern, already benchmarked: **object = Yoneda relationship-profile;
hypothesis = unfilled inner horn; coherence = independent chains AGREE (corroboration),
down-weighted by SPECIFICITY (kill hub/promiscuity confounding), contradictions FILTERED;
validated by leave-one-out retrodiction vs leakage-free baselines.** That maps directly onto
EPE/DSA multi-view coherence (do the masks/views agree on a feature; is a non-specific global
constraint over-vouching) — and it is the SAME corroboration+specificity shape as the silicon
trust gate. **This cluster, not hott/cubical, is the ready coherence engine.** (Lift still
gated on real Track-3 data + a measured test, per the discipline.)

## Chip-coherence stack (the Track-3 engine) — READ IN FULL — Tier A (real)

| File | What the code actually does | Verdict |
|---|---|---|
| `topology/persistent_sheaves.py` | Two subsystems. (1) `CellularSheaf`: sections + restriction maps, `local/global_coherence`, `coboundary` (signed δ⁰/δ¹), `total_variation` = ‖δ⁰x‖² (Hansen-Ghrist sheaf Laplacian), `PersistentSheafComputer` (PH + coherence-across-filtration). (2) **`CellularCochainComplex`**: exact finite C⁰→C¹→C², *verifies* δ¹∘δ⁰=0, `cohomology()` = H⁰ (`ker δ⁰`), H¹ (`ker δ¹ / im δ⁰`) via SVD, **plus `h1_support`** (which edges carry the obstruction). | **Real cohomology**, not heuristic. The exact cochain complex is the gluing-obstruction engine. (1) is scalar/heuristic for β₀ but grounded; (2) is the load-bearing part for chips. |
| `domains/silicon/coherence.py` | `analyze_calibration_nerve` → builds `simplicial_cochain_complex` from artifacts/calibrations/certificates, returns H⁰/H¹ + support. `analyze_crosswalk_cohomology`: builds verilog↔def↔spef calibrations **only where evidence justifies them**, and refuses to invent verilog↔spef (derived through def) → a 2-view chain correctly gives H¹=0. | **Real, honest adapter.** Already wires the cohomology engine to silicon. Won't manufacture obstructions. |
| `domains/silicon/verilog.py` | `parse_verilog` (structural gate netlist: modules/ports/wire decls/named-port instances/constants). `build_crosswalk`: matches logical↔physical nets by **terminal-set identity** (frozenset of (inst,pin)), so synthesis renaming doesn't break it; reports renamed/logical_only/physical_only/cell_mismatches. | **Real.** The independent *logical* view + structural crosswalk. |

### Verdict for chips
The Track-3 coherence engine **exists and is tested** (exact H⁰/H¹ + support, plus a silicon
adapter and a logical-view parser). The gap is NOT math — it's a genuine *third independent
view* and real data. Multi-patterning (N masks of one layer) supplies that structure; the
oracle corroboration+specificity cluster supplies the trust-weighting. See
`docs/SILICON_POSTMOORE_PLAN.md` Track 3.

## Not prioritized (per user scoping) — read only if a specific file is flagged
- oracle/ (remaining 40 files), topology/ (4), categorical/ (20), zfc/ (13), cog/ (7),
  geometry/ (23), game/ (3), operadum/ (121). `topology/persistent_sheaves.py` is the one
  likely worth a full read next (real H⁰/H¹), since `coherence.py` is only rule-based.
