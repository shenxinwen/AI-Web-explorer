import csv
import json
from pathlib import Path

from scripts.paper.build_annotation_package import build_package, extract_samples


def _fixture_run(tmp_path: Path) -> tuple[Path, Path]:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"before")
    after.write_bytes(b"after")
    edge_id = "page__submit__result"
    graph = {
        "edges": [{
            "edge_id": edge_id,
            "action": {
                "semantic_id": "submit",
                "action_label": "Submit order",
                "expected_outcome": "An order confirmation becomes visible.",
            },
            "status": "succeeded_with_observed_change",
            "required_action_ids": ["fill_form"],
            "execution_trace": {"success": True},
        }]
    }
    evidence = {
        "edges": {
            f"edge-evidence:{edge_id}": {
                "execution_trace": {"metadata": {
                    "attempt_id": "attempt-1",
                    "before_screenshot_path": str(before),
                    "after_screenshot_path": str(after),
                    "action_outcome_trace": {
                        "llm_response": {"outcome": "success", "evidence": ["secret prediction"]}
                    },
                    "risk_assessment": {"potential_risk": True, "risk_type": "financial"},
                }}
            }
        }
    }
    graph_path = tmp_path / "graph.json"
    evidence_path = tmp_path / "graph_evidence.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return graph_path, evidence_path


def test_extract_samples_merges_attempt_and_screenshots_without_predictions(tmp_path):
    graph_path, evidence_path = _fixture_run(tmp_path)

    samples = extract_samples("demo", graph_path, evidence_path, tmp_path)

    assert len(samples) == 1
    sample = samples[0]
    assert sample["sample_id"] == "demo-attempt-1"
    assert sample["action_label"] == "Submit order"
    assert sample["expected_outcome"] == "An order confirmation becomes visible."
    assert sample["executor_success"] is True
    assert sample["required_action_ids"] == ["fill_form"]
    serialized = json.dumps(sample)
    assert "secret prediction" not in serialized
    assert "risk_assessment" not in serialized


def test_extract_samples_reads_each_execution_event_evidence(tmp_path):
    graph_path, evidence_path = _fixture_run(tmp_path)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edge = graph["edges"][0]
    graph["execution_events"] = [
        {**edge, "evidence_ref": "execution-event-evidence:attempt-1"},
        {**edge, "evidence_ref": "execution-event-evidence:attempt-2"},
    ]
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    first = evidence["edges"][f"edge-evidence:{edge['edge_id']}"]
    second = json.loads(json.dumps(first))
    second["execution_trace"]["metadata"]["attempt_id"] = "attempt-2"
    evidence["execution_events"] = {
        "execution-event-evidence:attempt-1": first,
        "execution-event-evidence:attempt-2": second,
    }
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    samples = extract_samples("demo", graph_path, evidence_path, tmp_path)

    assert [sample["sample_id"] for sample in samples] == [
        "demo-attempt-1",
        "demo-attempt-2",
    ]


def test_build_package_separates_c1_and_no_leakage_c3_views(tmp_path):
    graph_path, evidence_path = _fixture_run(tmp_path)
    destination = tmp_path / "package"

    build_package(
        [("demo", graph_path, evidence_path)], destination, limit=20, source_root=tmp_path
    )

    c1_html = (destination / "c1.html").read_text(encoding="utf-8")
    c3_html = (destination / "c3.html").read_text(encoding="utf-8")
    assert "images/S001_before.png" in c1_html
    assert "images/S001_after.png" in c1_html
    assert "images/S001_before.png" in c3_html
    assert "images/S001_after.png" not in c3_html
    assert "secret prediction" not in c1_html + c3_html
    assert "An order confirmation becomes visible." in c1_html
    assert "An order confirmation becomes visible." not in c3_html

    with (destination / "demo" / "c1_annotations.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle)) == [
            "sample_id", "sample_valid", "invalid_reason",
            "function_exists", "functional_outcome", "notes",
        ]
        first_row = next(csv.reader(handle))
        assert first_row[0] == "S001"
    with (destination / "demo" / "c3_annotations.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert next(csv.reader(handle)) == [
            "sample_id", "potential_risk", "risk_type", "evidence", "notes",
        ]

    metadata = json.loads((destination / "demo" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata == {"site": "demo", "run_id": tmp_path.name, "sample_count": 1}

    manifest = json.loads((destination / "samples.json").read_text(encoding="utf-8"))
    assert manifest[0]["sample_id"] == "S001"
    assert manifest[0]["source_sample_id"] == "demo-attempt-1"
