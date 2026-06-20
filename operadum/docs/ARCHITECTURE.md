# Architecture Map

This repository is the delivery home for the design and prediction stack. It is
not an Orion project and does not require Orion.

## Canonical Layout

```text
operadum/
  domain_core/          shared contracts only
  operadum/             design engine: proposes/builds candidates
  pronoia/              prediction engine: ranks, checks, certifies
  tests/pronoia/        PRONOIA tests after consolidation
  examples/pronoia/     PRONOIA demos after consolidation
  docs/                 architecture notes and imported PRONOIA docs
```

KOMPOSOS remains a separate evidence/verification system. This repo should hold
adapters to KOMPOSOS, not a copied KOMPOSOS tree.

## Engine Responsibilities

- `domain_core`: owns the shared nouns. `Candidate`, `EvidencePacket`,
  `PredictionReport`, `TraceStep`, and provider/predictor protocols live here.
  It has no dependency on OPERADUM, PRONOIA, or KOMPOSOS.
- `operadum`: constructs or proposes candidates and can compile designs into
  evidence graphs for verification.
- `komposos_adapter`: the boundary to external KOMPOSOS checkouts. It should turn
  KOMPOSOS graph paths, scores, validation results, and provenance into
  `EvidencePacket` objects. Existing adapters can live under `operadum.integrations`
  until they are worth promoting.
- `pronoia`: consumes `EvidencePacket` objects and returns `PredictionReport`
  objects. It is responsible for MDL ranking, sheaf contradiction checks, causal
  checks, learned rules, and honesty/grounding gates.

## Intended Flow

```text
OPERADUM proposes Candidate
        ->
KOMPOSOS adapter gathers EvidencePacket
        ->
PRONOIA emits PredictionReport
        ->
app/example displays decision, trace, bits, and abstain/pass status
```

## What Not To Do

- Do not copy full KOMPOSOS repos into this repository for delivery.
- Do not make PRONOIA import OPERADUM internals for prediction.
- Do not make OPERADUM depend on PRONOIA internals to propose candidates.
- Do not add Orion as a dependency. If plugin behavior is needed, keep it local
  to OPERADUM's existing forge/domain system.

## Current Consolidation Status

- PRONOIA has been promoted from the copied nested folder into a sibling package:
  `pronoia/`.
- PRONOIA tests live under `tests/pronoia/`.
- The original PRONOIA README was kept as `docs/PRONOIA_README.md`.
- `domain_core/` now defines the shared contracts that prevent future scattering.
- `pronoia.domain_adapter.PronoiaPredictor` is the first contract-based adapter.


## Phase 1 Standing Predictor Loop

The next spine is now represented in code:

```text
domain_core.Candidate
  -> operadum.integrations.KompososPharmEvidenceProvider
  -> domain_core.EvidencePacket
  -> pronoia.domain_adapter.PronoiaPredictor
  -> domain_core.PredictionReport
```

Run the live PHARM loop demo with:

```powershell
python -m examples.pronoia.pharm_prediction_loop_demo
```

This is intentionally a vertical slice. It proves the shared contracts can carry
real KOMPOSOS evidence into PRONOIA without merging the engines or copying the
KOMPOSOS repository.
## Verification Commands

```powershell
python -m pytest operadum/tests tests -q -p no:cacheprovider
python -c "import domain_core, operadum, pronoia; print('imports ok')"
```
