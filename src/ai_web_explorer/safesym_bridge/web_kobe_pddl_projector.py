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
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)

PROJECTABLE_EDGE_STATUSES = {
    "verified",
    "succeeded",
    "succeeded_with_observed_change",
}


@dataclass(frozen=True)
class WebKobePddlArtifacts:
    domain: str
    problem: str


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
    )


def _action_from_dict(data: dict[str, Any]) -> BrowserAction:
    return BrowserAction(
        action_kind=str(data.get("action_kind", "")),
        locator=data.get("locator"),
        semantic_id=str(data["semantic_id"]),
        input_values=dict(data.get("input_values", {})),
        description=data.get("description"),
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
            _observed_delta_from_dict(item)
            for item in data.get("observed_delta", [])
        ],
        schema_delta=data.get("schema_delta"),
        execution_trace=_execution_trace_from_dict(
            dict(data.get("execution_trace", {}))
        ),
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


def _is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _is_zero_or_negative_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value <= 0


def _positive_predicate(name: str) -> str:
    return f"{_predicate(name)}_positive"


def _state_predicate_for_value(key: str, value: object) -> str | None:
    if isinstance(value, bool):
        return _predicate(key)
    if _is_positive_number(value):
        return _positive_predicate(key)
    return None


def _state_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
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


def _initial_predicates(graph: WebKobeGraph, *, start_node_id: str) -> list[str]:
    start = _require_node(graph, start_node_id, role="start")
    predicates = [_at(start.node_id)]
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
        elif _is_positive_number(value):
            predicates.append(_positive_predicate(key))
    return sorted(set(predicates))


def _action_name(raw: str) -> str:
    return _predicate(raw)


def _effects_for_edge(edge) -> list[str]:
    effects = [
        f"(not ({_at(edge.source_node_id)}))",
        f"({_at(edge.target_node_id)})",
    ]
    for delta in edge.observed_delta:
        if isinstance(delta.after, bool):
            pred = _predicate(delta.field)
            if delta.after:
                effects.append(f"({pred})")
            else:
                effects.append(f"(not ({pred}))")
        elif _is_zero_or_negative_number(delta.before) and _is_positive_number(
            delta.after
        ):
            effects.append(f"({_positive_predicate(delta.field)})")
        elif _is_positive_number(delta.before) and _is_zero_or_negative_number(
            delta.after
        ):
            effects.append(f"(not ({_positive_predicate(delta.field)}))")
    return effects


def _is_projectable_edge(edge) -> bool:
    return edge.execution_trace.success and edge.status in PROJECTABLE_EDGE_STATUSES


def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
) -> WebKobePddlArtifacts:
    selected_start_node_id = start_node_id or graph.start_node_id
    _require_node(graph, selected_start_node_id, role="start")
    _require_node(graph, goal_node_id, role="goal")

    predicates = sorted(
        set([_at(node.node_id) for node in graph.nodes] + _state_predicates(graph))
    )
    predicate_text = "\n".join(f"    ({name})" for name in predicates)

    action_blocks = []
    for edge in graph.edges:
        if not _is_projectable_edge(edge):
            continue
        action_name = _action_name(edge.action.semantic_id)
        preconditions = [f"({_at(edge.source_node_id)})"]
        effects = _effects_for_edge(edge)
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
        )
    )
    problem = "\n".join(
        [
            "(define (problem web-kobe-problem)",
            "  (:domain web-kobe)",
            f"  (:init {init_text})",
            f"  (:goal (and ({_at(goal_node_id)})))",
            ")",
        ]
    )
    return WebKobePddlArtifacts(domain=domain, problem=problem)
