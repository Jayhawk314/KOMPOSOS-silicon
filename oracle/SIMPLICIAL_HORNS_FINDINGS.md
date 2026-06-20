# Simplicial Horns on the Drug-Repurposing Category — Findings

**Status:** settled negative result for ranking; positive result for *structure &
confidence*. Session 2026-06-03. All artifacts are standalone diagnostics — **none
is wired into `make_strategies` or any score**.

## TL;DR

1. **Inner-horn filling IS the composition strategy** — proven empirically, identical
   to floating-point dust (max |Δ| = 1.1e-16 over 1,293 pairs, Spearman = 1.0000).
2. **Four elaborations on top of it all fail to beat plain `max` for ranking**
   (coherence noisy-OR, specificity-IDF, signed superposition, hybrid re-ranker).
3. **Why:** `base = max(magnitude)` (= composition) is already near-ceiling on this
   benchmark — **AUROC 0.9807** globally and **hit@3 93% / hit@1 75%** within-drug.
   There is almost nothing left to fix.
4. **The genuine value of the horn layer is NOT a better number** — it is structure
   and confidence: filled/unfilled typing, inner/outer (composition vs equivalence),
   a soundness check (recovered all 44 known treatments), and a confidence/margin
   signal. Use it there, never in the point estimate.
5. **The only un-exhausted lever is DATA, not math:** protein→disease edges lack a
   causal sign (only 19% of chains are signed; 12 harmful edges in the whole graph),
   which starves any interference/coherence model.

## The construction

Nerve of the loaded `Category` up to dimension 2:
- 0-simplices = objects (Drug 78, Protein 269, Disease 20, …)
- 1-simplices = morphisms (weighted edges)
- 2-simplices = composable spines `A→B→C` with a witnessing `A→C` (filled triangle)

An **inner horn `Λ²₁`** is a spine `Drug --mech--> Protein --assoc--> Disease` with no
direct `Drug --treats--> Disease` edge. **Filling it = predicting the repurposing.**
Filler confidence = product of the two edge confidences (multiplicative quantale).

Outer horns `Λ²₀/Λ²₂` would need an edge *inverted* → an equivalence/invertibility
claim → the Kan condition → the `Rezk` strategy's territory. The nerve has only **2
invertible edge pairs**, so it is a **quasi-category (inner-fillable), not a Kan
complex** — exactly as a causal biomedical graph should be.

## Experiments and results

All scoring is leak-free (`remove_direct_labels=True`); labels are the 44 FDA
oncology `treats` pairs; candidates are all 78×20 = 1,560 Drug×Disease pairs.

| experiment | result | verdict |
|---|---|---|
| horn-filling vs composition | AUROC 0.9807 vs 0.9807; ρ=1.0; max|Δ|=1.1e-16 | **identical construction** |
| coherence noisy-OR | AUROC 0.9337 | worse (promiscuity inflation) |
| specificity-weighted (IDF) | AUROC 0.6435 | much worse (assoc_with zeros real drivers) |
| drug-promiscuity penalty | AUROC 0.9684 | worse (penalizes true indications too) |
| signed superposition (net_strict) | AUROC 0.7447 | fails globally (19% sign coverage) |
| signed superposition (within Sunitinib) | GIST/RCC surfaced over 18 false | **right locally** |
| hybrid (base + w·net_strict) | AUROC ↓ (0.97→0.92), within-drug MRR flat | no gain |

### Why each elaboration failed

- **Coherence / noisy-OR:** only *adds* evidence, never cancels, so promiscuous
  multi-target drugs (Sunitinib) get boosted toward *every* disease. 21 of 44 true
  treatments are clean **single-driver** mechanisms (Imatinib→BCR_ABL→CML) that
  corroboration cannot help and actively demotes.
- **Specificity-IDF:** measured protein "breadth" over *all* disease edges, but the
  promiscuous `associated_with` relation makes even genuine drivers (JAK2) look
  non-specific → spec ≈ 0 → real drivers zeroed. Broken proxy.
- **Signed superposition:** the right idea (let contradictory mechanisms
  destructively interfere), but the data only signs **19%** of chains (protein→disease
  causal direction is unencoded) and contains only **12 harmful edges** — so
  interference is starved and cancellation is essentially never exercised.
- **Hybrid re-ranker:** base already ranks the true indication #1 for 75% of drugs and
  top-3 for 93% — even Sunitinib's GIST/RCC are already #1/#2 under base. Nothing to
  fix; the nudge only widened the confidence margin while costing global AUROC.

## What IS worth keeping from the horn layer

- **Filled/unfilled bookkeeping** — recovered all 44 known treatments as filled
  triangles with correct mechanism spines (Imatinib→BCR_ABL→CML, etc.); a soundness/
  audit check composition does not give for free.
- **Inner vs outer typing** — every prediction can be tagged "composition" (expected)
  vs "equivalence claim" (needs invertibility, rare, must be earned).
- **Confidence/margin annotation** — the signed model's real effect was *widening the
  gap* between a drug's true and false indications, not reordering them. That belongs
  in the uncertainty band, paired with (but distinct from) cross-strategy
  **gray coherence**. Λ³ dial = within-strategy corroboration; gray coherence =
  across-strategy agreement. Use per circumstance.

## The one real future lever (data, not math)

To ever beat `max` for ranking you must give interference something to act on:
**encode causal sign on protein→disease edges** (driver vs suppressor; up/down
regulation). That would raise sign coverage well above 19% and let signed
superposition — including destructive cancellation — actually run. Expected upside is
plausible but unproven; it is a data-curation project with a falsifiable hypothesis,
which is a far better place to invest than another aggregator.

## Files (pharm repo, all standalone diagnostics)

- `oracle/horns.py` — nerve / horn enumeration; filled vs unfilled; Kan check; coherence stub
- `oracle/horns_vs_composition.py` — proved horn-ranking ≡ composition
- `oracle/coherence_dial.py` — corroboration aggregators (noisy-OR, corr-bonus): lose
- `oracle/coherence_specificity.py` — specificity/promiscuity weighting: lose
- `oracle/path_superposition.py` — signed-amplitude interference + coverage gate
- `oracle/hybrid_reranker.py` — base global order + signed within-drug nudge: no gain

## Bottom line

The simplicial framing is **sound and unifying** (composition = inner-horn filling;
Rezk = outer/Kan), and it gives real **structure and confidence** signals. It does
**not** improve ranking on this benchmark, because composition/max is already near the
ceiling. Stop tuning the ranking; spend effort on causal-sign data or on the
structure/confidence layer where horns genuinely add value.

---

## Independent confirmation via leave-one-edge-out (Session 2026-06-07)

`oracle/horns_retrodiction.py` re-tests the two key claims under a **stricter
protocol** than the earlier `remove_direct_labels` global removal: it holds out **each
`treats` edge individually** (`load_full_typed_view(skip_pair=...)`, which also strips
that pair's label-derived bridges), rebuilds the nerve per fold, scores the held pair
against all negatives, and averages. Corroboration is noisy-OR over **distinct
intermediates** B (parallel edges through the same B collapsed by `max` first), and the
specificity variant discounts each B by an IDF weight `s(B)=clamp₀(log(N/(1+deg B))/log N)`.

Result (44 held-out FDA `treats` edges, 78×20 candidate pairs):

| scorer | AUROC | AUPRC | Hits@10 | MRR |
|---|---|---|---|---|
| **horn-max** (single best spine) | **0.9804** | **0.5837** | 0.700 | 0.0755 |
| horn-noisy_or (corroboration) | 0.9380 | 0.3661 | 0.700 | 0.0689 |
| horn-noisy_or-spec (IDF hub penalty) | 0.8938 | 0.2716 | 0.600 | 0.0586 |
| best graph baseline (common-neighbor) | 0.6219 | — | — | — |

Independently reproduces the settled conclusion:

1. **Horn-max crushes naive baselines** (0.98 vs 0.62) on recovering *deleted* truth —
   the strongest validation of the mechanism-spine signal, under per-edge hold-out.
2. **Corroboration still loses** (noisy_or 0.938 < max 0.980), matching the earlier
   coherence-noisy-OR result (0.9337). Avg only **2.0 distinct intermediates per true
   edge** — too sparse to corroborate, and noisy-OR inflates hub-routed negatives.
3. **Specificity weighting makes it WORSE, not better** (0.894), confirming line 49's
   finding from the IDF direction: real drug mechanisms route through **well-studied,
   high-degree** target proteins, so penalizing degree penalizes the true drivers. The
   *sign* of the effect rules out specificity-weighted corroboration on this graph — no
   knob setting beats `max`. This is a clean negative, recorded rather than tuned away.

Reusable artifact: the per-edge leave-one-out harness in `horns_retrodiction.py` will
honestly vet any future scoring change against deleted-truth recovery.
