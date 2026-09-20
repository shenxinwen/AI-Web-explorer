from scripts.paper.analyze_c3_external_pilot import compute_pair_metrics


def test_compute_pair_metrics_reports_joint_accuracy_and_correct_flip_rate():
    samples = [
        {"sample_id": "a", "pair_id": "p1"},
        {"sample_id": "b", "pair_id": "p1"},
        {"sample_id": "c", "pair_id": "p2"},
        {"sample_id": "d", "pair_id": "p2"},
    ]
    gold = {
        "a": {"potential_risk": "false"},
        "b": {"potential_risk": "true"},
        "c": {"potential_risk": "false"},
        "d": {"potential_risk": "true"},
    }
    predictions = {
        "a": {"potential_risk": False},
        "b": {"potential_risk": True},
        "c": {"potential_risk": False},
        "d": {"potential_risk": False},
    }

    result = compute_pair_metrics(samples, gold, predictions)

    assert result["eligible_pairs"] == 2
    assert result["joint_accuracy"] == 0.5
    assert result["correct_risk_flip_rate"] == 0.5
    assert result["pair_results"]["p1"]["both_correct"] is True
    assert result["pair_results"]["p2"]["correct_flip"] is False
