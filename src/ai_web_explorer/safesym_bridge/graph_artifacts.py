from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ai_web_explorer.grounded_web.graph import WebKobeGraph

GRAPH_EVIDENCE_SCHEMA_VERSION = "web-kobe-graph-evidence-v1"


@dataclass(frozen=True)
class GraphArtifactPayload:
    compact_graph: dict[str, Any]
    evidence_sidecar: dict[str, Any]


def _without_empty_optional_values(value: Any) -> Any:
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, child in value.items():
            compact_child = _without_empty_optional_values(child)
            if compact_child not in (None, "", [], {}):
                compact[key] = compact_child
        return compact
    if isinstance(value, list):
        return [
            compact_child
            for child in value
            if (compact_child := _without_empty_optional_values(child))
            not in (None, "", [], {})
        ]
    return value


def _compact_page_frame(page_frame: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: page_frame.get(key)
        for key in (
            "page_id",
            "page_type",
            "url",
            "url_pattern",
            "title",
            "heading",
            "signature_hints",
        )
    }
    return _without_empty_optional_values(compact)


def _compact_business_affordance(affordance: dict[str, Any]) -> dict[str, Any]:
    compact = {"action_name": affordance.get("action_name")}
    for key in (
        "label",
        "relevance_hint",
        "target_hint",
        "execution_policy",
        "source",
        "confidence",
        "supporting_facts",
    ):
        if key in affordance:
            compact[key] = affordance[key]
    return _without_empty_optional_values(compact)


def _compact_node(node: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    compact: dict[str, Any] = {
        key: node.get(key)
        for key in (
            "node_id",
            "page_description",
            "state_schema",
            "last_state_snapshot",
            "visit_count",
            "status",
        )
    }
    compact["page_frame"] = _compact_page_frame(node.get("page_frame", {}))
    compact["business_affordances"] = [
        _compact_business_affordance(affordance)
        for affordance in node.get("business_affordances", [])
    ]
    for key in (
        "node_label",
        "state_summary",
        "naming_provenance",
        "planning_state",
        "semantic_location_hint",
    ):
        if node.get(key) is not None:
            compact[key] = node[key]
    compact = _without_empty_optional_values(compact)
    semantic_location_conflict = (node.get("naming_provenance") or {}).get(
        "semantic_location_hint_conflict"
    )
    if semantic_location_conflict is not None:
        compact.setdefault("naming_provenance", {})[
            "semantic_location_hint_conflict"
        ] = deepcopy(semantic_location_conflict)

    page_frame = node.get("page_frame", {})
    removed_fields = {
        key: deepcopy(value) for key, value in node.items() if key not in compact
    }
    page_frame_evidence = page_frame.get("evidence")
    if page_frame_evidence:
        removed_fields["page_frame_evidence"] = deepcopy(page_frame_evidence)
    sidecar = _without_empty_optional_values(removed_fields)
    return compact, sidecar


def _compact_action(action: dict[str, Any]) -> dict[str, Any]:
    semantic_id = action.get("semantic_id")
    compact: dict[str, Any] = {
        "action_kind": action.get("action_kind"),
        "semantic_id": semantic_id,
    }
    for key in (
        "input_values",
        "description",
        "action_label",
        "supporting_facts",
        "execution_policy",
    ):
        if action.get(key):
            compact[key] = action[key]
    canonical = action.get("canonical_action_name")
    if canonical and canonical != semantic_id:
        compact["canonical_action_name"] = canonical
    return _without_empty_optional_values(compact)


def _compact_execution_trace(trace: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        key: trace.get(key)
        for key in (
            "concrete_action_kind",
            "before_observation_id",
            "after_observation_id",
            "success",
        )
    }
    if trace.get("error"):
        compact["error"] = trace["error"]
    replay_validation_status = (trace.get("metadata") or {}).get(
        "replay_validation_status"
    )
    if replay_validation_status is not None:
        compact["metadata"] = {
            "replay_validation_status": replay_validation_status,
        }
    trace_metadata = trace.get("metadata") or {}
    for key in ("risk_assessment", "risk_detection_error"):
        if key in trace_metadata:
            compact.setdefault("metadata", {})[key] = deepcopy(trace_metadata[key])
    semantic_conflict = (trace.get("metadata") or {}).get(
        "semantic_observation_conflict"
    )
    compact = _without_empty_optional_values(compact)
    if semantic_conflict is not None:
        compact.setdefault("metadata", {})["semantic_observation_conflict"] = deepcopy(
            semantic_conflict
        )
    return compact


def _compact_edge(edge: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    compact: dict[str, Any] = {
        key: edge.get(key)
        for key in (
            "edge_id",
            "source_node_id",
            "target_node_id",
            "status",
            "visit_count",
            "visual_change_kind",
            "required_action_ids",
        )
    }
    compact["action"] = _compact_action(edge.get("action", {}))
    compact["execution_trace"] = _compact_execution_trace(
        edge.get("execution_trace", {})
    )
    for key in ("planning_delta", "planning_transition"):
        if edge.get(key) is not None:
            compact[key] = edge[key]
    if edge.get("semantic_observation") is not None:
        compact["semantic_observation"] = edge["semantic_observation"]
    compact = _without_empty_optional_values(compact)
    semantic_conflict = (edge.get("execution_trace", {}).get("metadata") or {}).get(
        "semantic_observation_conflict"
    )
    if semantic_conflict is not None:
        compact.setdefault("execution_trace", {}).setdefault("metadata", {})[
            "semantic_observation_conflict"
        ] = deepcopy(semantic_conflict)

    action = edge.get("action", {})
    sidecar = {
        key: deepcopy(edge[key])
        for key in (
            "instruction",
            "target_observation",
            "observed_delta",
            "schema_delta",
            "pddl_hint",
            "evidence",
        )
        if key in edge and edge[key] not in (None, "", [], {})
    }
    action_details = {
        key: deepcopy(action[key])
        for key in ("locator", "description", "naming_provenance")
        if action.get(key) not in (None, "", [], {})
    }
    if action_details:
        sidecar["action_details"] = action_details
    if edge.get("execution_trace"):
        sidecar["execution_trace"] = deepcopy(edge["execution_trace"])
    sidecar = _without_empty_optional_values(sidecar)
    return compact, sidecar


def build_graph_artifact_payload(graph: WebKobeGraph) -> GraphArtifactPayload:
    full_graph = graph.to_dict()
    compact_graph = {
        "meta": deepcopy(full_graph.get("meta", {})),
        "nodes": [],
        "edges": [],
    }
    evidence_sidecar: dict[str, Any] = {
        "schema_version": GRAPH_EVIDENCE_SCHEMA_VERSION,
        "nodes": {},
        "edges": {},
    }

    for node in full_graph.get("nodes", []):
        compact_node, sidecar_node = _compact_node(node)
        if sidecar_node:
            evidence_ref = f"node-evidence:{node['node_id']}"
            compact_node["evidence_ref"] = evidence_ref
            evidence_sidecar["nodes"][evidence_ref] = sidecar_node
        compact_graph["nodes"].append(compact_node)

    for edge in full_graph.get("edges", []):
        compact_edge, sidecar_edge = _compact_edge(edge)
        if sidecar_edge:
            evidence_ref = f"edge-evidence:{edge['edge_id']}"
            compact_edge["evidence_ref"] = evidence_ref
            evidence_sidecar["edges"][evidence_ref] = sidecar_edge
        compact_graph["edges"].append(compact_edge)

    if full_graph.get("execution_events"):
        compact_graph["execution_events"] = [
            _compact_edge(event)[0] for event in full_graph["execution_events"]
        ]

    if not evidence_sidecar["nodes"]:
        evidence_sidecar.pop("nodes")
    if not evidence_sidecar["edges"]:
        evidence_sidecar.pop("edges")
    return GraphArtifactPayload(
        compact_graph=compact_graph,
        evidence_sidecar=evidence_sidecar,
    )
