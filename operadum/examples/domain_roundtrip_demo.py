# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM domain + KOMPOSOS round-trip demo.

Run:  python -m examples.domain_roundtrip_demo

The full loop on a real domain:
  1. Load a synthesis-route design domain in one call (colours+reactions+cost).
  2. WRIGHT/DAEDALUS design the cheapest route to a target molecule.
  3. Run the route (it yields the target).
  4. Compile the route to a KOMPOSOS morphism graph and VERIFY it -- using the
     real KOMPOSOS-IV engine if its path is given, else a faithful MiniCategory.
  5. Score the domain's ground-truth accuracy.

OPERADUM designs; KOMPOSOS audits; the loop closes.
"""

import os

from operadum.domains.synthesis_design import SynthesisDesignDomain
from operadum.core.types import Spec
from operadum.wright.engine import Wright
from operadum.bridges.komposos_bridge import compile_to_komposos
from operadum.bridges.round_trip import KomposVerifier
from operadum.validation.domain_accuracy import measure_domain_accuracy

# Point the verifier at the real KOMPOSOS-IV-CHEM repo if it is present.
KOMPOSOS_PATH = r"C:\Users\JAMES\github\KOMPOSOS-IV-CHEM"
_kp = KOMPOSOS_PATH if os.path.isdir(KOMPOSOS_PATH) else None


def main():
    domain = SynthesisDesignDomain()
    op = domain.build_operad()
    print("1) Domain loaded:", op)
    print()

    spec = Spec(inputs=("Benzene",), output="Paracetamol")
    design = Wright(op, max_depth=8).optimize(spec).construction
    print(f"2) Cheapest route to Paracetamol: {design.wiring}")
    print(f"   cost = {design.cost}")
    print()

    print("3) Run the route:", design.artifact("Benzene"))
    print()

    graph = compile_to_komposos(design.composite, op)
    print("4) Compile -> KOMPOSOS reaction network:")
    for m in graph.morphisms:
        print(f"     {m['source']} --{m['name']}--> {m['target']}  "
              f"(confidence={m['confidence']:.3f})")
    result = KomposVerifier(komposos_path=_kp).verify(design.composite, op)
    print(f"   KOMPOSOS verdict: {result}")
    print(f"   {result.detail}")
    print()

    print("5) Domain ground-truth accuracy:")
    score = measure_domain_accuracy(domain, komposos_path=_kp)
    print("   ", score)


if __name__ == "__main__":
    main()
