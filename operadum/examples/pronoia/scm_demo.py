"""
Demo: Structural Causal Model — observation lies, intervention tells the truth.

Confounding by indication: sicker patients are more likely to be treated, and
severity also lowers recovery. So the OBSERVED association makes the drug look
useless — even though it genuinely helps.

  Severity S ~ Bernoulli(0.5)                         (confounder)
  Treatment T ~ Bernoulli(0.8 if sick else 0.2)       (sicker -> more treated)
  Recovery  Y = 0.5 + 0.4*T - 0.6*S + noise           (drug helps; severity hurts)

True causal effect of the drug = +0.4. Watch what each query says.

    python -m examples.scm_demo
"""

from __future__ import annotations

import numpy as np

from pronoia.scm import SCM


def build() -> SCM:
    m = SCM()
    m.add("S", [], lambda d, r, n: (r.random(n) < 0.5).astype(float))
    m.add("T", ["S"],
          lambda d, r, n: (r.random(n) < np.where(d["S"] == 1, 0.8, 0.2)).astype(float))
    m.add("Y", ["T", "S"],
          lambda d, r, n: 0.5 + 0.4 * d["T"] - 0.6 * d["S"] + r.normal(0, 0.1, n))
    return m


def main() -> None:
    m = build()
    obs = m.observational_effect("T", "Y")
    causal = m.causal_effect("T", "Y")
    adjusted = m.backdoor_effect("T", "Y", adjust=["S"])

    print("Effect of the drug on recovery (true structural effect = +0.40):\n")
    print(f"  observed association  E[Y|T=1]-E[Y|T=0]        = {obs:+.3f}   <- biased, looks useless")
    print(f"  causal effect         E[Y|do(T=1)]-E[Y|do(T=0)] = {causal:+.3f}   <- the truth")
    print(f"  back-door adjusted (for severity S)            = {adjusted:+.3f}   <- recovers truth from observational data")
    print("\nObservation confounds the drug with severity; do(...) and correct")
    print("adjustment reveal it helps. This is why causal models generalize.")


if __name__ == "__main__":
    main()
