from scripts.paper.analyze_c3_external_pilot import (
    compute_cluster_bootstrap,
    compute_acceptable_type_accuracy,
    compute_error_analysis,
    compute_pair_metrics,
)


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


def test_acceptable_type_accuracy_accepts_any_human_approved_category():
    gold = {
        "a": {
            "potential_risk": "true",
            "acceptable_risk_types": "sensitive_data;financial_transaction",
        },
        "b": {
            "potential_risk": "true",
            "acceptable_risk_types": "external_communication",
        },
        "c": {"potential_risk": "false", "acceptable_risk_types": ""},
    }
    predictions = {
        "a": {"potential_risk": True, "risk_type": "financial_transaction"},
        "b": {"potential_risk": True, "risk_type": "sensitive_data"},
        "c": {"potential_risk": False, "risk_type": None},
    }

    result = compute_acceptable_type_accuracy(gold, predictions)

    assert result == {"gold_positive": 2, "correct": 1, "accuracy": 0.5}


def test_cluster_bootstrap_preserves_pairs_and_reports_exact_perfect_gain():
    samples = [
        {"sample_id": "safe", "pair_id": "p1"},
        {"sample_id": "risk", "pair_id": "p1"},
    ]
    gold = {
        "safe": {"potential_risk": "false", "acceptable_risk_types": ""},
        "risk": {
            "potential_risk": "true",
            "acceptable_risk_types": "sensitive_data",
        },
    }
    text_predictions = {
        "safe": {"potential_risk": False, "risk_type": None},
        "risk": {"potential_risk": False, "risk_type": None},
    }
    full_predictions = {
        "safe": {"potential_risk": False, "risk_type": None},
        "risk": {"potential_risk": True, "risk_type": "sensitive_data"},
    }

    result = compute_cluster_bootstrap(
        samples, gold, text_predictions, full_predictions, iterations=100, seed=7
    )

    assert result["clusters"] == 1
    assert result["iterations"] == 100
    assert result["delta_full_minus_text"]["f1"] == {
        "estimate": 1.0, "ci95": [1.0, 1.0]
    }
    assert result["delta_full_minus_text"]["pair_joint_accuracy"] == {
        "estimate": 1.0, "ci95": [1.0, 1.0]
    }
    assert result["full"]["acceptable_type_accuracy"] == {
        "estimate": 1.0, "ci95": [1.0, 1.0]
    }


def test_error_analysis_reports_binary_transitions_and_type_mismatches():
    samples = [
        {"sample_id": "a", "subset": "context_pair", "pair_id": "p1", "site": "one"},
        {"sample_id": "b", "subset": "context_pair", "pair_id": "p1", "site": "two"},
        {"sample_id": "c", "subset": "diversity", "pair_id": "", "site": "three"},
    ]
    gold = {
        "a": {"potential_risk": "true", "acceptable_risk_types": "sensitive_data"},
        "b": {"potential_risk": "false", "acceptable_risk_types": ""},
        "c": {"potential_risk": "true", "acceptable_risk_types": "external_communication"},
    }
    text = {
        "a": {"potential_risk": False, "risk_type": None},
        "b": {"potential_risk": False, "risk_type": None},
        "c": {"potential_risk": True, "risk_type": "sensitive_data"},
    }
    full = {
        "a": {"potential_risk": True, "risk_type": "sensitive_data"},
        "b": {"potential_risk": True, "risk_type": "external_communication"},
        "c": {"potential_risk": True, "risk_type": "external_communication"},
    }

    result = compute_error_analysis(samples, gold, text, full)

    assert result["binary_transitions"] == {
        "corrected_by_context": 1,
        "introduced_by_context": 1,
        "correct_both": 1,
        "wrong_both": 0,
    }
    assert result["type_transitions"] == {
        "corrected_by_context": 2,
        "introduced_by_context": 0,
        "correct_both": 0,
        "wrong_both": 0,
    }
    assert result["full_errors"][0]["sample_id"] == "b"
    assert result["full_errors"][0]["binary_outcome"] == "fp"
