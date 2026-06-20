# PRONOIA — An Interpretable, Non-LLM Prediction Stack

*Working codename: **PRONOIA** (Greek: foresight). Placeholder — rename freely.
Sibling to KOMPOSOS (interpret) and OPERADUM (design); this one **predicts**.*

**Status:** vision + build plan, 2026-06-04. Ambitious as a whole; every layer
has a small buildable prototype. Maturity is graded honestly per layer.

---

## 0. The thesis in one breath

**Prediction is compression. Compression is a game against nature. An honest
explanation is a faithful compressor of its own reasoning. Therefore: a predictor
that compresses well, plays the minimax game, fuses disagreeing evidence
consistently, keeps only the mechanisms that survive intervention, and certifies
that its explanation regenerates its behavior — is a real, interpretable
alternative to an LLM.**

This is not "one model." It is a **stack of sharp modules**, each best-in-class at
one job an LLM does fuzzily, each exposing its reasoning. They compose, but any
one can stand alone or plug into KOMPOSOS.

---

## 1. The stack (read bottom-up)

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ L5  CERTIFY    HoTT / cubical  +  honesty.py-as-MDL                        │
 │                "the explanation losslessly regenerates the behavior;        │
 │                 a lie shows up as excess code length. Abstain otherwise."   │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ L4  LEARN RULES  Bayesian program synthesis  +  Tsetlin machines          │
 │                  few-shot concepts as programs / readable logic clauses     │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ L3  GENERALIZE   Structural Causal Models (Pearl)                          │
 │                  keep the shortest descriptions that survive intervention   │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ L2  PREDICT      Compression / MDL  +  game-theoretic universal coding     │
 │                  score any hypothesis by how much it shortens the evidence; │
 │                  regret bounds fall out of the minimax game                 │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ L1  FUSE         Cellular sheaf over the network                           │
 │                  glue disagreeing sources; H¹ cohomology = inconsistency    │
 ├──────────────────────────────────────────────────────────────────────────┤
 │ L0  REPRESENT    Vector Symbolic Architecture (hyperdimensional computing) │
 │                  every entity/evidence/hypothesis → a composable hypervector│
 └──────────────────────────────────────────────────────────────────────────┘
```

Each paradigm from the earlier brainstorm has a home:
- #1 Compression/MDL → **L2** · #2 Causal → **L3** · #3 VSA → **L0** ·
  #4 Bayesian program synthesis → **L4** · #5 Tsetlin → **L4** ·
  honesty/HoTT → **L5** · sheaves → **L1**.

---

## 2. Layer by layer

Format per layer: **What · Math · Why it predicts · How to build · KOMPOSOS hook ·
Maturity · Honest caveat.**

### L0 — REPRESENT: Vector Symbolic Architectures (hyperdimensional computing)
- **What.** Represent every concept as a high-dim random vector (~10⁴-d). Build
  structure with algebra: **bind** (⊛, e.g. circular convolution / XOR) ties a
  role to a filler; **bundle** (+) superposes; **permute** sequences.
- **Math.** Near-orthogonality of random high-d vectors; binding is invertible
  (unbind = bind with inverse); similarity = cosine/Hamming. (Kanerva; Plate's
  Holographic Reduced Representations; Gayler.)
- **Why it predicts.** One-shot learning, analogy ("king ⊛ male⁻¹ ⊛ female"),
  noise-robust, *no backprop*. It is "embeddings + reasoning" without the net.
- **How to build.** Pure NumPy. Encode each drug/target/disease as a hypervector
  bundled from its evidence atoms; predict a missing link by binding/unbinding and
  reading off the nearest concept.
- **KOMPOSOS hook.** Drop-in encoder for graph nodes; the hypervector *is* the
  feature the upper layers consume.
- **Maturity.** 🟢 Buildable now (small library).
- **Caveat.** Capacity limits (a bundle blurs after ~dozens of items); design the
  binding scheme carefully.

### L1 — FUSE: Cellular sheaf over the evidence network
- **What.** A sheaf assigns each node/edge a small data space (a *stalk*) and each
  edge a *restriction map*. It is the correct math for **fusing local data that may
  disagree** and **measuring the disagreement**.
- **Math.** Cellular sheaves + the **sheaf Laplacian** (Hansen–Ghrist). **H⁰
  (global sections)** = assignments consistent with every local constraint = your
  prediction. **H¹ (cohomology)** = the obstruction to gluing = a *measurable*
  "these sources can't all be right" signal. (Neural Sheaf Diffusion, 2022.)
- **Why it predicts.** Sheaf diffusion fills missing stalk values *consistently
  with local evidence* — a principled link/value predictor that also self-reports
  contradictions.
- **How to build.** Stalks = the L0 hypervectors (or low-d feature spaces);
  restriction maps from edge type/confidence; sheaf Laplacian via SciPy sparse.
- **KOMPOSOS hook.** Over the existing drug–target–disease graph: predict missing
  edges via H⁰; flag known-contradictory evidence via H¹.
- **Maturity.** 🟡 Research-grade (sheaf Laplacians on heterogeneous graphs are
  fiddly; learning restriction maps is open).
- **Caveat.** The most novel and the most work. Start with fixed (not learned)
  restriction maps.

### L2 — PREDICT: Compression / MDL + game-theoretic universal coding
- **What.** Score *any* hypothesis by how much it shortens the description of your
  data. The best predictor is the best compressor (Solomonoff/MDL).
- **Math.** Two-part code `L(model) + L(data | model)`; pick the minimizer.
  **Universal coding is a minimax game**: Shtarkov's Normalized Maximum Likelihood
  is the game-optimal code; the **redundancy = the game value** (redundancy–
  capacity theorem). Online: log-loss prediction with regret bounds = excess code
  length (Cesa-Bianchi & Lugosi, *Prediction, Learning, and Games*; Vovk's
  aggregating algorithm).
- **Why it predicts.** Occam's razor *as math* — the shortest faithful description
  generalizes best — *with provable worst-case regret* from the game side.
- **How to build.** Practical MDL surrogates (two-part codes, context-tree
  weighting, off-the-shelf compressors as length estimators) to rank hypotheses;
  the aggregating algorithm to combine the lower layers as "experts" with regret
  guarantees.
- **KOMPOSOS hook.** Rank drug→disease hypotheses by **how much each compresses the
  evidence graph** — the hypothesis that most shortens "everything we know" wins.
- **Maturity.** 🟢 Buildable now (MDL scoring, expert aggregation) / 🔴 Theoretical
  ceiling (exact Solomonoff is uncomputable — approximate only).
- **Caveat.** "Description length" depends on your coding scheme; state it, don't
  hide it. Garbage codebook → garbage scores.

### L3 — GENERALIZE: Structural Causal Models (Pearl)
- **What.** Model mechanisms, not correlations. Predict under **intervention**
  (`do(x)`), which is what "predict really well *in the world*" requires.
- **Math.** Structural causal models, the do-calculus, causal discovery
  (constraint/score-based). Tight bond to L2: **a causal model is the shortest
  description that stays short under intervention** (independent-mechanisms /
  algorithmic-independence principle, Janzing–Schölkopf).
- **Why it predicts.** It survives distribution shift. Directly addresses the
  internal-vs-external gap (KOMPOSOS: 0.97 internal vs 0.64 external — that gap *is*
  a causal/shift problem).
- **How to build.** Promote the existing mechanistic Drug→Protein→Disease paths to
  a real SCM; use interventional/temporal data you already log to test edges.
- **KOMPOSOS hook.** You already have half a causal graph (mechanistic paths). This
  is the highest-value upgrade for predictive robustness.
- **Maturity.** 🟡 Research-grade (discovery from observational data needs stated
  assumptions).
- **Caveat.** Causal claims require assumptions you must *declare* — which is on-
  brand for the honesty layer, not a weakness.

### L4 — LEARN RULES: Bayesian program synthesis + Tsetlin machines
- **What.** Two interpretable few-shot learners. **Program synthesis**: infer the
  *program* that generated the data; predict by running it forward (Lake/Tenenbaum;
  DreamCoder). **Tsetlin machines**: learn predictions as human-readable
  propositional clauses via simple automata — no gradients.
- **Math.** Bayesian inference over a program prior (ties straight to L2: a short
  program *is* a short code); Tsetlin automata + clause voting.
- **Why it predicts.** Learns concepts from a *handful* of examples (the opposite
  of LLM data hunger) and returns the rule/program as the explanation.
- **How to build.** Tsetlin first (🟢 small, fast, readable clauses out);
  program synthesis on a small DSL over your domain (🟡 search is the cost).
- **KOMPOSOS hook.** Synthesize the *rule* behind known repurposings, apply to new
  pairs; Tsetlin gives auditable clauses that fit the honesty ethos.
- **Maturity.** 🟢 Tsetlin / 🟡 program synthesis.
- **Caveat.** Program search blows up without a good DSL and priors.

### L5 — CERTIFY: honesty.py-as-MDL + HoTT/cubical
- **What.** The integrity gate. An honest explanation **losslessly regenerates the
  actual behavior**; a lie is a compression failure.
- **The formalization (your idea, made rigorous).** Map `honesty.py`'s failure
  modes to MDL:
  - *fabricated step* = claimed code that doesn't run → description fails to
    reproduce the trace.
  - *hidden step* = real generating code omitted → stated description is **shorter
    than the truth yet claims completeness** = lossy where it claims lossless.
  - *distorted step* = wrong codebook (claimed justification ≠ actual).
  So **sincerity = "the stated explanation, run as a program, reproduces the trace,
  and is near-minimal."** "Abstain if no honest action" becomes **"abstain if no
  short honest program reproduces the behavior."** MDL as an integrity check.
- **HoTT's real home.** *Not* prediction — **identity and proof**. `honesty.py`
  already models sincerity as "sameness is a witnessed path that fails in
  structured ways" (pure HoTT). Use cubical/HoTT to *certify* equality of the
  stated and actual reasoning, not to forecast.
- **Why it matters.** Every prediction ships with a faithful, non-fabricated
  explanation — the thing LLMs structurally cannot give you.
- **How to build.** Extend `honesty.py` with a trace-regeneration scorer (does the
  explanation, executed, reproduce the trace? what's its excess length?).
- **Maturity.** 🟢 The MDL scorer is buildable now / 🔴 full HoTT proofs need
  Lean/Agda/cubical and are out of scope — keep the "MEASURED mode" honesty
  (bounds insincerity, doesn't prove honesty).
- **Caveat.** Honesty ≠ truth. L5 certifies the explanation is *faithful*; whether
  it's *true of the world* is L3's job (domain invariants). Don't conflate them.

---

## 3. How the layers actually talk to each other

- **L0 → L1.** Hypervectors are the sheaf *stalks*; binding/unbinding gives natural
  restriction maps.
- **L1 → L2.** A sheaf section is a candidate explanation; its **description length**
  (incl. the H¹ inconsistency penalty) is exactly what L2 scores. Contradiction
  costs bits.
- **L2 ↔ L3.** Causal models are the descriptions that stay short under
  intervention — L3 is L2 with an invariance constraint.
- **L2 ↔ L4.** A short program (L4) *is* a short code (L2). Same objective, two
  search spaces (clauses, programs).
- **All → L5.** Every layer emits a trace; L5 checks the trace *regenerates* the
  output and is minimal, else abstains.

The spine running through all of it: **bits.** Fusion cost, prediction score,
causal invariance, rule length, and honesty are *all measured in description
length.* That is what makes this one system, not five.

---

## 4. Build roadmap (smallest-first, dependency-ordered)

Each story: goal · deliverable · acceptance · maturity.

### Phase 0 — Prove the spine on data you already have (days, not weeks)
- **S0.1 — VSA encoder (L0).** Hypervector encoder for graph nodes from their
  evidence atoms. *Accept:* analogy + one-shot retrieval works on a toy
  drug–target set; nearest-neighbor recovers known links. 🟢
- **S0.2 — Sheaf inconsistency probe (L1).** Build a fixed-restriction sheaf over
  the existing KOMPOSOS graph; compute H¹. *Accept:* the obstruction lights up on
  **known-contradictory** edges and stays quiet on clean ones. 🟡 *(highest signal:
  if this fires correctly, the whole stack has a foundation.)*
- **S0.3 — honesty-as-MDL (L5).** Add a trace-regeneration scorer to `honesty.py`.
  *Accept:* a fabricated/hidden step shows up as measurable excess code length on a
  scripted example. 🟢 *(most "aha"; it's your own idea made rigorous.)*

### Phase 1 — A standing predictor (1–3 weeks)
- **S1.1 — MDL hypothesis ranker (L2).** Score drug→disease hypotheses by evidence
  compression; compare ranking to the current KOMPOSOS scorer. *Accept:* AUROC on
  the existing benchmark within noise of (or above) today, with a bits-based
  explanation per call. 🟢
- **S1.2 — Tsetlin rule learner (L4).** Train on known repurposings; emit clauses.
  *Accept:* readable clauses + accuracy competitive with a baseline. 🟢
- **S1.3 — Expert aggregation (L2 game side).** Combine L1/L4 outputs via the
  aggregating algorithm. *Accept:* measured regret bound vs the best single module.
  🟢

### Phase 2 — Robustness + composition (1–2 months)
- **S2.1 — Causal upgrade (L3).** Promote mechanistic paths to an SCM; test edges
  against temporal/interventional data. *Accept:* improved **external** AUROC
  (the real metric), not just internal. 🟡
- **S2.2 — Sheaf-VSA fusion (L0+L1).** Hypervector stalks + learned-ish restriction
  maps; sheaf-diffusion prediction. *Accept:* recall@N vs the exhaustive scorer,
  with H¹ as a live contradiction meter. 🟡
- **S2.3 — Program synthesis (L4).** Small DSL; synthesize repurposing rules.
  *Accept:* a synthesized rule reproduces a held-out family of known links. 🟡

### Phase 3 — The certified loop (ongoing)
- **S3.1 — End-to-end integrity.** Every prediction passes L5 (regenerates trace,
  near-minimal) or the system abstains. *Accept:* an abstention rate and a
  per-prediction "bits + faithful explanation" record. 🟢 wrapper / 🔴 full proofs
  out of scope.

**Rule of thumb:** ship S0.2 and S0.3 first. They are cheap, they are the two most
distinctive ideas (sheaf-contradiction detection + honesty-as-compression), and if
they work the rest of the stack is justified.

---

## 5. Connection to KOMPOSOS / OPERADUM (optional, not required)

- **Standalone.** PRONOIA can predict with zero KOMPOSOS dependency — VSA + MDL +
  Tsetlin run on any tabular/graph data.
- **As a KOMPOSOS predictor.** Swap/augment the oracle scorer with the L2 MDL
  ranker; feed H¹ contradiction scores into the evidence gate; reuse the existing
  mechanistic graph as the L3 causal skeleton.
- **As an OPERADUM evaluator.** OPERADUM *designs* candidates; PRONOIA *predicts*
  their quality and compresses the evidence for each — a natural design→predict
  loop. (OPERADUM's shortlist→rerank already rhymes with L2 expert aggregation.)
- **Shared DNA.** Both KOMPOSOS and PRONOIA are built on *honest, inspectable
  reasoning*. PRONOIA just turns the honesty checker into a predictor.

---

## 6. Honest risk register

- **Most novel = most risk.** L1 (sheaves) and L3 (causal discovery) are research-
  grade; budget for them to be hard or to fail, and gate on real metrics.
- **Compression is scheme-dependent.** Description length is only as meaningful as
  the codebook; always state the coding scheme. This is a footgun if hidden.
- **Solomonoff/HoTT-proofs are ceilings, not deliverables.** Build the computable
  approximations (MDL, MEASURED-mode honesty); don't promise the uncomputable.
- **Don't oversell category theory or HoTT as predictors.** They structure and
  certify; L2/L3/L4 predict. Keep that line clean.
- **Validate externally, always.** The whole point is generalization; an internal
  win that doesn't move external/held-out numbers is noise.
- **Scope creep.** Five paradigms is a lot. The phased plan exists so you get value
  from S0/S1 even if Phases 2–3 never happen.

---

## 7. Next step

Pick the first prototype — my recommendation is **S0.2 (sheaf contradiction probe)**
or **S0.3 (honesty-as-MDL)**; they're the cheapest and the most uniquely yours.
Say which, and I'll write the actual math + a minimal module we can stand up and
watch run — same way we built the OPERADUM ranker.

*(Names to consider instead of PRONOIA: TEKMAR (Gk. "proof/token/sign"), MANTIS
(Gk. "seer"), SOLOMON (nod to Solomonoff + judgment). Your call.)*
