from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


SEMANTIC_ACTION_ROLES = frozenset(
    {
        "presentation_capability",
        "state_mutation",
        "navigation",
        "guarded_navigation",
        "form_completion",
        "commit",
        "unknown",
    }
)

_MAX_FACT_ENTRIES = 8


def normalize_semantic_id(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return normalized.strip("_")


def _bounded_strings(value: object, *, normalize: bool = True) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:_MAX_FACT_ENTRIES]:
        normalized = normalize_semantic_id(item) if normalize else str(item).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _bounded_evidence(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:_MAX_FACT_ENTRIES]:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _role(value: object) -> str:
    normalized = normalize_semantic_id(value)
    return normalized if normalized in SEMANTIC_ACTION_ROLES else "unknown"


def _location(value: object) -> str:
    return normalize_semantic_id(value)


def _confidence(value: object) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return confidence


@dataclass(frozen=True)
class SemanticObservation:
    action_role: str
    source_location: str
    target_location: str
    completion_facts: list[str] = field(default_factory=list)
    candidate_required_facts: list[str] = field(default_factory=list)
    preserved_facts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_role": self.action_role,
            "source_location": self.source_location,
            "target_location": self.target_location,
            "completion_facts": list(self.completion_facts),
            "candidate_required_facts": list(self.candidate_required_facts),
            "preserved_facts": list(self.preserved_facts),
            "evidence": list(self.evidence),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SemanticAction:
    action_id: str
    action_name: str
    action_role: str
    source_location: str
    target_location: str
    required_facts: list[str] = field(default_factory=list)
    added_facts: list[str] = field(default_factory=list)
    removed_facts: list[str] = field(default_factory=list)
    preserved_facts: list[str] = field(default_factory=list)
    raw_edge_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "action_role": self.action_role,
            "source_location": self.source_location,
            "target_location": self.target_location,
            "required_facts": list(self.required_facts),
            "added_facts": list(self.added_facts),
            "removed_facts": list(self.removed_facts),
            "preserved_facts": list(self.preserved_facts),
            "raw_edge_ids": list(self.raw_edge_ids),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class SemanticPlanningGraph:
    start_location: str
    locations: list[str]
    capability_facts: list[str]
    business_facts: list[str]
    initial_business_facts: list[str]
    actions: list[SemanticAction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_location": self.start_location,
            "locations": list(self.locations),
            "capability_facts": list(self.capability_facts),
            "business_facts": list(self.business_facts),
            "initial_business_facts": list(self.initial_business_facts),
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class SemanticProjectionReport:
    included_raw_edge_ids: list[str]
    excluded_edges: list[dict[str, Any]]
    uncertain_preconditions: list[dict[str, Any]]
    fact_provenance: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "included_raw_edge_ids": list(self.included_raw_edge_ids),
            "excluded_edges": [dict(item) for item in self.excluded_edges],
            "uncertain_preconditions": [dict(item) for item in self.uncertain_preconditions],
            "fact_provenance": [dict(item) for item in self.fact_provenance],
        }


def semantic_observation_from_dict(
    data: dict[str, Any] | None,
) -> SemanticObservation | None:
    if data is None or not isinstance(data, dict):
        return None
    return SemanticObservation(
        action_role=_role(data.get("action_role", "unknown")),
        source_location=_location(data.get("source_location", "")),
        target_location=_location(data.get("target_location", "")),
        completion_facts=_bounded_strings(data.get("completion_facts", [])),
        candidate_required_facts=_bounded_strings(
            data.get("candidate_required_facts", [])
        ),
        preserved_facts=_bounded_strings(data.get("preserved_facts", [])),
        evidence=_bounded_evidence(data.get("evidence", data.get("semantic_evidence", []))),
        confidence=_confidence(data.get("confidence", data.get("semantic_confidence"))),
    )


def semantic_action_from_dict(data: dict[str, Any]) -> SemanticAction:
    return SemanticAction(
        action_id=normalize_semantic_id(data.get("action_id", "")),
        action_name=normalize_semantic_id(data.get("action_name", "")),
        action_role=_role(data.get("action_role", "unknown")),
        source_location=_location(data.get("source_location", "")),
        target_location=_location(data.get("target_location", "")),
        required_facts=_bounded_strings(data.get("required_facts", [])),
        added_facts=_bounded_strings(data.get("added_facts", [])),
        removed_facts=_bounded_strings(data.get("removed_facts", [])),
        preserved_facts=_bounded_strings(data.get("preserved_facts", [])),
        raw_edge_ids=_bounded_strings(data.get("raw_edge_ids", []), normalize=False),
        evidence=_bounded_evidence(data.get("evidence", [])),
    )


def semantic_planning_graph_from_dict(data: dict[str, Any]) -> SemanticPlanningGraph:
    return SemanticPlanningGraph(
        start_location=_location(data.get("start_location", "")),
        locations=_bounded_strings(data.get("locations", [])),
        capability_facts=_bounded_strings(data.get("capability_facts", [])),
        business_facts=_bounded_strings(data.get("business_facts", [])),
        initial_business_facts=_bounded_strings(data.get("initial_business_facts", [])),
        actions=[
            semantic_action_from_dict(item)
            for item in data.get("actions", [])
            if isinstance(item, dict)
        ],
    )
