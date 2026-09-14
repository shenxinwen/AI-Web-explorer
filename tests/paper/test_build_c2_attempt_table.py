import json

from scripts.paper.build_c2_attempt_table import extract_attempts


def test_extract_attempts_retains_missing_screenshot_and_failed_event(tmp_path):
    graph = tmp_path / "graph.json"
    evidence = tmp_path / "evidence.json"
    graph.write_text(json.dumps({
        "meta": {"exploration_condition": "ungated_random", "random_seed": 0},
        "nodes": [{"node_id": "n1", "semantic_location_hint": "login"}],
        "execution_events": [{
            "edge_id": "e1", "evidence_ref": "ev1", "source_node_id": "n1",
            "action": {"semantic_id": "submit_login"},
            "execution_trace": {"success": False},
        }],
    }), encoding="utf-8")
    evidence.write_text(json.dumps({"execution_events": {"ev1": {
        "execution_trace": {"metadata": {"attempt_id": "a1"}}
    }}}), encoding="utf-8")

    rows = extract_attempts("saucedemo", "run-1", graph, evidence)

    assert len(rows) == 1
    assert rows[0]["attempt_id"] == "a1"
    assert rows[0]["executor_status"] == "failed"
    assert rows[0]["evidence_complete"] == "false"
    assert rows[0]["random_seed"] == "0"
