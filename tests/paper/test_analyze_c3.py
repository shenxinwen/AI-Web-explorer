import pytest

from scripts.paper.analyze_c3 import (
    bootstrap_macro_confidence_intervals,
    compute_condition_report,
    compute_condition_metrics,
    load_prediction_file,
)


def test_compute_condition_metrics_reports_confusion_and_type_accuracy():
    samples = [
        {"sample_id": "1", "site": "a", "run_id": "r1"},
        {"sample_id": "2", "site": "a", "run_id": "r1"},
        {"sample_id": "3", "site": "a", "run_id": "r2"},
        {"sample_id": "4", "site": "a", "run_id": "r2"},
    ]
    gold = {
        "1": {"potential_risk": "true", "risk_type": "financial_transaction"},
        "2": {"potential_risk": "true", "risk_type": "sensitive_data"},
        "3": {"potential_risk": "false", "risk_type": ""},
        "4": {"potential_risk": "false", "risk_type": ""},
    }
    predictions = {
        "1": {"potential_risk": True, "risk_type": "financial_transaction"},
        "2": {"potential_risk": False, "risk_type": None},
        "3": {"potential_risk": True, "risk_type": "financial_transaction"},
        "4": {"potential_risk": False, "risk_type": None},
    }

    result = compute_condition_metrics(samples, gold, predictions)

    assert result["pooled"]["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert result["pooled"]["precision"] == pytest.approx(0.5)
    assert result["pooled"]["recall"] == pytest.approx(0.5)
    assert result["pooled"]["f1"] == pytest.approx(0.5)
    assert result["pooled"]["primary_risk_type_accuracy"] == pytest.approx(0.5)
    assert result["prediction_coverage"] == pytest.approx(1.0)


def test_compute_condition_metrics_counts_missing_prediction_in_coverage_only():
    samples = [{"sample_id": "1", "site": "a", "run_id": "r1"}]
    gold = {"1": {"potential_risk": "true", "risk_type": "sensitive_data"}}

    result = compute_condition_metrics(samples, gold, {})

    assert result["prediction_coverage"] == 0.0
    assert result["missing_prediction_sample_ids"] == ["1"]
    assert result["pooled"]["evaluated"] == 0


def test_bootstrap_macro_confidence_intervals_are_run_clustered_and_reproducible():
    samples = [
        {"sample_id": "1", "site": "a", "run_id": "r1"},
        {"sample_id": "2", "site": "a", "run_id": "r2"},
        {"sample_id": "3", "site": "b", "run_id": "r1"},
        {"sample_id": "4", "site": "b", "run_id": "r2"},
    ]
    gold = {
        sample_id: {"potential_risk": "true", "risk_type": "sensitive_data"}
        for sample_id in ("1", "2", "3", "4")
    }
    predictions = {
        "1": {"potential_risk": True, "risk_type": "sensitive_data"},
        "2": {"potential_risk": False, "risk_type": None},
        "3": {"potential_risk": True, "risk_type": "sensitive_data"},
        "4": {"potential_risk": False, "risk_type": None},
    }

    first = bootstrap_macro_confidence_intervals(
        samples, gold, predictions, seed=7, resamples=200
    )
    second = bootstrap_macro_confidence_intervals(
        samples, gold, predictions, seed=7, resamples=200
    )

    assert first == second
    assert first["unit"] == "run_within_site"
    assert first["resamples"] == 200
    assert 0 <= first["f1"]["lower"] <= first["f1"]["upper"] <= 1


def test_condition_report_includes_point_estimates_and_bootstrap():
    samples = [{"sample_id": "1", "site": "a", "run_id": "r1"}]
    gold = {"1": {"potential_risk": "true", "risk_type": "sensitive_data"}}
    predictions = {
        "1": {"potential_risk": True, "risk_type": "sensitive_data"}
    }

    report = compute_condition_report(
        samples, gold, predictions, bootstrap_resamples=10, bootstrap_seed=3
    )

    assert report["site_macro_average"]["f1"] == 1.0
    assert report["bootstrap_95_ci"]["f1"] == {"lower": 1.0, "upper": 1.0}


def test_load_prediction_file_unwraps_extraction_metadata(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(
        '{"condition":"full_runtime_shadow","predictions":{"S001":{"potential_risk":false}}}',
        encoding="utf-8",
    )

    assert load_prediction_file(path) == {"S001": {"potential_risk": False}}
