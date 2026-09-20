import json
from pathlib import Path

from scripts.paper.extract_c3_runtime_full import extract_runtime_predictions


def test_extract_runtime_predictions_joins_attempt_ids_without_after_data(tmp_path: Path):
    run = tmp_path / "demo" / "full" / "run_01"
    run.mkdir(parents=True)
    graph = {
        "execution_events": [{
            "evidence_ref": "execution-event-evidence:1",
            "execution_trace": {"metadata": {"risk_assessment": {
                "potential_risk": True,
                "risk_type": "sensitive_data",
                "evidence": "Credentials are entered.",
            }}},
        }]
    }
    evidence = {"execution_events": {"execution-event-evidence:1": {
        "execution_trace": {"metadata": {"attempt_id": "attempt-1"}}
    }}}
    (run / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (run / "graph_evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    samples = [{
        "sample_id": "S001",
        "source_sample_id": "demo-attempt-1",
        "site": "demo",
        "run_id": "run_01",
    }]

    predictions, missing = extract_runtime_predictions(samples, tmp_path)

    assert missing == []
    assert predictions == {"S001": {
        "potential_risk": True,
        "risk_type": "sensitive_data",
        "evidence": "Credentials are entered.",
    }}
