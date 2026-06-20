# SPDX-License-Identifier: Apache-2.0
"""
Horn-Filling Strategy  (generic, domain-agnostic).

Promotes the simplicial-nerve idea from oracle/horns.py into the runtime
strategy registry. Where oracle/horns.py is a STANDALONE drug-repurposing
diagnostic (it imports the pharma benchmark and only enumerates Drug->Disease
spines), this strategy is the same construction with the domain stripped out:
it works on any Category and is registered in create_all_strategies().

The construction, in one line
-----------------------------
    An unfilled inner horn  Lambda^2_1 :  A --f--> B --g--> C
    (with NO direct A --> C edge)  IS a hypothesis, and
    FILLING it  =  predicting the A->C edge.

The filler's confidence is the composite along the spine (product of edge
confidences -- the multiplicative enriched-category / quantale rule), matching
CompositionStrategy.

Why this is not just CompositionStrategy
----------------------------------------
CompositionStrategy reports the single best 2-hop path and (in this codebase)
carries a drug-repurposing type filter on the intermediate. HornFillingStrategy
is type-agnostic and adds the *coherence* signal that the nerve makes visible:
when MANY intermediates B_i span the same (A, C) horn, do their fillers AGREE?

  - Concordant fillers (low spread)  -> independent mechanistic confirmation,
    confidence is boosted above the single best spine.
  - Discordant fillers (high spread) -> the predicted edge is ambiguous; we keep
    the best composite but flag `coherent=False` in the evidence so downstream
    sheaf-coherence / honesty gates can see the disagreement.

This is the enriched/fuzzy analogue of asking whether the nerve fills its inner
horns *coherently*, rather than merely whether a composite exists.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy


class HornFillingStrategy(InferenceStrategy):
    """Fill inner 2-horns A->B->C to predict the missing A->C edge.

    Generic over any Category. Confidence = best spine composite, adjusted by
    cross-intermediate coherence.
    """

    name = "horn_filling"

    # A horn pair is only interesting if at least this many distinct
    # intermediates witness it before we treat agreement as confirmation.
    _CONFIRM_MIN_INTERMEDIATES = 2
    # Composites within this band of the best are treated as "agreeing".
    _CONCORDANT_SPREAD = 0.20
    # Per extra concordant intermediate, multiply confidence by (1 + this).
    _CONFIRM_BONUS = 0.05
    _MAX_CONFIDENCE = 0.95

    def predict(self, source: str, target: str) -> List[Prediction]:
        existing = self._existing_morphism_pairs()
        # An already-filled horn is not a prediction.
        if (source, target) in existing:
            return []

        outgoing, _ = self._build_morphism_index()
        if source not in outgoing:
            return []

        # Enumerate spines  source --f--> B --g--> target  with distinct A,B,C.
        # Each spine is (intermediate, f_morphism, g_morphism, composite).
        spines = []
        for f in outgoing.get(source, []):
            b = f.target
            if b == source or b == target:
                continue
            for g in outgoing.get(b, []):
                if g.target != target:
                    continue
                composite = float(f.confidence) * float(g.confidence)
                spines.append((b, f, g, composite))

        if not spines:
            return []

        composites = [s[3] for s in spines]
        best_b, best_f, best_g, best_comp = max(spines, key=lambda s: s[3])
        intermediates = {s[0] for s in spines}
        n_intermediates = len(intermediates)
        spread = max(composites) - min(composites)

        # Coherence-adjusted confidence.
        confidence = best_comp
        coherent = True
        if n_intermediates >= self._CONFIRM_MIN_INTERMEDIATES:
            if spread <= self._CONCORDANT_SPREAD:
                # Independent agreeing fillers reinforce the prediction.
                concordant = sum(
                    1 for c in composites if c >= best_comp - self._CONCORDANT_SPREAD
                )
                confidence = min(
                    self._MAX_CONFIDENCE,
                    best_comp * (1.0 + self._CONFIRM_BONUS * (concordant - 1)),
                )
            else:
                # Fillers disagree: keep the best composite but mark ambiguous so
                # coherence / honesty gates downstream can react.
                coherent = False

        # Name the predicted edge the way CompositionStrategy does, so merged
        # ensemble keys line up when both fire on the same spine.
        if best_f.name == best_g.name:
            relation = best_f.name
        else:
            relation = f"composed_{best_f.name}_{best_g.name}"
            if "influenced" in relation:
                relation = "influenced"

        reasoning = (
            f"Inner horn Lambda^2_1 filled: {source} -[{best_f.name} "
            f"{best_f.confidence:.2f}]-> {best_b} -[{best_g.name} "
            f"{best_g.confidence:.2f}]-> {target} (composite {best_comp:.3f}); "
            f"{n_intermediates} intermediate(s), spread {spread:.2f}, "
            f"{'coherent' if coherent else 'AMBIGUOUS'}"
        )

        return [Prediction(
            source=source,
            target=target,
            predicted_relation=relation,
            prediction_type=PredictionType.HORN_FILLING,
            strategy_name=self.name,
            confidence=confidence,
            reasoning=reasoning,
            evidence={
                "intermediate": best_b,
                "morphism1": best_f.name,
                "morphism2": best_g.name,
                "confidence1": float(best_f.confidence),
                "confidence2": float(best_g.confidence),
                "composite": round(best_comp, 4),
                "n_intermediates": n_intermediates,
                "intermediates": sorted(intermediates),
                "spread": round(spread, 4),
                "coherent": coherent,
            },
        )]
