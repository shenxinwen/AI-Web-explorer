import csv
import json

from scripts.paper.analyze_c1 import analyze_experiment, compute_admission_metrics


def test_compute_admission_metrics_counts_precision_retention_and_yield():
    candidates = {"a", "b", "c", "d"}
    supported = {"a", "b"}

    result = compute_admission_metrics(
        candidates=candidates,
        supported=supported,
        admissions={
            "proposal_as_fact": {"a", "b", "c", "d"},
            "executor_success_as_fact": {"a", "c"},
            "evidence_grounded": {"a", "b"},
        },
    )

    assert result["proposal_as_fact"] == {
        "admitted": 4,
        "true_positive": 2,
        "precision": 0.5,
        "supported_knowledge_retention": 1.0,
        "admission_yield": 1.0,
        "f1": 2 / 3,
    }
    assert result["executor_success_as_fact"]["precision"] == 0.5
    assert result["executor_success_as_fact"]["supported_knowledge_retention"] == 0.5
    assert result["evidence_grounded"]["precision"] == 1.0
    assert result["evidence_grounded"]["supported_knowledge_retention"] == 1.0


def test_compute_admission_metrics_handles_no_admissions():
    result = compute_admission_metrics(
        candidates={"a"},
        supported=set(),
        admissions={"evidence_grounded": set()},
    )

    assert result["evidence_grounded"]["precision"] is None
    assert result["evidence_grounded"]["supported_knowledge_retention"] is None
    assert result["evidence_grounded"]["admission_yield"] == 0.0
    assert result["evidence_grounded"]["f1"] is None


def test_analyze_experiment_aggregates_candidates_gold_and_attempt_evidence(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "samples.json").write_text(
        json.dumps([
            {
                "sample_id": "A001",
                "run_id": "run_01",
                "semantic_location": "catalog",
                "action_id": "working_action",
            }
        ]),
        encoding="utf-8",
    )
    with (package / "gold.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sample_id", "sample_valid", "invalid_reason", "function_exists",
            "functional_outcome", "notes",
        ])
        writer.writerow(["S001", "true", "", "yes", "success", ""])

    run = tmp_path / "runs" / "run_01"
    run.mkdir(parents=True)
    (run / "before.png").write_bytes(b"before")
    (run / "after.png").write_bytes(b"after")
    graph = {
        "nodes": [{
            "node_id": "n1",
            "semantic_location_hint": "catalog",
            "business_affordances": [
                {"action_name": "working_action"},
                {"action_name": "unverified_action"},
            ],
        }],
        "execution_events": [{
            "source_node_id": "n1",
            "evidence_ref": "event:1",
            "action": {"semantic_id": "working_action"},
        }],
    }
    evidence = {
        "execution_events": {
            "event:1": {
                "execution_trace": {"metadata": {
                    "backend_reported_success": True,
                    "before_screenshot_path": str(run / "before.png"),
                    "after_screenshot_path": str(run / "after.png"),
                    "action_outcome_trace": {
                        "llm_response": {"outcome": "success"}
                    },
                }}
            }
        }
    }
    (run / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (run / "graph_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    result = analyze_experiment(
        root=tmp_path,
        site_configs={
            "demo": {
                "runs": tmp_path / "runs",
                "package": package,
                "gold": "gold.csv",
                "legacy_run_grouping": False,
            }
        },
    )

    assert result["admission_rules"]["evidence_grounded"].startswith(
        "admit when at least one evidence-complete attempt"
    )
    assert result["sites"]["demo"]["candidate_functions"] == 2
    assert result["sites"]["demo"]["supported_functions"] == 1
    assert result["sites"]["demo"]["metrics"]["proposal_as_fact"]["precision"] == 0.5
    assert result["sites"]["demo"]["metrics"]["evidence_grounded"]["precision"] == 1.0
    assert result["sites"]["demo"]["errors"]["proposal_as_fact"]["false_positives"] == [
        ["demo", "catalog", "unverified_action"]
    ]
