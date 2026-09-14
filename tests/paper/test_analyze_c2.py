import csv
import json

from scripts.paper.analyze_c2 import analyze


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def test_analyze_c2_counts_all_attempts_and_deduplicates_supported_functions(tmp_path):
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    _write_csv(core_dir / "saucedemo.csv", [
        {"core_id": "SD01", "semantic_location": "login", "function_label": "login"},
        {"core_id": "SD02", "semantic_location": "catalog", "function_label": "sort"},
    ])
    annotations = tmp_path / "annotations.csv"
    fields = {
        "run_id": "r1", "site": "saucedemo", "condition": "linear",
        "attempt_id": "a1", "attempt_index": "1", "semantic_location": "login",
        "canonical_action_id": "login", "evidence_label": "supported",
        "core_match_status": "matched", "core_id": "SD01",
        "executor_status": "success", "evidence_complete": "true",
    }
    _write_csv(annotations, [
        fields,
        {**fields, "attempt_id": "a2", "attempt_index": "2"},
        {**fields, "attempt_id": "a3", "attempt_index": "3",
         "canonical_action_id": "missing", "evidence_label": "incomplete",
         "core_match_status": "no_match", "core_id": "",
         "executor_status": "failed", "evidence_complete": "false"},
        {**fields, "attempt_id": "a4", "attempt_index": "4",
         "semantic_location": "catalog", "canonical_action_id": "wishlist",
         "core_match_status": "no_match", "core_id": ""},
    ])

    result = analyze(annotations, core_dir)
    run = result["runs"][0]

    assert run["candidate_attempts"] == 4
    assert run["supported_functions"] == 2
    assert run["covered_functions"] == 1
    assert run["function_total"] == 2
    assert run["function_coverage"] == 0.5
    assert run["supported_noncore_count"] == 1
    assert run["effective_attempt_rate"] == 1 / 4
    assert run["failed_attempts"] == 1
    assert run["evidence_incomplete_attempts"] == 1
    assert run["coverage_growth_curve"] == [1, 1, 1, 1]
