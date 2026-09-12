from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    PddlActionHint,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    PlanningState,
    PlanningTransition,
)
from ai_web_explorer.grounded_web.semantic_model import (
    SemanticObservation,
    semantic_observation_from_dict,
)


def _evidence_from_dict(data: dict[str, Any]) -> Evidence:
    return Evidence(
        source=str(data.get("source", "json")),
        selector=data.get("selector"),
        text_sample=data.get("text_sample"),
        url=data.get("url"),
        confidence=float(data.get("confidence", 1.0)),
    )


def _page_frame_from_dict(data: dict[str, Any]) -> PageFrame:
    return PageFrame(
        page_id=str(data.get("page_id", "")),
        page_type=str(data.get("page_type", "")),
        url=str(data.get("url", "")),
        url_pattern=str(data.get("url_pattern", data.get("url", ""))),
        title=str(data.get("title", "")),
        heading=data.get("heading"),
        signature_hints=dict(data.get("signature_hints", {})),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _reference_observation_from_dict(
    data: dict[str, Any] | None,
) -> ReferenceObservation | None:
    if data is None:
        return None
    return ReferenceObservation(
        url=str(data.get("url", "")),
        title=str(data.get("title", "")),
        screenshot_path=data.get("screenshot_path"),
        dom_summary=data.get("dom_summary"),
        accessibility_summary=data.get("accessibility_summary"),
        observation_hash=data.get("observation_hash"),
    )


def _business_affordance_from_dict(data: dict[str, Any]) -> BusinessAffordance:
    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
    supporting_facts = data.get("supporting_facts", [])
    if not isinstance(supporting_facts, list):
        supporting_facts = []
    return BusinessAffordance(
        action_name=str(data.get("action_name", "")),
        label=data.get("label"),
        relevance_hint=str(data.get("relevance_hint", "unknown")),
        target_hint=data.get("target_hint"),
        execution_policy=str(data.get("execution_policy", "single_instance")),
        source=str(data.get("source", "json")),
        confidence=confidence,
        supporting_facts=[
            str(fact).strip()
            for fact in supporting_facts
            if str(fact).strip()
        ],
        expected_outcome=data.get("expected_outcome"),
        execution_instance=data.get("execution_instance"),
    )


def _node_from_dict(data: dict[str, Any]) -> WebKobeNode:
    return WebKobeNode(
        node_id=str(data["node_id"]),
        page_description=str(data.get("page_description", "")),
        page_frame=_page_frame_from_dict(dict(data.get("page_frame", {}))),
        state_schema={
            key: list(values)
            for key, values in dict(data.get("state_schema", {})).items()
        },
        last_state_snapshot=dict(data.get("last_state_snapshot", {})),
        reference_observation=_reference_observation_from_dict(
            data.get("reference_observation")
        ),
        visit_count=int(data.get("visit_count", 0)),
        status=str(data.get("status", "verified")),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
        node_label=data.get("node_label"),
        state_summary=data.get("state_summary"),
        naming_provenance=data.get("naming_provenance"),
        planning_state=_planning_state_from_dict(data.get("planning_state")),
        semantic_location_hint=data.get("semantic_location_hint"),
        business_affordances=[
            _business_affordance_from_dict(item)
            for item in data.get("business_affordances", [])
            if isinstance(item, dict)
        ],
    )


def _action_from_dict(data: dict[str, Any]) -> BrowserAction:
    supporting_facts = data.get("supporting_facts", [])
    if not isinstance(supporting_facts, list):
        supporting_facts = []
    semantic_id = str(data["semantic_id"])
    return BrowserAction(
        action_kind=str(data.get("action_kind", "")),
        locator=data.get("locator"),
        semantic_id=semantic_id,
        input_values=dict(data.get("input_values", {})),
        description=data.get("description"),
        action_label=data.get("action_label"),
        canonical_action_name=data.get("canonical_action_name") or semantic_id,
        naming_provenance=data.get("naming_provenance"),
        supporting_facts=[
            str(fact).strip()
            for fact in supporting_facts
            if str(fact).strip()
        ],
        execution_policy=str(data.get("execution_policy") or "single_instance"),
        expected_outcome=data.get("expected_outcome"),
        execution_instance=data.get("execution_instance"),
    )


def _observed_delta_from_dict(data: dict[str, Any]) -> ObservedDelta:
    return ObservedDelta(
        field=str(data["field"]),
        before=data.get("before"),
        after=data.get("after"),
        delta_type=str(data.get("delta_type", "unknown")),
        confidence=float(data.get("confidence", 1.0)),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _execution_trace_from_dict(data: dict[str, Any]) -> ExecutionTrace:
    return ExecutionTrace(
        concrete_action_kind=str(data.get("concrete_action_kind", "")),
        concrete_locator=data.get("concrete_locator"),
        concrete_target_sample=data.get("concrete_target_sample"),
        input_values_used=dict(data.get("input_values_used", {})),
        before_observation_id=str(data.get("before_observation_id", "")),
        after_observation_id=str(data.get("after_observation_id", "")),
        success=bool(data.get("success", False)),
        error=data.get("error"),
        metadata=dict(data.get("metadata", {})),
    )


def _planning_delta_from_dict(data: dict[str, Any] | None) -> PlanningDelta | None:
    if data is None:
        return None
    return PlanningDelta(
        candidate_added_facts=list(data.get("candidate_added_facts", [])),
        candidate_removed_facts=list(data.get("candidate_removed_facts", [])),
        verified_added_facts=list(data.get("verified_added_facts", [])),
        verified_removed_facts=list(data.get("verified_removed_facts", [])),
        preserved_profile_facts=list(data.get("preserved_profile_facts", [])),
        profile_fact_ids=list(data.get("profile_fact_ids", [])),
        generated_fact_ids=list(data.get("generated_fact_ids", [])),
        evidence=list(data.get("evidence", [])),
        confidence=data.get("confidence"),
        uncertainty_reason=data.get("uncertainty_reason"),
    )


def _planning_state_from_dict(data: dict[str, Any] | None) -> PlanningState | None:
    if data is None:
        return None
    return PlanningState(
        active_facts=list(data.get("active_facts", [])),
        profile_fact_ids=list(data.get("profile_fact_ids", [])),
        generated_fact_ids=list(data.get("generated_fact_ids", [])),
        evidence=list(data.get("evidence", [])),
    )


def _planning_transition_from_dict(
    data: dict[str, Any] | None,
) -> PlanningTransition | None:
    if data is None:
        return None
    return PlanningTransition(
        pre_facts=list(data.get("pre_facts", [])),
        added_facts=list(data.get("added_facts", [])),
        removed_facts=list(data.get("removed_facts", [])),
        post_facts=list(data.get("post_facts", [])),
        evidence=list(data.get("evidence", [])),
        confidence=data.get("confidence"),
    )


def _semantic_observation_from_dict(
    data: dict[str, Any] | None,
) -> SemanticObservation | None:
    return semantic_observation_from_dict(data)


def _pddl_action_hint_from_dict(data: dict[str, Any] | None) -> PddlActionHint | None:
    if data is None:
        return None
    return PddlActionHint(
        action_name=str(data["action_name"]),
        preconditions=list(data.get("preconditions", [])),
        add_effects=list(data.get("add_effects", [])),
        del_effects=list(data.get("del_effects", [])),
    )


def _edge_from_dict(data: dict[str, Any]) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=str(data["source_node_id"]),
        target_node_id=str(data["target_node_id"]),
        instruction=str(data.get("instruction", "")),
        action=_action_from_dict(dict(data["action"])),
        capability=None,
        target_observation=str(data.get("target_observation", "")),
        observed_delta=[
            _observed_delta_from_dict(item) for item in data.get("observed_delta", [])
        ],
        schema_delta=data.get("schema_delta"),
        execution_trace=_execution_trace_from_dict(
            dict(data.get("execution_trace", {}))
        ),
        pddl_hint=_pddl_action_hint_from_dict(data.get("pddl_hint")),
        planning_delta=_planning_delta_from_dict(data.get("planning_delta")),
        planning_transition=_planning_transition_from_dict(
            data.get("planning_transition")
        ),
        semantic_observation=_semantic_observation_from_dict(
            data.get("semantic_observation")
        ),
        required_action_ids=list(data.get("required_action_ids", [])),
        visual_change_kind=str(data.get("visual_change_kind", "unknown")),
        visit_count=int(data.get("visit_count", 1)),
        status=str(data.get("status", "verified")),
        evidence=[_evidence_from_dict(item) for item in data.get("evidence", [])],
    )


def _web_kobe_graph_from_dict(data: dict[str, Any]) -> WebKobeGraph:
    meta = dict(data.get("meta", {}))
    return WebKobeGraph(
        app=str(meta.get("app", "web")),
        start_node_id=str(meta["start_node_id"]),
        total_steps_completed=int(meta.get("total_steps_completed", 0)),
        nodes=[_node_from_dict(item) for item in data.get("nodes", [])],
        edges=[_edge_from_dict(item) for item in data.get("edges", [])],
        meta=meta,
        execution_events=[
            _edge_from_dict(item) for item in data.get("execution_events", [])
        ],
    )


def read_web_kobe_graph_json_data(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WebKobeGraph JSON root must be an object")
    return data


def load_web_kobe_graph_json(path: Path) -> WebKobeGraph:
    data = read_web_kobe_graph_json_data(path)
    return _web_kobe_graph_from_dict(data)
