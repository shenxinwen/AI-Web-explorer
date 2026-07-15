from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "web-capability-graph-v1"


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


@dataclass(frozen=True)
class Evidence:
    source: str
    selector: str | None = None
    text_sample: str | None = None
    url: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "selector": self.selector,
            "text_sample": self.text_sample,
            "url": self.url,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PageFrame:
    page_id: str
    page_type: str
    url: str
    url_pattern: str
    title: str
    heading: str | None = None
    signature_hints: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_type": self.page_type,
            "url": self.url,
            "url_pattern": self.url_pattern,
            "title": self.title,
            "heading": self.heading,
            "signature_hints": dict(self.signature_hints),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class StateIndicator:
    name: str
    value: bool | str | int
    role: str
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "role": self.role,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class InputSlot:
    name: str
    kind: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
        }


@dataclass(frozen=True)
class GroundingPattern:
    locator_strategy: str
    locator_pattern: str | None = None
    target_selection_policy: str = "single"
    field_bindings: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "locator_strategy": self.locator_strategy,
            "locator_pattern": self.locator_pattern,
            "target_selection_policy": self.target_selection_policy,
            "field_bindings": dict(self.field_bindings),
        }


@dataclass(frozen=True)
class AvailabilityCondition:
    required_page_type: str
    required_state_indicators: dict[str, Any] = field(default_factory=dict)
    required_target_presence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_page_type": self.required_page_type,
            "required_state_indicators": dict(self.required_state_indicators),
            "required_target_presence": self.required_target_presence,
        }


@dataclass(frozen=True)
class StateChangeHint:
    field: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class Capability:
    capability_id: str
    semantic_action: str
    action_kind: str
    target_type: str | None
    target_role: str | None
    grounding: GroundingPattern
    availability: AvailabilityCondition
    input_schema: list[InputSlot] = field(default_factory=list)
    expected_delta: list[StateChangeHint] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "semantic_action": self.semantic_action,
            "action_kind": self.action_kind,
            "target_type": self.target_type,
            "target_role": self.target_role,
            "input_schema": _list_to_dict(self.input_schema),
            "grounding": self.grounding.to_dict(),
            "availability": self.availability.to_dict(),
            "expected_delta": _list_to_dict(self.expected_delta),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ObservedDelta:
    field: str
    before: Any
    after: Any
    delta_type: str
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "delta_type": self.delta_type,
            "confidence": self.confidence,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ExecutionTrace:
    concrete_action_kind: str
    concrete_locator: str | None
    concrete_target_sample: str | None
    input_values_used: dict[str, str]
    before_observation_id: str
    after_observation_id: str
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "concrete_action_kind": self.concrete_action_kind,
            "concrete_locator": self.concrete_locator,
            "concrete_target_sample": self.concrete_target_sample,
            "input_values_used": dict(self.input_values_used),
            "before_observation_id": self.before_observation_id,
            "after_observation_id": self.after_observation_id,
            "success": self.success,
            "error": self.error,
        }


@dataclass(frozen=True)
class CapabilityTransition:
    transition_id: str
    source_state_id: str
    capability_id: str
    target_state_id: str
    transition_kind: str
    observed_delta: list[ObservedDelta]
    execution_trace: ExecutionTrace
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "source_state_id": self.source_state_id,
            "capability_id": self.capability_id,
            "target_state_id": self.target_state_id,
            "transition_kind": self.transition_kind,
            "observed_delta": _list_to_dict(self.observed_delta),
            "execution_trace": self.execution_trace.to_dict(),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class SemanticPageState:
    state_id: str
    page_frame: PageFrame
    state_indicators: list[StateIndicator]
    capabilities: list[Capability]
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "page_frame": self.page_frame.to_dict(),
            "state_indicators": _list_to_dict(self.state_indicators),
            "capabilities": _list_to_dict(self.capabilities),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class WebCapabilityGraph:
    app: str
    start_state: str
    total_steps_completed: int
    states: list[SemanticPageState]
    transitions: list[CapabilityTransition]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "app": self.app,
                "start_state": self.start_state,
                "total_steps_completed": self.total_steps_completed,
            },
            "states": _list_to_dict(self.states),
            "transitions": _list_to_dict(self.transitions),
        }
