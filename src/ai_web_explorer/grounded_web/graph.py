from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import (
    Capability,
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
    StateIndicator,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation

WEB_KOBE_SCHEMA_VERSION = "web-kobe-graph-v1"


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items
    ]


@dataclass(frozen=True)
class ActionTarget:
    target_type: str
    occurrence: str
    role: str
    structural_pattern: str | None = None
    representative_locator: str | None = None
    supported_capabilities: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "occurrence": self.occurrence,
            "role": self.role,
            "structural_pattern": self.structural_pattern,
            "representative_locator": self.representative_locator,
            "supported_capabilities": list(self.supported_capabilities),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ReferenceObservation:
    url: str
    title: str
    screenshot_path: str | None = None
    dom_summary: str | None = None
    accessibility_summary: str | None = None
    observation_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "screenshot_path": self.screenshot_path,
            "dom_summary": self.dom_summary,
            "accessibility_summary": self.accessibility_summary,
            "observation_hash": self.observation_hash,
        }


@dataclass(frozen=True)
class BrowserAction:
    action_kind: str
    locator: str | None
    semantic_id: str
    input_values: dict[str, str] = field(default_factory=dict)
    description: str | None = None
    action_label: str | None = None
    canonical_action_name: str | None = None
    naming_provenance: dict[str, Any] | None = None
    supporting_facts: list[str] = field(default_factory=list)
    execution_policy: str = "single_instance"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_kind": self.action_kind,
            "locator": self.locator,
            "semantic_id": self.semantic_id,
            "input_values": dict(self.input_values),
            "description": self.description,
            "action_label": self.action_label,
            "canonical_action_name": self.canonical_action_name,
            "naming_provenance": (
                dict(self.naming_provenance)
                if self.naming_provenance is not None
                else None
            ),
            "supporting_facts": list(self.supporting_facts),
            "execution_policy": self.execution_policy,
        }


@dataclass(frozen=True)
class PddlActionHint:
    action_name: str
    preconditions: list[str] = field(default_factory=list)
    add_effects: list[str] = field(default_factory=list)
    del_effects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_name": self.action_name,
            "preconditions": list(self.preconditions),
            "add_effects": list(self.add_effects),
            "del_effects": list(self.del_effects),
        }


@dataclass(frozen=True)
class BusinessAffordance:
    action_name: str
    label: str | None = None
    relevance_hint: str = "unknown"
    target_hint: str | None = None
    execution_policy: str = "single_instance"
    source: str = "vlm"
    confidence: float | None = None
    supporting_facts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_name": self.action_name,
            "label": self.label,
            "relevance_hint": self.relevance_hint,
            "target_hint": self.target_hint,
            "execution_policy": self.execution_policy,
            "source": self.source,
            "confidence": self.confidence,
            "supporting_facts": list(self.supporting_facts),
        }


@dataclass(frozen=True)
class WebKobeNode:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    state_indicators: list[StateIndicator] = field(default_factory=list)
    action_targets: list[ActionTarget] = field(default_factory=list)
    interactable_elements: list[dict[str, Any]] = field(default_factory=list)
    business_affordances: list[BusinessAffordance] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    reference_observation: ReferenceObservation | None = None
    visit_count: int = 0
    status: str = "verified"
    evidence: list[Evidence] = field(default_factory=list)
    node_label: str | None = None
    state_summary: str | None = None
    naming_provenance: dict[str, Any] | None = None
    planning_state: PlanningState | None = None
    semantic_location_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "page_description": self.page_description,
            "page_frame": self.page_frame.to_dict(),
            "state_schema": {
                key: list(values) for key, values in self.state_schema.items()
            },
            "last_state_snapshot": dict(self.last_state_snapshot),
            "state_indicators": _list_to_dict(self.state_indicators),
            "action_targets": _list_to_dict(self.action_targets),
            "business_affordances": _list_to_dict(self.business_affordances),
            "capabilities": _list_to_dict(self.capabilities),
            "reference_observation": (
                self.reference_observation.to_dict()
                if self.reference_observation is not None
                else None
            ),
            "visit_count": self.visit_count,
            "status": self.status,
            "evidence": _list_to_dict(self.evidence),
            "node_label": self.node_label,
            "state_summary": self.state_summary,
            "naming_provenance": (
                dict(self.naming_provenance)
                if self.naming_provenance is not None
                else None
            ),
            "planning_state": (
                self.planning_state.to_dict()
                if self.planning_state is not None
                else None
            ),
            "semantic_location_hint": self.semantic_location_hint,
        }


@dataclass(frozen=True)
class WebKobeEdge:
    source_node_id: str
    target_node_id: str
    instruction: str
    action: BrowserAction
    capability: Capability | None
    target_observation: str
    observed_delta: list[ObservedDelta]
    schema_delta: dict[str, Any] | None
    execution_trace: ExecutionTrace
    pddl_hint: PddlActionHint | None = None
    planning_delta: PlanningDelta | None = None
    planning_transition: PlanningTransition | None = None
    semantic_observation: SemanticObservation | None = None
    required_action_ids: list[str] = field(default_factory=list)
    visual_change_kind: str = "unknown"
    visit_count: int = 1
    status: str = "verified"
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def edge_id(self) -> str:
        return (
            f"{self.source_node_id}__{self.action.semantic_id}__"
            f"{self.target_node_id}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "instruction": self.instruction,
            "action": self.action.to_dict(),
            "capability": self.capability.to_dict() if self.capability else None,
            "target_observation": self.target_observation,
            "observed_delta": _list_to_dict(self.observed_delta),
            "schema_delta": self.schema_delta,
            "execution_trace": self.execution_trace.to_dict(),
            "pddl_hint": self.pddl_hint.to_dict() if self.pddl_hint else None,
            "planning_delta": (
                self.planning_delta.to_dict()
                if self.planning_delta is not None
                else None
            ),
            "planning_transition": (
                self.planning_transition.to_dict()
                if self.planning_transition is not None
                else None
            ),
            "semantic_observation": (
                self.semantic_observation.to_dict()
                if self.semantic_observation is not None
                else None
            ),
            "required_action_ids": list(self.required_action_ids),
            "visual_change_kind": self.visual_change_kind,
            "visit_count": self.visit_count,
            "status": self.status,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class WebKobeGraph:
    app: str
    start_node_id: str
    total_steps_completed: int
    nodes: list[WebKobeNode] = field(default_factory=list)
    edges: list[WebKobeEdge] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    execution_events: list[WebKobeEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        meta = dict(self.meta)
        meta.update(
            {
                "schema_version": WEB_KOBE_SCHEMA_VERSION,
                "app": self.app,
                "start_node_id": self.start_node_id,
                "total_steps_completed": self.total_steps_completed,
            }
        )
        payload = {
            "meta": meta,
            "nodes": _list_to_dict(self.nodes),
            "edges": _list_to_dict(self.edges),
        }
        if self.execution_events:
            payload["execution_events"] = _list_to_dict(self.execution_events)
        return payload
