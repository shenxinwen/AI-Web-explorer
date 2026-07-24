from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    PddlActionHint,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState

PROJECTABLE_EDGE_STATUSES = {
    "verified",
    "succeeded",
    "succeeded_with_observed_change",
    "succeeded_with_navigation",
}


@dataclass(frozen=True)
class WebKobePddlArtifacts:
    domain: str
    problem: str


@dataclass(frozen=True)
class PddlProjectionOptions:
    include_observed_delta_facts: bool = False


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
    )


def _action_from_dict(data: dict[str, Any]) -> BrowserAction:
    return BrowserAction(
        action_kind=str(data.get("action_kind", "")),
        locator=data.get("locator"),
        semantic_id=str(data["semantic_id"]),
        input_values=dict(data.get("input_values", {})),
        description=data.get("description"),
        action_label=data.get("action_label"),
        canonical_action_name=data.get("canonical_action_name"),
        naming_provenance=data.get("naming_provenance"),
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
        evidence=list(data.get("evidence", [])),
        confidence=data.get("confidence"),
        uncertainty_reason=data.get("uncertainty_reason"),
    )


def _planning_state_from_dict(data: dict[str, Any] | None) -> PlanningState | None:
    if data is None:
        return None
    return PlanningState(
        active_facts=list(data.get("active_facts", [])),
        evidence=list(data.get("evidence", [])),
    )


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
    )


def load_web_kobe_graph_json(path: Path) -> WebKobeGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WebKobeGraph JSON root must be an object")
    return _web_kobe_graph_from_dict(data)


def _predicate(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _at(node_id: str) -> str:
    return f"at_{_predicate(node_id)}"


def _location_base_for_node(node) -> str:
    return _predicate(node.node_label or node.node_id) or _predicate(node.node_id)


def _location_predicates_by_node_id(graph: WebKobeGraph) -> dict[str, str]:
    used: dict[str, int] = {}
    locations: dict[str, str] = {}
    for node in graph.nodes:
        base = _location_base_for_node(node) or "state"
        count = used.get(base, 0) + 1
        used[base] = count
        suffix = "" if count == 1 else f"_{count:03d}"
        locations[node.node_id] = f"at_{base}{suffix}"
    return locations


def _is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _is_zero_or_negative_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value <= 0


def _positive_predicate(name: str) -> str:
    return f"{_predicate(name)}_positive"


def _unique_facts(*fact_lists: list[str]) -> list[str]:
    facts: list[str] = []
    for fact_list in fact_lists:
        for fact in fact_list:
            if fact not in facts:
                facts.append(fact)
    return facts


def _unique_items(items: list[str]) -> list[str]:
    unique: list[str] = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique


def _trusted_added_planning_facts(delta: PlanningDelta) -> list[str]:
    return _unique_facts(delta.candidate_added_facts, delta.verified_added_facts)


def _trusted_removed_planning_facts(delta: PlanningDelta) -> list[str]:
    return _unique_facts(delta.candidate_removed_facts, delta.verified_removed_facts)


def _state_predicate_for_value(key: str, value: object) -> str | None:
    if isinstance(value, bool):
        return _predicate(key)
    if _is_positive_number(value):
        return _positive_predicate(key)
    return None


def _state_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
        if node.planning_state is not None:
            names.update(_predicate(fact) for fact in node.planning_state.active_facts)
            continue
        for key, value in node.last_state_snapshot.items():
            predicate = _state_predicate_for_value(key, value)
            if predicate is not None:
                names.add(predicate)
    return sorted(names)


def _nodes_by_id(graph: WebKobeGraph) -> dict[str, object]:
    return {node.node_id: node for node in graph.nodes}


def _require_node(graph: WebKobeGraph, node_id: str, *, role: str):
    nodes = _nodes_by_id(graph)
    if node_id not in nodes:
        raise ValueError(f"Unknown {role} node: {node_id}")
    return nodes[node_id]


def _initial_predicates(
    graph: WebKobeGraph,
    *,
    start_node_id: str,
    location_predicates: dict[str, str],
) -> list[str]:
    start = _require_node(graph, start_node_id, role="start")
    predicates = [location_predicates[start.node_id]]
    if start.planning_state is not None:
        predicates.extend(
            _predicate(fact) for fact in start.planning_state.active_facts
        )
        return sorted(set(predicates))
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
        elif _is_positive_number(value):
            predicates.append(_positive_predicate(key))
    return sorted(set(predicates))


def _action_name(raw: str) -> str:
    return _predicate(raw)


UI_LEVEL_ACTION_TERMS = {
    "button",
    "click",
    "fill",
    "selector",
    "type",
    "xpath",
}


def _business_canonical_action_name(edge) -> str | None:
    canonical = getattr(edge.action, "canonical_action_name", None)
    if not canonical:
        return None
    name = _action_name(canonical)
    if not name or name != canonical:
        return None
    terms = set(name.split("_"))
    if terms & UI_LEVEL_ACTION_TERMS:
        return None
    return name


def _is_order_completion_edge(edge) -> bool:
    effect_predicates = set(
        _effect_predicates_for_edge(edge, options=PddlProjectionOptions())
    )
    if "order_created" in effect_predicates or "order_completed" in effect_predicates:
        return True
    return "checkout_complete" in _predicate(
        edge.target_node_id
    ) and "finish" in _predicate(edge.action.semantic_id)


def _readable_action_suffix_for_edge(edge) -> str:
    if edge.pddl_hint is not None:
        return _action_name(edge.pddl_hint.action_name)
    canonical = _business_canonical_action_name(edge)
    if canonical is not None:
        return canonical
    if _is_order_completion_edge(edge):
        return "order_place_confirm"
    fallback = _action_name(edge.action.semantic_id)
    return fallback or "transition"


def _unique_pddl_action_name(edge, *, index: int) -> str:
    suffix = _readable_action_suffix_for_edge(edge)
    return f"edge_{index:03d}_{suffix}"


def _delta_predicate_change(delta) -> tuple[str, bool] | None:
    if isinstance(delta.after, bool):
        return _predicate(delta.field), delta.after
    if _is_zero_or_negative_number(delta.before) and _is_positive_number(delta.after):
        return _positive_predicate(delta.field), True
    if _is_positive_number(delta.before) and _is_zero_or_negative_number(delta.after):
        return _positive_predicate(delta.field), False
    return None


def _observed_effect_predicates_for_edge(edge) -> list[str]:
    predicates = []
    for delta in edge.observed_delta:
        change = _delta_predicate_change(delta)
        if change is not None:
            predicates.append(change[0])
    return predicates


def _planning_effect_predicates_for_edge(edge) -> list[str]:
    predicates = []
    if edge.planning_delta is not None:
        predicates.extend(
            _predicate(fact)
            for fact in _trusted_added_planning_facts(edge.planning_delta)
        )
        predicates.extend(
            _predicate(fact)
            for fact in _trusted_removed_planning_facts(edge.planning_delta)
        )
    return predicates


def _effect_predicates_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
    source_node=None,
) -> list[str]:
    predicates = []
    if options.include_observed_delta_facts:
        predicates.extend(_observed_effect_predicates_for_edge(edge))
    if edge.planning_delta is not None:
        predicates.extend(
            _predicate(fact)
            for fact in _trusted_added_planning_facts(edge.planning_delta)
        )
        predicates.extend(
            _removed_planning_predicates_for_edge(edge, source_node=source_node)
        )
    return predicates


def _active_planning_predicates_for_node(node) -> set[str] | None:
    if node.planning_state is None:
        return None
    return {_predicate(fact) for fact in node.planning_state.active_facts}


def _removed_planning_predicates_for_edge(edge, *, source_node=None) -> list[str]:
    if edge.planning_delta is None:
        return []
    predicates = [
        _predicate(fact)
        for fact in _trusted_removed_planning_facts(edge.planning_delta)
    ]
    active_predicates = (
        _active_planning_predicates_for_node(source_node)
        if source_node is not None
        else None
    )
    if active_predicates is None:
        return predicates
    return [predicate for predicate in predicates if predicate in active_predicates]


def _preconditions_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
    location_predicates: dict[str, str],
    source_node=None,
) -> list[str]:
    preconditions = [f"({location_predicates[edge.source_node_id]})"]
    for predicate in _removed_planning_predicates_for_edge(
        edge,
        source_node=source_node,
    ):
        preconditions.append(f"({predicate})")
    if options.include_observed_delta_facts:
        for delta in edge.observed_delta:
            change = _delta_predicate_change(delta)
            if change is None:
                continue
            pred, becomes_true = change
            if not becomes_true:
                preconditions.append(f"({pred})")
    return _unique_items(preconditions)


def _effects_for_edge(
    edge,
    *,
    options: PddlProjectionOptions,
    location_predicates: dict[str, str],
    source_node=None,
) -> list[str]:
    effects = [
        f"(not ({location_predicates[edge.source_node_id]}))",
        f"({location_predicates[edge.target_node_id]})",
    ]
    if options.include_observed_delta_facts:
        for delta in edge.observed_delta:
            change = _delta_predicate_change(delta)
            if change is None:
                continue
            pred, becomes_true = change
            if becomes_true:
                effects.append(f"({pred})")
            else:
                effects.append(f"(not ({pred}))")
    if edge.planning_delta is not None:
        for fact in _trusted_added_planning_facts(edge.planning_delta):
            effects.append(f"({_predicate(fact)})")
        for predicate in _removed_planning_predicates_for_edge(
            edge,
            source_node=source_node,
        ):
            effects.append(f"(not ({predicate}))")
    return _unique_items(effects)


def _is_projectable_edge(edge) -> bool:
    return edge.execution_trace.success and edge.status in PROJECTABLE_EDGE_STATUSES


def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
    options: PddlProjectionOptions | None = None,
) -> WebKobePddlArtifacts:
    options = options or PddlProjectionOptions()
    selected_start_node_id = start_node_id or graph.start_node_id
    _require_node(graph, selected_start_node_id, role="start")
    _require_node(graph, goal_node_id, role="goal")

    location_predicates = _location_predicates_by_node_id(graph)
    predicate_names = set(list(location_predicates.values()) + _state_predicates(graph))
    nodes_by_id = _nodes_by_id(graph)
    for edge in graph.edges:
        if _is_projectable_edge(edge):
            predicate_names.update(
                _effect_predicates_for_edge(
                    edge,
                    options=options,
                    source_node=nodes_by_id.get(edge.source_node_id),
                )
            )
    predicates = sorted(predicate_names)
    predicate_text = "\n".join(f"    ({name})" for name in predicates)

    projectable_edges = [edge for edge in graph.edges if _is_projectable_edge(edge)]
    action_blocks = []
    for index, edge in enumerate(projectable_edges, start=1):
        action_name = _unique_pddl_action_name(edge, index=index)
        source_node = nodes_by_id.get(edge.source_node_id)
        preconditions = _preconditions_for_edge(
            edge,
            options=options,
            location_predicates=location_predicates,
            source_node=source_node,
        )
        effects = _effects_for_edge(
            edge,
            options=options,
            location_predicates=location_predicates,
            source_node=source_node,
        )
        action_blocks.append(
            "\n".join(
                [
                    f"  (:action {action_name}",
                    f"    :precondition (and {' '.join(preconditions)})",
                    f"    :effect (and {' '.join(effects)})",
                    "  )",
                ]
            )
        )

    domain = "\n".join(
        [
            "(define (domain web-kobe)",
            "  (:requirements :strips)",
            "  (:predicates",
            predicate_text,
            "  )",
            *action_blocks,
            ")",
        ]
    )
    init_text = " ".join(
        f"({name})"
        for name in _initial_predicates(
            graph,
            start_node_id=selected_start_node_id,
            location_predicates=location_predicates,
        )
    )
    problem = "\n".join(
        [
            "(define (problem web-kobe-problem)",
            "  (:domain web-kobe)",
            f"  (:init {init_text})",
            f"  (:goal (and ({location_predicates[goal_node_id]})))",
            ")",
        ]
    )
    return WebKobePddlArtifacts(domain=domain, problem=problem)
