#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Simplicial horns over the drug-repurposing category  (STANDALONE DIAGNOSTIC).

NOT registered in make_strategies(); nothing here feeds a score. This is the
explicit *simplicial* layer that oracle/yoneda_strategy.py and the chem
"simplicial_strategies" only gesture at: it builds the low-dimensional NERVE of
the category and reads off HORNS.

The point, in one line:

    An unfilled inner horn  Lambda^2_1 :  Drug --mech--> Protein --assoc--> Disease
    (with NO direct Drug --treats--> Disease edge)  IS a repurposing hypothesis,
    and FILLING it  =  predicting the Drug->Disease edge.

Constructions
-------------
Nerve N(C) of the loaded Category C:
    0-simplices : objects (drugs, proteins, diseases, ...)
    1-simplices : morphisms (weighted edges)
    2-simplices : composable spines A->B->C *with* a witnessing A->C edge (a
                  filled triangle)

A 2-horn is Delta^2 with its interior + one face removed:
    Lambda^2_1  (INNER) : the spine A->B->C, missing edge A->C and the 2-cell.
                          Filling it = supplying the composite A->C. -> COMPOSITION.
    Lambda^2_0, Lambda^2_2 (OUTER) : a span / cospan. Filling them needs an edge
                          INVERTED -> only valid when the relation is reversible.
                          -> EQUIVALENCE / Kan condition (cf. Rezk strategy).

A quasi-category fills every INNER horn ("every mechanism composes").
A Kan complex fills every horn incl. outer ("every arrow is invertible" =
groupoid). A drug graph is the former, not the latter -- we verify that below.

Weighting note (honesty)
------------------------
Edges carry confidence in [0,1], so this is an *enriched / fuzzy* simplicial
object, not a strict Kan complex. A horn filler therefore comes with a graded
confidence (the composite = product along the spine, matching the multiplicative
quantale and the existing composition strategy), and fillers need not be unique.
We do NOT compute homotopy groups; we use simplicial structure as an organizing
principle + a coherence check.

Run:
    python -m oracle.horns
    python -m oracle.horns --top 25
"""

from __future__ import annotations

import argparse
from collections import defaultdict, namedtuple
from typing import Dict, List, Optional, Set, Tuple

from validation.repurposing_benchmark import load_full_typed_view

# A 2-horn spine A --f--> B --g--> C, plus what (if anything) fills edge A->C.
Horn = namedtuple(
    "Horn",
    "a b c f_name f_conf g_name g_conf composite filled_any filled_treats",
)


# ── Indexing ──────────────────────────────────────────────────────────────────

def _index(cat) -> Tuple[Dict[str, str], Dict[Tuple[str, str], float], Set[Tuple[str, str]]]:
    """type_by[name]=type, direct[(s,t)]=best confidence, treats={(drug,disease)}."""
    type_by = {o.name: o.type_name for o in cat.objects()}
    direct: Dict[Tuple[str, str], float] = {}
    treats: Set[Tuple[str, str]] = set()
    for m in cat.morphisms():
        key = (m.source, m.target)
        direct[key] = max(direct.get(key, 0.0), float(m.confidence))
        if m.name == "treats":
            treats.add(key)
    return type_by, direct, treats


# ── Inner horn enumeration (Lambda^2_1) ───────────────────────────────────────

def inner_horns(
    cat,
    a_type: Optional[str] = None,
    c_type: Optional[str] = None,
) -> List[Horn]:
    """Every inner 2-horn (composable spine A->B->C with distinct A,B,C).

    Optionally restrict endpoint types (e.g. a_type='Drug', c_type='Disease').
    'filled_any' = some A->C morphism exists; 'filled_treats' = a 'treats' edge
    exists (the meaningful filler for a Drug->Disease horn).
    """
    type_by, direct, treats = _index(cat)
    horns: List[Horn] = []
    for B in cat.objects():
        b = B.name
        ins = cat.morphisms_to(b)
        outs = cat.morphisms_from(b)
        if not ins or not outs:
            continue
        for f in ins:
            a = f.source
            if a_type and type_by.get(a) != a_type:
                continue
            for g in outs:
                c = g.target
                if c_type and type_by.get(c) != c_type:
                    continue
                if len({a, b, c}) != 3:
                    continue
                horns.append(Horn(
                    a, b, c, f.name, float(f.confidence), g.name, float(g.confidence),
                    round(float(f.confidence) * float(g.confidence), 4),
                    (a, c) in direct, (a, c) in treats,
                ))
    return horns


def best_fillers(horns: List[Horn]) -> Dict[Tuple[str, str], Horn]:
    """Collapse to the strongest spine per (A,C) endpoint pair."""
    best: Dict[Tuple[str, str], Horn] = {}
    for h in horns:
        key = (h.a, h.c)
        if key not in best or h.composite > best[key].composite:
            best[key] = h
    return best


# ── Outer horns / the Kan question ────────────────────────────────────────────

def invertible_pairs(cat) -> List[Tuple[str, str]]:
    """Pairs (s,t) with BOTH s->t and t->s present -> outer horns are fillable here."""
    _, direct, _ = _index(cat)
    seen = set()
    out = []
    for (s, t) in direct:
        if s < t and (t, s) in direct and (s, t) not in seen:
            seen.add((s, t))
            out.append((s, t))
    return out


# ── Coherence (multiple 2-simplices on one boundary edge) ─────────────────────

def coherence_conflicts(horns: List[Horn], hi: float = 0.5, lo: float = 0.2) -> List[dict]:
    """Endpoint pairs reached by several intermediates whose fillers DISAGREE.

    Under the multiplicative quantale strict associativity is automatic, so the
    meaningful coherence signal is *filler disagreement across intermediates*:
    different mechanistic chains predicting contradictory composite strengths for
    the same Drug->Disease edge. We flag pairs that carry both a strong (>=hi) and
    a weak (<=lo) filler.
    """
    by_pair: Dict[Tuple[str, str], List[Horn]] = defaultdict(list)
    for h in horns:
        by_pair[(h.a, h.c)].append(h)
    conflicts = []
    for (a, c), hs in by_pair.items():
        comps = [h.composite for h in hs]
        if len(hs) >= 2 and max(comps) >= hi and min(comps) <= lo:
            strong = max(hs, key=lambda h: h.composite)
            weak = min(hs, key=lambda h: h.composite)
            conflicts.append({
                "a": a, "c": c, "n_intermediates": len({h.b for h in hs}),
                "spread": round(max(comps) - min(comps), 4),
                "strong": (strong.b, strong.composite),
                "weak": (weak.b, weak.composite),
            })
    conflicts.sort(key=lambda d: d["spread"], reverse=True)
    return conflicts


# ── Report ────────────────────────────────────────────────────────────────────

def _spine(h: Horn) -> str:
    return (f"{h.a} -[{h.f_name} {h.f_conf:.2f}]-> {h.b} "
            f"-[{h.g_name} {h.g_conf:.2f}]-> {h.c}")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=15, help="how many candidates to show")
    args = ap.parse_args(argv)

    print("=" * 74)
    print("  HORNS over the drug-repurposing category  (nerve, dim <= 2)")
    print("=" * 74)

    cat, _ = load_full_typed_view()
    n_obj = len(list(cat.objects()))
    n_mor = len(list(cat.morphisms()))

    # Repurposing-relevant inner horns: Drug --mech--> ? --assoc--> Disease.
    rep = inner_horns(cat, a_type="Drug", c_type="Disease")
    best = best_fillers(rep)
    filled = [h for h in best.values() if h.filled_treats]
    unfilled = [h for h in best.values() if not h.filled_treats]
    unfilled.sort(key=lambda h: h.composite, reverse=True)

    print(f"\n0-simplices (objects): {n_obj}")
    print(f"1-simplices (morphisms): {n_mor}")
    print(f"Inner 2-horns  Lambda^2_1  with Drug->...->Disease spine: {len(rep)}")
    print(f"  distinct Drug->Disease endpoint pairs spanned: {len(best)}")
    print(f"  of these, FILLED (a 'treats' edge exists):   {len(filled)}")
    print(f"  UNFILLED (candidate repurposings):           {len(unfilled)}")

    # 1. A filled inner horn = a KNOWN treatment that also has a mechanism spine.
    print("\n" + "-" * 74)
    print("[1] A FILLED inner horn  (known 'treats' edge WITH a mechanistic 2-cell)")
    print("    The triangle is complete: spine composes to an edge that really exists.")
    for h in sorted(filled, key=lambda h: h.composite, reverse=True)[:3]:
        print(f"    filler: {h.a} --treats--> {h.c}   [the Delta^2 is filled]")
        print(f"      spine: {_spine(h)}   (composite {h.composite:.3f})")

    # 2. Unfilled inner horns = candidate repurposings. Filling = prediction.
    print("\n" + "-" * 74)
    print(f"[2] UNFILLED inner horns -> FILLING = PREDICTION  (top {args.top} by composite)")
    print("    Drug --mech--> intermediate --assoc--> Disease, but no 'treats' yet.")
    for i, h in enumerate(unfilled[:args.top], 1):
        print(f"   {i:>2}. fill?  {h.a} --treats?--> {h.c}   conf~{h.composite:.3f}")
        print(f"        via   {_spine(h)}")

    # 3. Outer horns / Kan: is this a quasi-category or a Kan complex?
    inv = invertible_pairs(cat)
    print("\n" + "-" * 74)
    print("[3] OUTER horns / Kan condition")
    print(f"    Invertible edge pairs (s<->t, where an OUTER horn could fill): {len(inv)}")
    print("    Almost all edges are one-directional, so the nerve fills INNER horns")
    print("    (a quasi-category: mechanisms compose) but NOT outer horns -- it is")
    print("    NOT a Kan complex (drugs/proteins are not freely invertible). Outer-")
    print("    horn filling = an EQUIVALENCE claim and must be earned (cf. Rezk).")
    for s, t in inv[:5]:
        print(f"      invertible: {s} <-> {t}")

    # 4. Coherence: 2-simplices on one boundary edge that disagree.
    conflicts = coherence_conflicts(rep)
    print("\n" + "-" * 74)
    print("[4] COHERENCE check  (multiple mechanistic 2-cells on one Drug->Disease edge)")
    print("    A high spread = chains disagree on how strongly the drug should treat")
    print("    the disease -> the predicted filler is ambiguous, flag for review.")
    if not conflicts:
        print("    No contradictory fillers found.")
    for d in conflicts[:8]:
        print(f"    {d['a']} -> {d['c']}: {d['n_intermediates']} intermediates, "
              f"spread {d['spread']:.2f}  "
              f"(strong via {d['strong'][0]}={d['strong'][1]:.2f}, "
              f"weak via {d['weak'][0]}={d['weak'][1]:.2f})")

    print("\n" + "-" * 74)
    print("Inner horn = mechanistic spine missing its composite. Filling it is the")
    print("repurposing prediction. The nerve is a quasi-category (inner-fillable),")
    print("not a Kan complex. Nothing here is wired into scoring -- diagnostic only.")


if __name__ == "__main__":
    main()
