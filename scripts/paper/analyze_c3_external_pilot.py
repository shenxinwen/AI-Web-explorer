"""Analyze the paired C3 external context-challenge pilot."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.paper.analyze_c3 import compute_condition_metrics, load_predictions
except ModuleNotFoundError:  # Direct execution from scripts/paper.
    from analyze_c3 import compute_condition_metrics, load_predictions


def _is_true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def compute_pair_metrics(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pairs: dict[str, list[str]] = {}
    for sample in samples:
        pairs.setdefault(str(sample["pair_id"]), []).append(str(sample["sample_id"]))
    pair_results = {}
    for pair_id, sample_ids in sorted(pairs.items()):
        if len(sample_ids) != 2 or any(sample_id not in predictions for sample_id in sample_ids):
            continue
        gold_values = [_is_true(gold[sample_id]["potential_risk"]) for sample_id in sample_ids]
        predicted_values = [
            _is_true(predictions[sample_id]["potential_risk"]) for sample_id in sample_ids
        ]
        if len(set(gold_values)) != 2:
            continue
        both_correct = predicted_values == gold_values
        correct_flip = both_correct and len(set(predicted_values)) == 2
        pair_results[pair_id] = {
            "sample_ids": sample_ids,
            "both_correct": both_correct,
            "correct_flip": correct_flip,
        }
    eligible = len(pair_results)
    return {
        "eligible_pairs": eligible,
        "joint_accuracy": (
            sum(item["both_correct"] for item in pair_results.values()) / eligible
            if eligible
            else None
        ),
        "correct_risk_flip_rate": (
            sum(item["correct_flip"] for item in pair_results.values()) / eligible
            if eligible
            else None
        ),
        "pair_results": pair_results,
    }


def compute_acceptable_type_accuracy(
    gold: Mapping[str, Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    positives = correct = 0
    for sample_id, label in gold.items():
        if not _is_true(label["potential_risk"]):
            continue
        positives += 1
        acceptable = {
            item.strip()
            for item in str(label.get("acceptable_risk_types", "")).split(";")
            if item.strip()
        }
        prediction = predictions.get(sample_id, {})
        if _is_true(prediction.get("potential_risk")) and prediction.get("risk_type") in acceptable:
            correct += 1
    return {
        "gold_positive": positives,
        "correct": correct,
        "accuracy": correct / positives if positives else None,
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def compute_cluster_bootstrap(
    samples: list[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, Any]],
    text_predictions: Mapping[str, Mapping[str, Any]],
    full_predictions: Mapping[str, Mapping[str, Any]],
    *,
    iterations: int = 10000,
    seed: int = 20260920,
) -> dict[str, Any]:
    paired: dict[str, list[str]] = {}
    clusters: list[list[str]] = []
    for sample in samples:
        sample_id = str(sample["sample_id"])
        pair_id = str(sample.get("pair_id") or "")
        if pair_id:
            paired.setdefault(pair_id, []).append(sample_id)
        else:
            clusters.append([sample_id])
    clusters.extend(paired[pair_id] for pair_id in sorted(paired))

    def scores(selected: list[list[str]], predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, float | None]:
        ids = [sample_id for cluster in selected for sample_id in cluster]
        tp = fp = fn = 0
        type_total = type_correct = 0
        for sample_id in ids:
            actual = _is_true(gold[sample_id]["potential_risk"])
            predicted = _is_true(predictions[sample_id]["potential_risk"])
            tp += actual and predicted
            fp += not actual and predicted
            fn += actual and not predicted
            if actual:
                type_total += 1
                acceptable = {
                    item.strip() for item in str(
                        gold[sample_id].get("acceptable_risk_types", "")
                    ).split(";") if item.strip()
                }
                type_correct += predicted and predictions[sample_id].get("risk_type") in acceptable
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        eligible_pairs = pair_correct = 0
        for cluster in selected:
            if len(cluster) != 2:
                continue
            actuals = [_is_true(gold[sample_id]["potential_risk"]) for sample_id in cluster]
            if len(set(actuals)) != 2:
                continue
            eligible_pairs += 1
            predicted_values = [
                _is_true(predictions[sample_id]["potential_risk"])
                for sample_id in cluster
            ]
            pair_correct += predicted_values == actuals
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "acceptable_type_accuracy": type_correct / type_total if type_total else 0.0,
            "pair_joint_accuracy": pair_correct / eligible_pairs if eligible_pairs else None,
        }

    observed = {
        "text": scores(clusters, text_predictions),
        "full": scores(clusters, full_predictions),
    }
    rng = random.Random(seed)
    distributions = {
        condition: {metric: [] for metric in metrics}
        for condition, metrics in observed.items()
    }
    deltas = {metric: [] for metric in observed["text"]}
    for _ in range(iterations):
        selected = [rng.choice(clusters) for _ in clusters]
        replicate = {
            "text": scores(selected, text_predictions),
            "full": scores(selected, full_predictions),
        }
        for condition in ("text", "full"):
            for metric, value in replicate[condition].items():
                if value is not None:
                    distributions[condition][metric].append(value)
        for metric in deltas:
            text_value = replicate["text"][metric]
            full_value = replicate["full"][metric]
            if text_value is not None and full_value is not None:
                deltas[metric].append(full_value - text_value)

    def summarize(estimate: float | None, values: list[float]) -> dict[str, Any]:
        return {
            "estimate": estimate,
            "ci95": [_percentile(values, 0.025), _percentile(values, 0.975)]
            if values else None,
        }

    return {
        "seed": seed,
        "iterations": iterations,
        "clusters": len(clusters),
        "text": {
            metric: summarize(value, distributions["text"][metric])
            for metric, value in observed["text"].items()
        },
        "full": {
            metric: summarize(value, distributions["full"][metric])
            for metric, value in observed["full"].items()
        },
        "delta_full_minus_text": {
            metric: summarize(
                None if observed["text"][metric] is None or observed["full"][metric] is None
                else observed["full"][metric] - observed["text"][metric],
                deltas[metric],
            )
            for metric in deltas
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    samples = json.loads(args.manifest.read_text(encoding="utf-8"))
    with args.gold.open(encoding="utf-8-sig", newline="") as handle:
        gold = {row["sample_id"]: row for row in csv.DictReader(handle)}
    results = {}
    for condition in ("action_only", "action_taxonomy", "action_visual", "full"):
        predictions = load_predictions(args.predictions, condition)
        results[condition] = {
            "classification": compute_condition_metrics(samples, gold, predictions),
            "acceptable_type": compute_acceptable_type_accuracy(gold, predictions),
            "context_pairs": compute_pair_metrics(samples, gold, predictions),
        }
    text_predictions = load_predictions(args.predictions, "action_taxonomy")
    full_predictions = load_predictions(args.predictions, "full")
    if text_predictions and full_predictions:
        results["comparison_bootstrap"] = compute_cluster_bootstrap(
            samples, gold, text_predictions, full_predictions
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
