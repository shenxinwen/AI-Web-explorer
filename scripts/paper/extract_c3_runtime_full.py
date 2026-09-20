"""Extract the C2 runtime Full risk predictions for the frozen C3 sample set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def extract_runtime_predictions(
    samples: list[Mapping[str, Any]], c2_root: Path
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    cache: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    predictions: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for sample in samples:
        site = str(sample["site"])
        run_id = str(sample["run_id"])
        key = (site, run_id)
        if key not in cache:
            run_dir = c2_root / site / "full" / run_id
            graph = json.loads((run_dir / "graph.json").read_text(encoding="utf-8"))
            evidence = json.loads((run_dir / "graph_evidence.json").read_text(encoding="utf-8"))
            by_attempt: dict[str, dict[str, Any]] = {}
            for event in graph.get("execution_events", []):
                ref = event.get("evidence_ref", "")
                detail = evidence.get("execution_events", {}).get(ref, {})
                attempt_id = str(
                    detail.get("execution_trace", {}).get("metadata", {}).get("attempt_id", "")
                )
                assessment = event.get("execution_trace", {}).get("metadata", {}).get("risk_assessment")
                if attempt_id and isinstance(assessment, dict):
                    by_attempt[attempt_id] = assessment
            cache[key] = by_attempt
        prefix = f"{site}-"
        source_sample_id = str(sample.get("source_sample_id", ""))
        attempt_id = source_sample_id[len(prefix):] if source_sample_id.startswith(prefix) else ""
        assessment = cache[key].get(attempt_id)
        if assessment is None:
            missing.append(str(sample["sample_id"]))
        else:
            predictions[str(sample["sample_id"])] = {
                "potential_risk": assessment.get("potential_risk"),
                "risk_type": assessment.get("risk_type"),
                "evidence": assessment.get("evidence"),
            }
    return predictions, missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--c2-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    samples = json.loads(args.manifest.read_text(encoding="utf-8"))
    predictions, missing = extract_runtime_predictions(samples, args.c2_root)
    payload = {
        "condition": "full_runtime_shadow",
        "prediction_count": len(predictions),
        "missing_sample_ids": missing,
        "predictions": predictions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(predictions)} predictions; missing {len(missing)}.")


if __name__ == "__main__":
    main()
