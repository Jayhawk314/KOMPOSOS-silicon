# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Lightweight world-model shell.

This is intentionally not an LLM and not a simulator. It is the small transition
layer OPERADUM needs when the question is "what action should we take next?"

    WorldState + WorldAction -> WorldPrediction(next_state, figures, evidence)

The shell can be backed by rules, cached scores, KOMPOSOS graph queries, lab
results, or any other specialized tool. OPERADUM then ranks the possible next
actions with the active figure profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .core.enrichment import GENERAL_FIGURES, ResourceMonoid, _meets_minimum
from .core.operad import Operad
from .core.types import ResourceValue, Spec
from .wright.engine import Wright


Facts = Dict[str, Any]
Evidence = Tuple[str, ...]


@dataclass(frozen=True)
class WorldState:
    """A compact snapshot of a domain state.

    `facts` are arbitrary structured values. `figures` are numeric design
    figures compatible with OPERADUM's resource/figure profiles. `evidence`
    records the trace that produced the state.
    """

    label: str = "state"
    facts: Mapping[str, Any] = field(default_factory=dict)
    figures: Mapping[str, float] = field(default_factory=dict)
    evidence: Evidence = field(default_factory=tuple)

    def with_updates(
        self,
        *,
        label: Optional[str] = None,
        facts: Optional[Mapping[str, Any]] = None,
        figures: Optional[Mapping[str, float]] = None,
        evidence: Iterable[str] = (),
    ) -> "WorldState":
        """Return a new state with shallow-merged facts/figures and appended evidence."""
        merged_facts = dict(self.facts)
        if facts:
            merged_facts.update(facts)

        merged_figures = dict(self.figures)
        if figures:
            merged_figures.update({k: float(v) for k, v in figures.items()})

        return WorldState(
            label=label or self.label,
            facts=merged_facts,
            figures=merged_figures,
            evidence=tuple(self.evidence) + tuple(evidence),
        )


@dataclass(frozen=True)
class WorldPrediction:
    """The predicted effect of one action from one state."""

    action: str
    before: WorldState
    after: WorldState
    figures: ResourceValue = field(default_factory=dict)
    confidence: float = 1.0
    evidence: Evidence = field(default_factory=tuple)
    explanation: str = ""

    @property
    def cost(self) -> ResourceValue:
        """Figures used by OPERADUM to rank this prediction."""
        out = {k: float(v) for k, v in self.figures.items()}
        out.setdefault("confidence", float(self.confidence))
        return out


TransitionFn = Callable[[WorldState], WorldPrediction]
PreconditionFn = Callable[[WorldState], bool]


@dataclass(frozen=True)
class WorldAction:
    """A named transition rule."""

    name: str
    transition: TransitionFn
    precondition: Optional[PreconditionFn] = None
    description: str = ""

    def applicable(self, state: WorldState) -> bool:
        return True if self.precondition is None else bool(self.precondition(state))

    def predict(self, state: WorldState) -> WorldPrediction:
        if not self.applicable(state):
            raise ValueError(f"World action {self.name!r} is not applicable to {state.label!r}")
        return self.transition(state)


@dataclass(frozen=True)
class ActionChoice:
    """The result of asking OPERADUM to choose one world-model action."""

    prediction: WorldPrediction
    wiring: str
    figures: ResourceValue


class RuleWorldModel:
    """A deterministic, lightweight world model made from named transition rules."""

    def __init__(self, name: str = "world-model"):
        self.name = name
        self._actions: Dict[str, WorldAction] = {}

    @property
    def actions(self) -> Tuple[WorldAction, ...]:
        return tuple(self._actions.values())

    def register(self, action: WorldAction) -> "RuleWorldModel":
        if action.name in self._actions:
            raise ValueError(f"World action already registered: {action.name}")
        self._actions[action.name] = action
        return self

    def action(
        self,
        name: str,
        *,
        precondition: Optional[PreconditionFn] = None,
        description: str = "",
    ) -> Callable[[TransitionFn], TransitionFn]:
        """Decorator for registering a transition function."""
        def decorate(fn: TransitionFn) -> TransitionFn:
            self.register(WorldAction(name, fn, precondition, description))
            return fn
        return decorate

    def predict(self, state: WorldState, action_name: str) -> WorldPrediction:
        return self._actions[action_name].predict(state)

    def predictions(self, state: WorldState) -> List[WorldPrediction]:
        """All applicable one-step predictions from `state`."""
        out: List[WorldPrediction] = []
        for action in self.actions:
            if action.applicable(state):
                out.append(action.predict(state))
        return out

    def action_operad(
        self,
        state: WorldState,
        *,
        monoid: ResourceMonoid = GENERAL_FIGURES,
        output: str = "WorldPrediction",
    ) -> Operad:
        """Represent applicable one-step actions as zero-arity OPERADUM operations."""
        op = Operad(f"{self.name}-actions", monoid=monoid)
        op.add_colour(output)
        for prediction in self.predictions(state):
            op.add_op(
                _operation_name(prediction.action),
                [],
                output,
                cost=prediction.cost,
                fn=lambda _p=prediction: _p,
                action=prediction.action,
                explanation=prediction.explanation,
            )
        return op

    def choose(
        self,
        state: WorldState,
        *,
        monoid: ResourceMonoid = GENERAL_FIGURES,
        budget: Optional[ResourceValue] = None,
        requirements: Optional[ResourceValue] = None,
    ) -> Optional[ActionChoice]:
        """Choose the best one-step action under an OPERADUM figure profile."""
        op = self.action_operad(state, monoid=monoid)
        result = Wright(op, max_depth=1).optimize(
            Spec((), "WorldPrediction", budget=budget, requirements=requirements)
        )
        if not result.buildable or result.construction is None:
            return None
        prediction = result.construction.artifact()
        return ActionChoice(
            prediction=prediction,
            wiring=result.construction.wiring,
            figures=result.construction.cost,
        )

    def feasible_predictions(
        self,
        state: WorldState,
        *,
        budget: Optional[ResourceValue] = None,
        requirements: Optional[ResourceValue] = None,
    ) -> List[WorldPrediction]:
        """Filter predictions by upper-bound budgets and lower-bound requirements."""
        out = []
        for prediction in self.predictions(state):
            figures = prediction.cost
            if budget is not None and not GENERAL_FIGURES.compare(figures, budget):
                continue
            if requirements is not None and not _meets_minimum(figures, requirements):
                continue
            out.append(prediction)
        return out


def _operation_name(action: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", action.strip()).strip("_")
    return name or "action"

