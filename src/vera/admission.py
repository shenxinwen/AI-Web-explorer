"""Build a knowledge view from recorded attempts and screenshot evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _artifact_exists(root: Path, value: str | None) -> bool:
    if not value:
        return False
    path = Path(value)
    return (path if path.is_absolute() else root / path).is_file()


def evidence_supported(metadata: dict[str, Any], *, artifact_root: Path) -> bool:
    """Require both screenshot files and an explicit successful outcome judgment."""
    complete = _artifact_exists(
        artifact_root, metadata.get("before_screenshot_path")
    ) and _artifact_exists(artifact_root, metadata.get("after_screenshot_path"))
    outcome = (metadata.get("action_outcome_trace", {}).get("llm_response") or {}).get(
        "outcome"
    )
    return complete and outcome == "success"


def build_admitted_knowledge(
    graph_path: Path,
    *,
    artifact_root: Path,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Aggregate supported attempts by application, location, and action identifier.

    This reads the compact graph and its evidence sidecar without rewriting
    either. Relative screenshot paths are resolved against the run's working
    directory, supplied as artifact_root.
    """
    evidence_path = evidence_path or graph_path.with_name("graph_evidence.json")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    application = graph.get("meta", {}).get("app") or graph.get("app")
    if not application:
        raise ValueError("graph must contain its application identifier")
    nodes = {node["node_id"]: node for node in graph.get("nodes", [])}
    admitted: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for event in graph.get("execution_events", []):
        action = event.get("action", {})
        action_id = action.get("semantic_id") or action.get("action_id")
        if not action_id:
            continue
        semantic = event.get("semantic_observation") or {}
        location = semantic.get("source_location") or nodes.get(
            event.get("source_node_id"), {}
        ).get("semantic_location_hint", "")
        detail = evidence.get("execution_events", {}).get(event.get("evidence_ref", ""), {})
        metadata = detail.get("execution_trace", {}).get("metadata", {})
        if evidence_supported(metadata, artifact_root=artifact_root):
            key = (application, location, action_id)
            admitted.setdefault(key, []).append({
                "attempt_id": metadata.get("attempt_id"),
                "evidence_ref": event.get("evidence_ref"),
                "expected_outcome": action.get("expected_outcome", ""),
                "before_screenshot_path": metadata.get("before_screenshot_path"),
                "after_screenshot_path": metadata.get("after_screenshot_path"),
                "risk_assessment": metadata.get("risk_assessment"),
            })
    return {
        "aggregation_key": ["application", "semantic_location", "canonical_action_id"],
        "functions": [
            {"application": app, "semantic_location": location,
             "canonical_action_id": action_id, "supporting_attempts": attempts}
            for (app, location, action_id), attempts in sorted(admitted.items())
        ],
    }
