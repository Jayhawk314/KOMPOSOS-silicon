# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
General figure profiles: same operations, different optimization intent.

Run:
    python -m examples.figure_profiles_demo
"""

from operadum import (
    Operad,
    Spec,
    Wright,
    SAFETY_FIRST,
    FASTEST_RECOVERY,
    GENERAL_FIGURES,
)


def release_operad(monoid):
    op = Operad("manufacturing-release", monoid=monoid)
    op.add_op(
        "quick_close",
        [],
        "Released",
        cost={
            "schedule_delay": 1,
            "safety_risk": 0.70,
            "compliance_debt": 1,
            "confidence": 0.70,
        },
    )
    op.add_op(
        "document_torque_inspect",
        [],
        "Released",
        cost={
            "schedule_delay": 8,
            "safety_risk": 0.01,
            "compliance_debt": 0,
            "confidence": 0.96,
        },
    )
    return op


def main():
    safest = Wright(release_operad(SAFETY_FIRST)).optimize(Spec((), "Released"))
    fastest = Wright(release_operad(FASTEST_RECOVERY)).optimize(Spec((), "Released"))

    def pretty(figures):
        return {k: round(float(v), 4) for k, v in sorted(figures.items())}

    print("Same component library, different global figure profile:")
    print(f"  SAFETY_FIRST      -> {safest.construction.wiring}  {pretty(safest.construction.cost)}")
    print(f"  FASTEST_RECOVERY  -> {fastest.construction.wiring}  {pretty(fastest.construction.cost)}")
    print()

    constrained = Wright(release_operad(GENERAL_FIGURES)).optimize(
        Spec(
            (),
            "Released",
            budget={"safety_risk": 0.05, "compliance_debt": 0},
            requirements={"confidence": 0.9},
        )
    )
    print("Hard figure limits:")
    print("  budget       safety_risk<=0.05, compliance_debt<=0")
    print("  requirements confidence>=0.9")
    print(f"  selected     {constrained.construction.wiring}  {pretty(constrained.construction.cost)}")


if __name__ == "__main__":
    main()
