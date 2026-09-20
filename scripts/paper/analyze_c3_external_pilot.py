"""Analyze the paired C3 external context-challenge pilot."""

from __future__ import annotations

import argparse
import csv
import json
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
