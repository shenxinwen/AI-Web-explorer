"""Export every E004 execution attempt to a human-review CSV template."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


COLUMNS = [
    "run_id", "site", "condition", "random_seed", "attempt_id",
    "attempt_index", "semantic_location", "canonical_action_id",
    "executor_status", "before_screenshot_path", "after_screenshot_path",
    "evidence_complete", "evidence_label", "core_match_status", "core_id",
    "notes",
]


def extract_attempts(
    site: str, run_id: str, graph_path: Path, evidence_path: Path
) -> list[dict[str, str]]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    details = evidence.get("execution_events", {})
    locations = {
        node.get("node_id", ""): node.get("semantic_location_hint", "")
        for node in graph.get("nodes", [])
    }
    rows = []
    for index, event in enumerate(graph.get("execution_events", []), 1):
        detail = details.get(event.get("evidence_ref", ""), {})
        metadata = detail.get("execution_trace", {}).get("metadata", {})
        before = str(metadata.get("before_screenshot_path") or "")
        after = str(metadata.get("after_screenshot_path") or "")
        semantic = event.get("semantic_observation") or {}
        success = event.get("execution_trace", {}).get("success")
        rows.append({
            "run_id": run_id,
            "site": site,
            "condition": str(graph.get("meta", {}).get("exploration_condition", "")),
            "random_seed": str(graph.get("meta", {}).get("random_seed") or ""),
            "attempt_id": str(metadata.get("attempt_id") or f"event-{index:04d}"),
            "attempt_index": str(index),
            "semantic_location": str(
                semantic.get("source_location")
                or locations.get(event.get("source_node_id", ""), "")
            ),
            "canonical_action_id": str(event.get("action", {}).get("semantic_id", "")),
            "executor_status": "success" if success else "failed",
            "before_screenshot_path": before,
            "after_screenshot_path": after,
            "evidence_complete": "true" if before and after else "false",
            "evidence_label": "",
            "core_match_status": "",
            "core_id": "",
            "notes": "",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = extract_attempts(args.site, args.run_id, args.graph, args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
