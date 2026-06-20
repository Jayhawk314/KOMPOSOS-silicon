# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Activity Theory Integration for KOMPOSOS-III

Implements Engestrom's expanded Activity Theory as categorical structures:

Phase 1 - Activity Hierarchy (Leontiev):
  Three-level decomposition: Activity -> Action -> Operation
  Level transformations: automatization (action->operation),
  de-automatization (operation->action)

Phase 2 - Activity System (Engestrom):
  Six-component model: Subject, Object, Tool, Rule, Community, Division of Labor
  Four morphism classes: Production, Regulation, Distribution, Exchange

Phase 3 - Contradiction Detection:
  Four levels of contradiction as non-commuting diagrams in enriched categories

Phase 5 - Expansive Learning:
  Predict system-level transformations from accumulated contradictions

Mathematical basis:
  - Engestrom, Y. (1987). Learning by Expanding.
  - Leontiev, A.N. (1978). Activity, Consciousness, and Personality.
  - Lawvere, F.W. (1996). Unity and Identity of Opposites.
  - Robinson, M. (2017). Sheaves are the canonical data structure for sensor integration.

Category-theoretic correspondences:
  - Mediation = morphism composition
  - Contradictions = non-commuting diagrams
  - Expansive learning = natural transformation
  - ZPD = Kan extension
  - Boundary objects = profunctors (see boundary_profunctor.py)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .enriched_category import EnrichedCategory, MonoidalStructure, ACTIVITY_QUANTALE


# =============================================================================
# Phase 1: Activity Hierarchy (Leontiev)
# =============================================================================

class ActivityLevel(Enum):
    """Leontiev's three-level hierarchy of human activity."""
    OPERATION = "operation"   # Automated, condition-driven
    ACTION = "action"         # Conscious, goal-directed
    ACTIVITY = "activity"     # Collective, motive-driven


@dataclass
class LevelClassification:
    """Result of classifying a morphism into the activity hierarchy."""
    level: ActivityLevel
    confidence: float            # In [0, 1]
    features: Dict[str, float]   # Evidence features that led to classification


@dataclass
class LevelTransition:
    """A transition between activity levels."""
    source_level: ActivityLevel
    target_level: ActivityLevel
    trigger: str                 # What caused the transition
    morphism_id: str             # Which morphism transitioned


class ActivityHierarchy:
    """
    Classify morphisms into Leontiev's activity hierarchy.

    Uses metadata indicators to score each level. The highest-scoring
    level is returned with confidence = score / sum_of_scores.

    Indicator weights are configurable but default to balanced sets
    that cover common blockchain transaction metadata.
    """

    OPERATION_INDICATORS = {
        "regularity": 0.3,
        "automation_signature": 0.3,
        "low_variance": 0.2,
        "gas_optimization": 0.2,
    }

    ACTION_INDICATORS = {
        "irregular_timing": 0.25,
        "goal_achievement": 0.25,
        "tool_selection": 0.25,
        "responsive": 0.25,
    }

    ACTIVITY_INDICATORS = {
        "multi_action": 0.3,
        "motive_evidence": 0.3,
        "collective": 0.2,
        "sustained": 0.2,
    }

    def classify(self, morphism_metadata: Dict[str, Any]) -> LevelClassification:
        """
        Classify a morphism's activity level based on its metadata.

        Args:
            morphism_metadata: Dictionary of metadata fields. Keys matching
                indicator names are used as evidence (values in [0,1]).

        Returns:
            LevelClassification with the most likely level and confidence.
        """
        op_score = self._score_level(morphism_metadata, self.OPERATION_INDICATORS)
        act_score = self._score_level(morphism_metadata, self.ACTION_INDICATORS)
        actv_score = self._score_level(morphism_metadata, self.ACTIVITY_INDICATORS)

        total = op_score + act_score + actv_score
        if total < 1e-12:
            # No evidence — default to ACTION with low confidence
            return LevelClassification(
                level=ActivityLevel.ACTION,
                confidence=0.33,
                features={}
            )

        scores = {
            ActivityLevel.OPERATION: op_score,
            ActivityLevel.ACTION: act_score,
            ActivityLevel.ACTIVITY: actv_score,
        }

        best_level = max(scores, key=scores.get)
        confidence = scores[best_level] / total

        features = {}
        if best_level == ActivityLevel.OPERATION:
            features = self._extract_features(morphism_metadata, self.OPERATION_INDICATORS)
        elif best_level == ActivityLevel.ACTION:
            features = self._extract_features(morphism_metadata, self.ACTION_INDICATORS)
        else:
            features = self._extract_features(morphism_metadata, self.ACTIVITY_INDICATORS)

        return LevelClassification(
            level=best_level,
            confidence=round(confidence, 4),
            features=features
        )

    def detect_transitions(
        self, morphism_sequence: List[Dict[str, Any]]
    ) -> List[LevelTransition]:
        """
        Detect level transitions in a sequence of morphisms.

        Automatization: ACTION -> OPERATION (action becomes routine)
        De-automatization: OPERATION -> ACTION (routine breaks, requires conscious control)
        Motivation: ACTION -> ACTIVITY (action acquires independent motive)

        Args:
            morphism_sequence: List of morphism metadata dicts, ordered temporally.

        Returns:
            List of detected transitions.
        """
        if len(morphism_sequence) < 2:
            return []

        transitions = []
        prev_class = self.classify(morphism_sequence[0])

        for i in range(1, len(morphism_sequence)):
            curr_class = self.classify(morphism_sequence[i])

            if prev_class.level != curr_class.level:
                # Determine trigger based on transition direction
                trigger = self._infer_trigger(prev_class.level, curr_class.level)
                morphism_id = morphism_sequence[i].get("id", f"morphism_{i}")

                transitions.append(LevelTransition(
                    source_level=prev_class.level,
                    target_level=curr_class.level,
                    trigger=trigger,
                    morphism_id=morphism_id
                ))

            prev_class = curr_class

        return transitions

    def _score_level(
        self, metadata: Dict[str, Any], indicators: Dict[str, float]
    ) -> float:
        """Score a metadata dict against a set of weighted indicators."""
        score = 0.0
        for indicator, weight in indicators.items():
            value = metadata.get(indicator, 0.0)
            try:
                score += weight * float(value)
            except (TypeError, ValueError):
                # Non-numeric indicator — treat as boolean
                score += weight * (1.0 if value else 0.0)
        return score

    def _extract_features(
        self, metadata: Dict[str, Any], indicators: Dict[str, float]
    ) -> Dict[str, float]:
        """Extract indicator values from metadata."""
        features = {}
        for indicator in indicators:
            value = metadata.get(indicator, 0.0)
            try:
                features[indicator] = float(value)
            except (TypeError, ValueError):
                features[indicator] = 1.0 if value else 0.0
        return features

    def _infer_trigger(
        self, source: ActivityLevel, target: ActivityLevel
    ) -> str:
        """Infer the trigger for a level transition."""
        if source == ActivityLevel.ACTION and target == ActivityLevel.OPERATION:
            return "automatization"
        elif source == ActivityLevel.OPERATION and target == ActivityLevel.ACTION:
            return "de-automatization"
        elif source == ActivityLevel.ACTION and target == ActivityLevel.ACTIVITY:
            return "motive_acquisition"
        elif source == ActivityLevel.ACTIVITY and target == ActivityLevel.ACTION:
            return "motive_loss"
        elif source == ActivityLevel.OPERATION and target == ActivityLevel.ACTIVITY:
            return "double_promotion"
        elif source == ActivityLevel.ACTIVITY and target == ActivityLevel.OPERATION:
            return "full_automatization"
        return "level_change"


# =============================================================================
# Phase 2: Activity System (Engestrom)
# =============================================================================

class ActivityComponent(Enum):
    """The six components of Engestrom's expanded activity system."""
    SUBJECT = "subject"
    OBJECT = "object"
    TOOL = "tool"
    RULE = "rule"
    COMMUNITY = "community"
    DIVISION_OF_LABOR = "division_of_labor"


class MorphismClass(Enum):
    """The four classes of morphisms in an activity system."""
    PRODUCTION = "production"       # Subject -> Object (via Tool)
    REGULATION = "regulation"       # Subject -> Community (via Rules)
    DISTRIBUTION = "distribution"   # Community -> Object (via DoL)
    EXCHANGE = "exchange"           # Within any component


@dataclass
class ActivitySystemComponent:
    """A component of an activity system."""
    name: str
    component_type: ActivityComponent
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassifiedMorphism:
    """A morphism classified within the activity system structure."""
    source: str
    target: str
    morphism_class: MorphismClass
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ActivitySystem:
    """
    An Engestrom activity system as a structured category.

    Models the six-component expanded activity system with typed components
    and classified morphisms. Can be converted to an EnrichedCategory for
    quantitative analysis (contradiction detection via non-commutativity).
    """

    def __init__(self, name: str):
        self.name = name
        self.components: Dict[str, ActivitySystemComponent] = {}
        self.morphisms: List[ClassifiedMorphism] = []
        self._enriched_cache: Optional[EnrichedCategory] = None

    def add_component(
        self, name: str, component_type: ActivityComponent,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ActivitySystemComponent:
        """Add a component to the activity system."""
        comp = ActivitySystemComponent(
            name=name,
            component_type=component_type,
            metadata=metadata or {}
        )
        self.components[name] = comp
        self._enriched_cache = None
        return comp

    def add_morphism(
        self, source: str, target: str, morphism_class: MorphismClass,
        confidence: float = 1.0, metadata: Optional[Dict[str, Any]] = None
    ) -> ClassifiedMorphism:
        """Add a classified morphism to the activity system."""
        mor = ClassifiedMorphism(
            source=source, target=target,
            morphism_class=morphism_class,
            confidence=confidence,
            metadata=metadata or {}
        )
        self.morphisms.append(mor)
        self._enriched_cache = None
        return mor

    def get_components_by_type(
        self, component_type: ActivityComponent
    ) -> List[ActivitySystemComponent]:
        """Get all components of a given type."""
        return [c for c in self.components.values()
                if c.component_type == component_type]

    def get_morphisms_by_class(
        self, morphism_class: MorphismClass
    ) -> List[ClassifiedMorphism]:
        """Get all morphisms of a given class."""
        return [m for m in self.morphisms if m.morphism_class == morphism_class]

    def to_enriched_category(
        self, quantale: MonoidalStructure = ACTIVITY_QUANTALE
    ) -> EnrichedCategory:
        """
        Convert the activity system to an enriched category.

        Components become objects, morphism confidences become hom-values.
        This enables quantitative analysis via path weights and
        commutativity checking.
        """
        if self._enriched_cache is not None:
            return self._enriched_cache

        ec = EnrichedCategory(quantale)

        for name, comp in self.components.items():
            ec.add_object(name, {"component_type": comp.component_type.value,
                                 **comp.metadata})

        for mor in self.morphisms:
            ec.set_hom(mor.source, mor.target, mor.confidence)

        self._enriched_cache = ec
        return ec

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the activity system."""
        type_counts = {}
        for comp in self.components.values():
            key = comp.component_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        class_counts = {}
        for mor in self.morphisms:
            key = mor.morphism_class.value
            class_counts[key] = class_counts.get(key, 0) + 1

        return {
            "name": self.name,
            "num_components": len(self.components),
            "num_morphisms": len(self.morphisms),
            "component_types": type_counts,
            "morphism_classes": class_counts,
        }


class ActivitySystemBuilder:
    """
    Build an ActivitySystem from generic objects and morphisms.

    Uses type inference rules to classify objects as activity system
    components and morphisms into the four AT morphism classes.
    """

    TYPE_MAPPINGS: Dict[str, ActivityComponent] = {
        "address": ActivityComponent.SUBJECT,
        "entity": ActivityComponent.SUBJECT,
        "wallet": ActivityComponent.SUBJECT,
        "account": ActivityComponent.SUBJECT,
        "protocol": ActivityComponent.TOOL,
        "contract": ActivityComponent.TOOL,
        "dex": ActivityComponent.TOOL,
        "bridge": ActivityComponent.TOOL,
        "mixer": ActivityComponent.TOOL,
        "token": ActivityComponent.OBJECT,
        "asset": ActivityComponent.OBJECT,
        "goal": ActivityComponent.OBJECT,
        "pool": ActivityComponent.COMMUNITY,
        "network": ActivityComponent.COMMUNITY,
        "validator": ActivityComponent.COMMUNITY,
        "rule": ActivityComponent.RULE,
        "constraint": ActivityComponent.RULE,
        "governance": ActivityComponent.RULE,
        "role": ActivityComponent.DIVISION_OF_LABOR,
        "task": ActivityComponent.DIVISION_OF_LABOR,
    }

    # Morphism class inference based on (source_type, target_type)
    MORPHISM_MAPPINGS: Dict[Tuple[ActivityComponent, ActivityComponent], MorphismClass] = {
        (ActivityComponent.SUBJECT, ActivityComponent.OBJECT): MorphismClass.PRODUCTION,
        (ActivityComponent.SUBJECT, ActivityComponent.TOOL): MorphismClass.PRODUCTION,
        (ActivityComponent.TOOL, ActivityComponent.OBJECT): MorphismClass.PRODUCTION,
        (ActivityComponent.SUBJECT, ActivityComponent.COMMUNITY): MorphismClass.REGULATION,
        (ActivityComponent.RULE, ActivityComponent.SUBJECT): MorphismClass.REGULATION,
        (ActivityComponent.RULE, ActivityComponent.COMMUNITY): MorphismClass.REGULATION,
        (ActivityComponent.COMMUNITY, ActivityComponent.OBJECT): MorphismClass.DISTRIBUTION,
        (ActivityComponent.DIVISION_OF_LABOR, ActivityComponent.OBJECT): MorphismClass.DISTRIBUTION,
        (ActivityComponent.DIVISION_OF_LABOR, ActivityComponent.COMMUNITY): MorphismClass.DISTRIBUTION,
    }

    def __init__(self, hierarchy: Optional[ActivityHierarchy] = None):
        self.hierarchy = hierarchy

    def build(
        self, objects: List[Any], morphisms: List[Any],
        name: str = "system"
    ) -> ActivitySystem:
        """
        Build an ActivitySystem from lists of objects and morphisms.

        Objects should have .name and .type_name (or .metadata["type"]) attributes.
        Morphisms should have .source_name, .target_name, .confidence attributes.

        Args:
            objects: List of objects with name and type information.
            morphisms: List of morphisms with source, target, confidence.
            name: Name for the resulting activity system.

        Returns:
            A fully constructed ActivitySystem.
        """
        system = ActivitySystem(name)

        # Add components
        obj_types: Dict[str, ActivityComponent] = {}
        for obj in objects:
            obj_name = getattr(obj, "name", str(obj))
            comp_type = self._infer_component_type(obj)
            metadata = getattr(obj, "metadata", {}) or {}
            system.add_component(obj_name, comp_type, metadata)
            obj_types[obj_name] = comp_type

        # Add morphisms
        for mor in morphisms:
            source = getattr(mor, "source_name", "")
            target = getattr(mor, "target_name", "")
            confidence = getattr(mor, "confidence", 1.0)
            metadata = getattr(mor, "metadata", {}) or {}

            source_type = obj_types.get(source, ActivityComponent.SUBJECT)
            target_type = obj_types.get(target, ActivityComponent.OBJECT)
            mor_class = self._infer_morphism_class(source_type, target_type)

            # If hierarchy is available, add level classification to metadata
            if self.hierarchy:
                classification = self.hierarchy.classify(metadata)
                metadata = {**metadata, "activity_level": classification.level.value,
                            "level_confidence": classification.confidence}

            system.add_morphism(source, target, mor_class, confidence, metadata)

        return system

    def _infer_component_type(self, obj: Any) -> ActivityComponent:
        """Infer AT component type from object attributes."""
        # Try type_name attribute
        type_name = getattr(obj, "type_name", "")
        if type_name:
            lower = type_name.lower()
            for key, comp_type in self.TYPE_MAPPINGS.items():
                if key in lower:
                    return comp_type

        # Try metadata["type"]
        metadata = getattr(obj, "metadata", {}) or {}
        obj_type = str(metadata.get("type", "")).lower()
        if obj_type:
            for key, comp_type in self.TYPE_MAPPINGS.items():
                if key in obj_type:
                    return comp_type

        # Default to OBJECT
        return ActivityComponent.OBJECT

    def _infer_morphism_class(
        self, source_type: ActivityComponent, target_type: ActivityComponent
    ) -> MorphismClass:
        """Infer morphism class from source and target component types."""
        pair = (source_type, target_type)
        if pair in self.MORPHISM_MAPPINGS:
            return self.MORPHISM_MAPPINGS[pair]

        # Same type -> EXCHANGE
        if source_type == target_type:
            return MorphismClass.EXCHANGE

        # Default to PRODUCTION
        return MorphismClass.PRODUCTION


# =============================================================================
# Phase 3: Contradiction Detection
# =============================================================================

@dataclass
class Contradiction:
    """
    A contradiction detected in an activity system.

    Engestrom's four levels:
      1. Primary: within a single component (use-value vs exchange-value)
      2. Secondary: between components (misalignment)
      3. Tertiary: between existing and advanced form of the system
      4. Quaternary: between the system and neighboring systems
    """
    level: int                    # 1-4
    description: str
    components_involved: List[str]
    tension: float                # 0.0 = no tension, higher = more
    evidence: Dict[str, Any] = field(default_factory=dict)


class ContradictionDetector:
    """
    Detect contradictions as non-commuting diagrams in activity systems.

    Uses the enriched category representation to measure non-commutativity
    as a continuous tension metric. Higher tension indicates stronger
    structural contradiction.
    """

    def __init__(self, quantale: MonoidalStructure = ACTIVITY_QUANTALE):
        self.quantale = quantale

    def detect_all(self, system: ActivitySystem) -> List[Contradiction]:
        """Detect all levels of contradictions in a single system."""
        contradictions = []
        contradictions.extend(self.detect_primary(system))
        contradictions.extend(self.detect_secondary(system))
        return contradictions

    def detect_primary(self, system: ActivitySystem) -> List[Contradiction]:
        """
        Detect primary contradictions (within a single component type).

        Measured by variance of hom-values for morphisms within the same
        component type. High variance = internal tension.
        """
        contradictions = []
        enriched = system.to_enriched_category(self.quantale)

        for comp_type in ActivityComponent:
            components = system.get_components_by_type(comp_type)
            if len(components) < 2:
                continue

            # Collect all hom-values between components of the same type
            hom_values = []
            comp_names = [c.name for c in components]
            for i, name_a in enumerate(comp_names):
                for name_b in comp_names[i + 1:]:
                    h = enriched.get_hom(name_a, name_b)
                    if h is not None:
                        hom_values.append(float(h))
                    h_rev = enriched.get_hom(name_b, name_a)
                    if h_rev is not None:
                        hom_values.append(float(h_rev))

            if len(hom_values) < 2:
                continue

            # Variance as tension measure
            mean = sum(hom_values) / len(hom_values)
            variance = sum((v - mean) ** 2 for v in hom_values) / len(hom_values)
            tension = variance ** 0.5  # Standard deviation

            if tension > 0.1:
                contradictions.append(Contradiction(
                    level=1,
                    description=(
                        f"Primary contradiction within {comp_type.value}: "
                        f"high internal variance (std={tension:.3f})"
                    ),
                    components_involved=comp_names,
                    tension=round(tension, 4),
                    evidence={"hom_values": hom_values, "variance": variance}
                ))

        return contradictions

    def detect_secondary(self, system: ActivitySystem) -> List[Contradiction]:
        """
        Detect secondary contradictions (between components).

        Checks if production, regulation, and distribution triangles commute.
        Non-commutativity indicates structural misalignment between components.
        """
        contradictions = []
        enriched = system.to_enriched_category(self.quantale)

        # Check all pairs of paths between the same endpoints
        # Focus on the key AT triangles:
        # Production: Subject -> Tool -> Object vs Subject -> Object
        # Regulation: Subject -> Rule -> Community vs Subject -> Community
        # Distribution: Community -> DoL -> Object vs Community -> Object

        subjects = [c.name for c in system.get_components_by_type(ActivityComponent.SUBJECT)]
        objects = [c.name for c in system.get_components_by_type(ActivityComponent.OBJECT)]
        tools = [c.name for c in system.get_components_by_type(ActivityComponent.TOOL)]
        rules = [c.name for c in system.get_components_by_type(ActivityComponent.RULE)]
        communities = [c.name for c in system.get_components_by_type(ActivityComponent.COMMUNITY)]
        dol = [c.name for c in system.get_components_by_type(ActivityComponent.DIVISION_OF_LABOR)]

        # Production triangle: Subject -> Tool -> Object vs Subject -> Object
        for s in subjects:
            for t in tools:
                for o in objects:
                    path_mediated = [s, t, o]
                    path_direct = [s, o]
                    result = enriched.check_commutativity(path_mediated, path_direct)
                    if not result["commutes"] and result["tension"] > 0.1:
                        contradictions.append(Contradiction(
                            level=2,
                            description=(
                                f"Secondary contradiction in production: "
                                f"tool-mediated path ({s}->{t}->{o}) diverges from "
                                f"direct path ({s}->{o}), tension={result['tension']:.3f}"
                            ),
                            components_involved=[s, t, o],
                            tension=round(result["tension"], 4),
                            evidence=result
                        ))

        # Regulation triangle: Subject -> Rule -> Community vs Subject -> Community
        for s in subjects:
            for r in rules:
                for c in communities:
                    path_regulated = [s, r, c]
                    path_direct = [s, c]
                    result = enriched.check_commutativity(path_regulated, path_direct)
                    if not result["commutes"] and result["tension"] > 0.1:
                        contradictions.append(Contradiction(
                            level=2,
                            description=(
                                f"Secondary contradiction in regulation: "
                                f"rule-mediated path ({s}->{r}->{c}) diverges from "
                                f"direct path ({s}->{c}), tension={result['tension']:.3f}"
                            ),
                            components_involved=[s, r, c],
                            tension=round(result["tension"], 4),
                            evidence=result
                        ))

        # Distribution triangle: Community -> DoL -> Object vs Community -> Object
        for c in communities:
            for d in dol:
                for o in objects:
                    path_distributed = [c, d, o]
                    path_direct = [c, o]
                    result = enriched.check_commutativity(path_distributed, path_direct)
                    if not result["commutes"] and result["tension"] > 0.1:
                        contradictions.append(Contradiction(
                            level=2,
                            description=(
                                f"Secondary contradiction in distribution: "
                                f"labor-mediated path ({c}->{d}->{o}) diverges from "
                                f"direct path ({c}->{o}), tension={result['tension']:.3f}"
                            ),
                            components_involved=[c, d, o],
                            tension=round(result["tension"], 4),
                            evidence=result
                        ))

        return contradictions

    def detect_tertiary(
        self, old_system: ActivitySystem, new_system: ActivitySystem
    ) -> List[Contradiction]:
        """
        Detect tertiary contradictions between existing and advanced forms.

        Compares hom-values for shared components between old and new system.
        Divergence indicates tension between current and evolved practice.
        """
        contradictions = []
        old_enriched = old_system.to_enriched_category(self.quantale)
        new_enriched = new_system.to_enriched_category(self.quantale)

        # Find shared component names
        shared = set(old_system.components.keys()) & set(new_system.components.keys())

        for name_a in shared:
            for name_b in shared:
                if name_a == name_b:
                    continue
                old_hom = old_enriched.get_hom(name_a, name_b)
                new_hom = new_enriched.get_hom(name_a, name_b)

                if old_hom is None or new_hom is None:
                    continue

                try:
                    diff = abs(float(old_hom) - float(new_hom))
                    if diff > 0.2:
                        contradictions.append(Contradiction(
                            level=3,
                            description=(
                                f"Tertiary contradiction: relationship "
                                f"{name_a}->{name_b} changed significantly "
                                f"(old={old_hom:.3f}, new={new_hom:.3f})"
                            ),
                            components_involved=[name_a, name_b],
                            tension=round(diff, 4),
                            evidence={"old_hom": old_hom, "new_hom": new_hom}
                        ))
                except (TypeError, ValueError):
                    continue

        return contradictions

    def detect_quaternary(
        self, central: ActivitySystem, neighbors: List[ActivitySystem]
    ) -> List[Contradiction]:
        """
        Detect quaternary contradictions between central and neighboring systems.

        Finds shared components (potential boundary objects) and checks if
        they are used consistently across systems.
        """
        contradictions = []
        central_enriched = central.to_enriched_category(self.quantale)

        for neighbor in neighbors:
            neighbor_enriched = neighbor.to_enriched_category(self.quantale)
            shared = set(central.components.keys()) & set(neighbor.components.keys())

            for name in shared:
                # Check if the shared component has different roles
                central_type = central.components[name].component_type
                neighbor_type = neighbor.components[name].component_type

                if central_type != neighbor_type:
                    contradictions.append(Contradiction(
                        level=4,
                        description=(
                            f"Quaternary contradiction: '{name}' is "
                            f"{central_type.value} in {central.name} but "
                            f"{neighbor_type.value} in {neighbor.name}"
                        ),
                        components_involved=[name],
                        tension=1.0,
                        evidence={
                            "central_role": central_type.value,
                            "neighbor_role": neighbor_type.value,
                            "neighbor_system": neighbor.name
                        }
                    ))

                # Check if hom-patterns differ for this shared component
                central_homs = []
                neighbor_homs = []
                for other in shared:
                    if other == name:
                        continue
                    ch = central_enriched.get_hom(name, other)
                    nh = neighbor_enriched.get_hom(name, other)
                    if ch is not None:
                        central_homs.append(float(ch))
                    if nh is not None:
                        neighbor_homs.append(float(nh))

                if central_homs and neighbor_homs:
                    c_mean = sum(central_homs) / len(central_homs)
                    n_mean = sum(neighbor_homs) / len(neighbor_homs)
                    diff = abs(c_mean - n_mean)
                    if diff > 0.2:
                        contradictions.append(Contradiction(
                            level=4,
                            description=(
                                f"Quaternary contradiction: '{name}' used differently "
                                f"in {central.name} (mean_hom={c_mean:.3f}) vs "
                                f"{neighbor.name} (mean_hom={n_mean:.3f})"
                            ),
                            components_involved=[name],
                            tension=round(diff, 4),
                            evidence={
                                "central_mean": c_mean,
                                "neighbor_mean": n_mean,
                                "neighbor_system": neighbor.name
                            }
                        ))

        return contradictions


# =============================================================================
# Phase 5: Expansive Learning Detection
# =============================================================================

@dataclass
class ExpansiveLearningPrediction:
    """Prediction that an activity system will undergo qualitative transformation."""
    system_name: str
    predicted_phase: str             # One of Engestrom's 7 epistemic actions
    contradiction_drivers: List[Contradiction]
    transformation_probability: float  # In [0, 1]
    predicted_changes: Dict[str, str]  # component -> predicted change description


class ExpansiveLearningDetector:
    """
    Detect expansive learning cycles from contradiction accumulation.

    Engestrom's expansive learning cycle has 7 phases:
      1. Questioning, 2. Analysis, 3. Modeling, 4. Examining,
      5. Implementing, 6. Reflecting, 7. Consolidating

    When accumulated contradictions exceed thresholds, the system
    is predicted to undergo qualitative transformation.
    """

    TENSION_THRESHOLD = 0.6
    CRITICAL_MASS = 3

    PHASES = [
        "questioning", "analysis", "modeling", "examining",
        "implementing", "reflecting", "consolidating"
    ]

    def __init__(self, detector: Optional[ContradictionDetector] = None):
        self.detector = detector or ContradictionDetector()

    def assess(
        self, system: ActivitySystem,
        historical_contradictions: Optional[List[Contradiction]] = None
    ) -> ExpansiveLearningPrediction:
        """
        Assess whether a system is approaching expansive transformation.

        Args:
            system: The activity system to assess.
            historical_contradictions: Previously detected contradictions
                (accumulated over time). If None, detects current contradictions.

        Returns:
            ExpansiveLearningPrediction with transformation probability.
        """
        if historical_contradictions is None:
            contradictions = self.detector.detect_all(system)
        else:
            contradictions = historical_contradictions

        # Count secondary contradictions (the main drivers)
        secondary = [c for c in contradictions if c.level == 2]
        all_tensions = [c.tension for c in contradictions]

        # Transformation probability based on:
        # 1. Number of secondary contradictions vs critical mass
        # 2. Maximum tension vs threshold
        count_factor = min(1.0, len(secondary) / max(1, self.CRITICAL_MASS))
        tension_factor = 0.0
        if all_tensions:
            max_tension = max(all_tensions)
            tension_factor = min(1.0, max_tension / max(0.01, self.TENSION_THRESHOLD))

        probability = 0.5 * count_factor + 0.5 * tension_factor
        probability = round(min(1.0, probability), 4)

        # Predict phase based on probability
        phase_idx = min(int(probability * len(self.PHASES)), len(self.PHASES) - 1)
        predicted_phase = self.PHASES[phase_idx]

        # Predict which components will change (those involved in contradictions)
        predicted_changes: Dict[str, str] = {}
        for c in contradictions:
            for comp in c.components_involved:
                if comp not in predicted_changes:
                    predicted_changes[comp] = (
                        f"Under tension (level {c.level}): {c.description[:80]}"
                    )

        return ExpansiveLearningPrediction(
            system_name=system.name,
            predicted_phase=predicted_phase,
            contradiction_drivers=contradictions,
            transformation_probability=probability,
            predicted_changes=predicted_changes
        )

    def compare_systems(
        self, old: ActivitySystem, new: ActivitySystem
    ) -> Dict[str, Any]:
        """
        Check if transformation between old and new constitutes expansive learning.

        Expansive learning = structural relationships preserved (naturality)
        while components have qualitatively transformed.

        Returns:
            {
                "is_expansive": bool,
                "preserved_relationships": int,
                "transformed_components": int,
                "total_shared": int,
                "expansion_score": float
            }
        """
        shared = set(old.components.keys()) & set(new.components.keys())

        if not shared:
            return {
                "is_expansive": False,
                "preserved_relationships": 0,
                "transformed_components": 0,
                "total_shared": 0,
                "expansion_score": 0.0
            }

        old_enriched = old.to_enriched_category(self.detector.quantale)
        new_enriched = new.to_enriched_category(self.detector.quantale)

        preserved = 0
        transformed = 0
        total_pairs = 0

        shared_list = list(shared)
        for i, a in enumerate(shared_list):
            for b in shared_list[i + 1:]:
                total_pairs += 1
                old_h = old_enriched.get_hom(a, b)
                new_h = new_enriched.get_hom(a, b)

                if old_h is not None and new_h is not None:
                    try:
                        diff = abs(float(old_h) - float(new_h))
                        if diff < 0.1:
                            preserved += 1
                        else:
                            transformed += 1
                    except (TypeError, ValueError):
                        if old_h == new_h:
                            preserved += 1
                        else:
                            transformed += 1
                elif old_h is None and new_h is None:
                    preserved += 1
                else:
                    transformed += 1

        # Check for component type changes
        type_changes = 0
        for name in shared:
            if old.components[name].component_type != new.components[name].component_type:
                type_changes += 1

        # Expansive = some transformation happened but structure was mostly preserved
        has_transformation = transformed > 0 or type_changes > 0
        mostly_preserved = total_pairs == 0 or preserved >= total_pairs * 0.5

        expansion_score = 0.0
        if total_pairs > 0:
            preservation_ratio = preserved / total_pairs
            transformation_ratio = transformed / total_pairs
            # Best score when ~30% transformed and ~70% preserved
            expansion_score = min(preservation_ratio, 1.0) * min(transformation_ratio * 3, 1.0)
            expansion_score = round(expansion_score, 4)

        return {
            "is_expansive": has_transformation and mostly_preserved,
            "preserved_relationships": preserved,
            "transformed_components": transformed + type_changes,
            "total_shared": len(shared),
            "expansion_score": expansion_score
        }
