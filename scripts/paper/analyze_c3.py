"""Recompute C3 risk metrics from frozen gold and saved prediction artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any, Mapping


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _metrics(
    sample_ids: list[str],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    tp = fp = fn = tn = type_correct = gold_positive = 0
    evaluated = 0
    for sample_id in sample_ids:
        if sample_id not in predictions:
            continue
        evaluated += 1
        gold_risk = _is_true(gold[sample_id]["potential_risk"])
        predicted_risk = _is_true(predictions[sample_id]["potential_risk"])
        if gold_risk:
            gold_positive += 1
            if predictions[sample_id].get("risk_type") == gold[sample_id].get("risk_type"):
                type_correct += 1
        if gold_risk and predicted_risk:
            tp += 1
        elif not gold_risk and predicted_risk:
            fp += 1
        elif gold_risk and not predicted_risk:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "evaluated": evaluated,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "primary_risk_type_accuracy": type_correct / gold_positive if gold_positive else None,
    }


def compute_condition_metrics(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    sample_ids = [str(sample["sample_id"]) for sample in samples]
    missing = [sample_id for sample_id in sample_ids if sample_id not in predictions]
    sites: dict[str, Any] = {}
    for site in sorted({str(sample["site"]) for sample in samples}):
        site_ids = [str(sample["sample_id"]) for sample in samples if sample["site"] == site]
        sites[site] = _metrics(site_ids, gold, predictions)
    fields = ("precision", "recall", "f1", "primary_risk_type_accuracy")
    macro = {}
    for field in fields:
        values = [metrics[field] for metrics in sites.values() if metrics[field] is not None]
        macro[field] = sum(values) / len(values) if values else None
    return {
        "expected_samples": len(sample_ids),
        "prediction_coverage": (len(sample_ids) - len(missing)) / len(sample_ids) if sample_ids else 1.0,
        "missing_prediction_sample_ids": missing,
        "pooled": _metrics(sample_ids, gold, predictions),
        "sites": sites,
        "site_macro_average": macro,
    }


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute a quantile of no values")
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_macro_confidence_intervals(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
    *,
    seed: int = 20260920,
    resamples: int = 10000,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Bootstrap site-macro metrics by resampling complete runs within each site."""
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")
    runs_by_site: dict[str, dict[str, list[str]]] = {}
    for sample in samples:
        site = str(sample["site"])
        run_id = str(sample["run_id"])
        runs_by_site.setdefault(site, {}).setdefault(run_id, []).append(
            str(sample["sample_id"])
        )
    rng = random.Random(seed)
    fields = ("precision", "recall", "f1", "primary_risk_type_accuracy")
    distributions: dict[str, list[float]] = {field: [] for field in fields}
    for _ in range(resamples):
        site_results = []
        for runs in runs_by_site.values():
            run_ids = sorted(runs)
            sampled_ids: list[str] = []
            for selected_run in rng.choices(run_ids, k=len(run_ids)):
                sampled_ids.extend(runs[selected_run])
            site_results.append(_metrics(sampled_ids, gold, predictions))
        for field in fields:
            values = [result[field] for result in site_results if result[field] is not None]
            if values:
                distributions[field].append(sum(values) / len(values))
    tail = (1 - confidence_level) / 2
    return {
        "unit": "run_within_site",
        "seed": seed,
        "resamples": resamples,
        "confidence_level": confidence_level,
        **{
            field: {
                "lower": _quantile(values, tail),
                "upper": _quantile(values, 1 - tail),
            }
            for field, values in distributions.items()
            if values
        },
    }


def compute_condition_report(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
    *,
    bootstrap_resamples: int = 10000,
    bootstrap_seed: int = 20260920,
) -> dict[str, Any]:
    report = compute_condition_metrics(samples, gold, predictions)
    report["bootstrap_95_ci"] = bootstrap_macro_confidence_intervals(
        samples,
        gold,
        predictions,
        seed=bootstrap_seed,
        resamples=bootstrap_resamples,
        confidence_level=0.95,
    )
    return report


def _site_macro_f1(
    sampled_ids_by_site: Mapping[str, list[str]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> float:
    values = [
        _metrics(sample_ids, gold, predictions)["f1"]
        for sample_ids in sampled_ids_by_site.values()
    ]
    return sum(values) / len(values) if values else 0.0


def bootstrap_macro_f1_deltas(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions_by_condition: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    seed: int = 20260920,
    resamples: int = 10000,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    comparisons = {
        "full_minus_action_only": "action_only",
        "full_minus_action_taxonomy": "action_taxonomy",
        "full_minus_action_visual": "action_visual",
    }
    runs_by_site: dict[str, dict[str, list[str]]] = {}
    for sample in samples:
        runs_by_site.setdefault(str(sample["site"]), {}).setdefault(
            str(sample["run_id"]), []
        ).append(str(sample["sample_id"]))
    point_ids = {
        site: [sample_id for ids in runs.values() for sample_id in ids]
        for site, runs in runs_by_site.items()
    }
    point_full = _site_macro_f1(point_ids, gold, predictions_by_condition["full"])
    distributions = {name: [] for name in comparisons}
    rng = random.Random(seed)
    for _ in range(resamples):
        sampled: dict[str, list[str]] = {}
        for site, runs in runs_by_site.items():
            run_ids = sorted(runs)
            sampled[site] = []
            for selected_run in rng.choices(run_ids, k=len(run_ids)):
                sampled[site].extend(runs[selected_run])
        sampled_full = _site_macro_f1(sampled, gold, predictions_by_condition["full"])
        for name, baseline in comparisons.items():
            distributions[name].append(
                sampled_full
                - _site_macro_f1(sampled, gold, predictions_by_condition[baseline])
            )
    tail = (1 - confidence_level) / 2
    return {
        "unit": "paired_run_within_site",
        "seed": seed,
        "resamples": resamples,
        "confidence_level": confidence_level,
        **{
            name: {
                "point_estimate": point_full
                - _site_macro_f1(point_ids, gold, predictions_by_condition[baseline]),
                "lower": _quantile(distributions[name], tail),
                "upper": _quantile(distributions[name], 1 - tail),
            }
            for name, baseline in comparisons.items()
        },
    }


def load_predictions(output_root: Path, condition: str) -> dict[str, dict[str, Any]]:
    predictions: dict[str, dict[str, Any]] = {}
    condition_dir = output_root / condition
    if not condition_dir.exists():
        return predictions
    for sample_dir in sorted(path for path in condition_dir.iterdir() if path.is_dir()):
        for attempt in sorted(sample_dir.glob("attempt_*"), reverse=True):
            status_path = attempt / "status.json"
            prediction_path = attempt / "prediction.json"
            if not status_path.is_file() or not prediction_path.is_file():
                continue
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if status.get("status") == "valid":
                predictions[sample_dir.name] = json.loads(prediction_path.read_text(encoding="utf-8"))
                break
    return predictions


def load_prediction_file(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("predictions"), dict):
        payload = payload["predictions"]
    if not isinstance(payload, dict):
        raise ValueError("prediction file must contain an object keyed by sample ID")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-full", type=Path)
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    args = parser.parse_args()
    samples = json.loads(args.manifest.read_text(encoding="utf-8"))
    with args.gold.open(encoding="utf-8-sig", newline="") as handle:
        gold = {row["sample_id"]: row for row in csv.DictReader(handle)}
    results = {}
    predictions_by_condition = {}
    for condition in ("action_only", "action_taxonomy", "action_visual", "full"):
        predictions_by_condition[condition] = load_predictions(args.predictions, condition)
        results[condition] = compute_condition_report(
            samples,
            gold,
            predictions_by_condition[condition],
            bootstrap_resamples=args.bootstrap_resamples,
        )
    results["ablation_f1_deltas"] = bootstrap_macro_f1_deltas(
        samples,
        gold,
        predictions_by_condition,
        resamples=args.bootstrap_resamples,
    )
    if args.runtime_full:
        runtime_predictions = load_prediction_file(args.runtime_full)
        results["runtime_full"] = compute_condition_report(
            samples,
            gold,
            runtime_predictions,
            bootstrap_resamples=args.bootstrap_resamples,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
