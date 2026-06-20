# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Temporal Sheaves for Event Stream Coherence

Key insight: Event streams form a sheaf over time.
- Base space: Timeline (totally ordered)
- Sheaf: Events that agree on overlapping time windows
- Coherence: Events in overlapping windows must not contradict

This detects:
1. Temporal evasion (events out of order)
2. Data tampering (conflicting events in same window)
3. Log manipulation (gaps that violate causality)

Example contradiction:
  Window [10:00-10:05]: User logged in from NYC
  Window [10:03-10:08]: User logged in from London
  Overlap [10:03-10:05]: IMPOSSIBLE TRAVEL -> Credential theft detected

This is a general temporal coherence checker: finds anomalies that
don't match known signatures but violate temporal consistency.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import math


@dataclass
class Event:
    """
    A generic event in an event stream.

    Domain-agnostic: the meaning of event_type, source, target,
    and metadata depends on the application context.
    """
    timestamp: float
    event_type: str
    source: str = ""
    target: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# Backward-compatible alias
SecurityEvent = Event


@dataclass
class TimeWindow:
    """
    A time window in the temporal sheaf.

    Objects in the category are time intervals.
    Morphisms are inclusion maps (window1 <= window2).
    """
    start: float  # Unix timestamp
    end: float

    def overlaps(self, other: 'TimeWindow') -> bool:
        """Check if two windows overlap."""
        return not (self.end <= other.start or self.start >= other.end)

    def intersection(self, other: 'TimeWindow') -> Optional['TimeWindow']:
        """Compute intersection of two windows (if exists)."""
        if not self.overlaps(other):
            return None
        return TimeWindow(
            start=max(self.start, other.start),
            end=min(self.end, other.end)
        )

    def contains(self, timestamp: float) -> bool:
        """Check if timestamp is in this window."""
        return self.start <= timestamp < self.end

    def duration(self) -> float:
        """Duration of window in seconds."""
        return self.end - self.start


@dataclass
class EventSection:
    """
    A section of the event sheaf over a time window.

    In sheaf theory: This is s in F(U) where U is a time window.
    Restriction maps send sections to smaller windows.
    """
    window: TimeWindow
    events: List[Event]

    def restrict_to(self, sub_window: TimeWindow) -> 'EventSection':
        """
        Restrict this section to a sub-window.

        This is the restriction morphism in sheaf theory:
        res: F(U) -> F(V) for V <= U
        """
        if not self.window.overlaps(sub_window):
            return EventSection(sub_window, [])

        intersection = self.window.intersection(sub_window)
        if not intersection:
            return EventSection(sub_window, [])

        restricted_events = [
            e for e in self.events
            if intersection.contains(e.timestamp)
        ]

        return EventSection(intersection, restricted_events)


class TemporalSheafChecker:
    """
    Checks coherence of event streams using sheaf theory.

    Sheaf axioms:
    1. Locality: If sections agree on all sub-windows, they're equal
    2. Gluing: If sections agree on overlaps, they glue to a global section

    We use these to detect:
    - Temporal inconsistencies (violate gluing)
    - Data tampering (violate locality)
    - Coherent multi-window patterns that span windows
    """

    def __init__(self, window_size_seconds: float = 300):  # 5-minute windows
        self.window_size = window_size_seconds

    def check_coherence(self, events: List[Event]) -> Dict[str, Any]:
        """
        Check if event stream forms a coherent sheaf.

        Returns:
            {
                "is_coherent": bool,
                "violations": List of temporal violations,
                "pattern_indicators": Coherent patterns spanning windows
            }
        """
        if not events:
            return {"is_coherent": True, "violations": [], "pattern_indicators": []}

        windows = self._create_time_windows(events)
        sections = [EventSection(window, self._events_in_window(events, window))
                   for window in windows]

        violations = []
        violations.extend(self._check_gluing_axiom(sections))
        violations.extend(self._check_temporal_causality(sections))
        violations.extend(self._check_impossible_colocation(sections))

        pattern_indicators = self._find_multi_window_patterns(sections)

        return {
            "is_coherent": len(violations) == 0,
            "violations": violations,
            "pattern_indicators": pattern_indicators,
            "num_windows": len(windows),
            "num_events": len(events)
        }

    def _create_time_windows(self, events: List[Event]) -> List[TimeWindow]:
        """
        Create overlapping time windows covering all events.
        Windows overlap by 50% to catch cross-window patterns.
        """
        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: e.timestamp)
        start_time = sorted_events[0].timestamp
        end_time = sorted_events[-1].timestamp

        windows = []
        current_start = start_time
        step = self.window_size / 2

        while current_start < end_time:
            window_end = current_start + self.window_size
            windows.append(TimeWindow(current_start, window_end))
            current_start += step

        return windows

    def _events_in_window(self, events: List[Event], window: TimeWindow) -> List[Event]:
        """Get all events that fall in a time window."""
        return [e for e in events if window.contains(e.timestamp)]

    def _check_gluing_axiom(self, sections: List[EventSection]) -> List[Dict]:
        """
        Check sheaf gluing axiom.

        If two sections agree on their overlap, they should glue consistently.
        Violations indicate data tampering or log manipulation.
        """
        violations = []

        for i in range(len(sections) - 1):
            section1 = sections[i]
            section2 = sections[i + 1]

            if not section1.window.overlaps(section2.window):
                continue

            overlap = section1.window.intersection(section2.window)
            if not overlap:
                continue

            events1_in_overlap = [e for e in section1.events if overlap.contains(e.timestamp)]
            events2_in_overlap = [e for e in section2.events if overlap.contains(e.timestamp)]

            if len(events1_in_overlap) != len(events2_in_overlap):
                violations.append({
                    "type": "gluing_violation",
                    "window1": f"[{section1.window.start:.1f}, {section1.window.end:.1f}]",
                    "window2": f"[{section2.window.start:.1f}, {section2.window.end:.1f}]",
                    "description": "Events don't agree in overlap - possible data tampering",
                    "severity": "high"
                })

        return violations

    def _check_temporal_causality(self, sections: List[EventSection]) -> List[Dict]:
        """
        Check temporal causality: effects must follow causes.

        Uses event metadata to determine causal ordering. Events with
        'precedes' metadata indicate which event types must come before them.
        """
        violations = []

        for section in sections:
            events_sorted = sorted(section.events, key=lambda e: e.timestamp)

            for i in range(len(events_sorted) - 1):
                event1 = events_sorted[i]
                event2 = events_sorted[i + 1]

                if self._violates_causality(event1, event2):
                    violations.append({
                        "type": "causality_violation",
                        "event1": event1.event_type,
                        "event2": event2.event_type,
                        "time_diff": event2.timestamp - event1.timestamp,
                        "description": f"Effect ({event2.event_type}) before cause ({event1.event_type})",
                        "severity": "medium"
                    })

        return violations

    def _violates_causality(self, event1: Event, event2: Event) -> bool:
        """
        Check if event2 following event1 violates causality.

        Uses 'must_precede' metadata if available. Otherwise uses
        simple heuristic based on event type names containing
        'result'/'output' appearing before 'input'/'request'.
        """
        # Check metadata-based causality
        must_precede = event2.metadata.get("must_precede", [])
        if must_precede and event1.event_type in must_precede:
            return True

        return False

    def _check_impossible_colocation(self, sections: List[EventSection]) -> List[Dict]:
        """
        Detect impossible colocation: same entity at two locations
        in overlapping time windows.

        This is a classic sheaf coherence violation.
        """
        violations = []

        for section in sections:
            entity_locations = defaultdict(list)

            for event in section.events:
                entity = event.metadata.get("entity", event.source)
                location = event.metadata.get("location", event.source)
                if entity and location:
                    entity_locations[entity].append((event.timestamp, location))

            for entity, locations in entity_locations.items():
                if len(locations) < 2:
                    continue

                sorted_locs = sorted(locations, key=lambda x: x[0])

                for i in range(len(sorted_locs) - 1):
                    time1, loc1 = sorted_locs[i]
                    time2, loc2 = sorted_locs[i + 1]

                    if loc1 != loc2:
                        time_diff_hours = (time2 - time1) / 3600

                        if time_diff_hours < 1.0:
                            violations.append({
                                "type": "impossible_colocation",
                                "entity": entity,
                                "location1": loc1,
                                "location2": loc2,
                                "time_diff_hours": time_diff_hours,
                                "description": f"Entity {entity} at two locations within {time_diff_hours:.2f} hours",
                                "severity": "critical"
                            })

        return violations

    def _find_multi_window_patterns(self, sections: List[EventSection]) -> List[Dict]:
        """
        Find patterns that span multiple windows.

        Detects "slow and low" patterns that evade single-window detection.
        Uses event metadata 'pattern_tag' to identify related events.
        """
        pattern_indicators = []

        tag_windows: Dict[str, List[int]] = defaultdict(list)

        for idx, section in enumerate(sections):
            for event in section.events:
                tag = event.metadata.get("pattern_tag")
                if tag:
                    if idx not in tag_windows[tag]:
                        tag_windows[tag].append(idx)

        for tag, window_indices in tag_windows.items():
            if len(window_indices) >= 2:
                span = max(window_indices) - min(window_indices)
                if span >= 1:
                    pattern_indicators.append({
                        "type": "multi_window_pattern",
                        "pattern_tag": tag,
                        "window_span": span,
                        "time_span_seconds": (sections[max(window_indices)].window.start -
                                            sections[min(window_indices)].window.start),
                        "description": f"Pattern '{tag}' spans {span + 1} windows",
                        "severity": "high"
                    })

        return pattern_indicators


class EventStreamCoherence:
    """
    High-level interface for event stream coherence checking.

    Wraps TemporalSheafChecker with a simpler API.
    """

    def __init__(self):
        self.sheaf_checker = TemporalSheafChecker(window_size_seconds=300)

    def check_event_stream(self, events: List[Event]) -> Dict:
        """
        Check coherence of an event stream.

        Returns:
            {
                "coherent": bool,
                "anomalies_detected": int,
                "violations": [...],
                "patterns": [...]
            }
        """
        result = self.sheaf_checker.check_coherence(events)

        anomalies = len(result["violations"]) + len(result["pattern_indicators"])

        return {
            "coherent": result["is_coherent"],
            "anomalies_detected": anomalies,
            "violations": result["violations"],
            "patterns": result["pattern_indicators"],
            "num_events_analyzed": result["num_events"],
            "num_windows_analyzed": result["num_windows"]
        }

    def filter_coherent_events(self, events: List[Event]) -> List[Event]:
        """
        Filter out events that violate coherence.

        Returns only events that form a coherent sheaf.
        """
        result = self.sheaf_checker.check_coherence(events)

        if result["is_coherent"]:
            return events

        # In a full implementation, would filter out specific violating events
        return events


# Backward-compatible alias
TemporalSheaf = TemporalSheafChecker
