"""Compute C1 knowledge-admission metrics from aggregated knowledge keys."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Hashable, Mapping, Set
from pathlib import Path
from typing import Any


def compute_admission_metrics(
    *,
    candidates: Set[Hashable],
    supported: Set[Hashable],
    admissions: Mapping[str, Set[Hashable]],
) -> dict[str, dict[str, Any]]:
    """Return admission precision, supported retention, yield, and F1."""
    result: dict[str, dict[str, Any]] = {}
    for method, admitted_keys in admissions.items():
        true_positive = len(admitted_keys & supported)
        precision = true_positive / len(admitted_keys) if admitted_keys else None
        retention = true_positive / len(supported) if supported else None
        admission_yield = len(admitted_keys) / len(candidates) if candidates else None
        f1 = (
            2 * precision * retention / (precision + retention)
            if precision is not None and retention is not None and precision + retention
            else None
        )
        result[method] = {
            "admitted": len(admitted_keys),
            "true_positive": true_positive,
            "precision": precision,
            "supported_knowledge_retention": retention,
            "admission_yield": admission_yield,
            "f1": f1,
        }
    return result


def _gold_supported(
    *, site: str, package: Path, gold_path: Path, legacy_run_grouping: bool
) -> set[tuple[str, str, str]]:
    samples = json.loads((package / "samples.json").read_text(encoding="utf-8"))
    with gold_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ordered: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for sample in samples:
        parts = [site]
        if legacy_run_grouping:
            parts.append(sample["run_id"])
        parts.extend([sample.get("semantic_location", ""), sample["action_id"]])
        key = tuple(parts)
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    if len(ordered) != len(rows):
        raise ValueError(
            f"{site}: {len(ordered)} grouped samples but {len(rows)} gold rows"
        )
    return {
        (site, key[-2], key[-1])
        for key, row in zip(ordered, rows)
        if row["sample_valid"].lower() == "true"
        and row["function_exists"].lower() == "yes"
        and row["functional_outcome"].lower() == "success"
    }


def _artifact_exists(root: Path, value: str | None) -> bool:
    if not value:
        return False
    path = Path(value)
    return (path if path.is_absolute() else root / path).is_file()


def analyze_experiment(
    *, root: Path, site_configs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Load frozen runs and confirmed gold labels, then compute C1 metrics."""
    all_candidates: set[tuple[str, str, str]] = set()
    all_supported: set[tuple[str, str, str]] = set()
    all_executor: set[tuple[str, str, str]] = set()
    all_evidence: set[tuple[str, str, str]] = set()
    site_results: dict[str, Any] = {}
    for site, config in site_configs.items():
        package = Path(config["package"])
        supported = _gold_supported(
            site=site,
            package=package,
            gold_path=package / str(config["gold"]),
            legacy_run_grouping=bool(config.get("legacy_run_grouping")),
        )
        candidates: set[tuple[str, str, str]] = set()
        executor: set[tuple[str, str, str]] = set()
        evidence_admitted: set[tuple[str, str, str]] = set()
        attempt_count = 0
        evidence_complete_count = 0
        for run in sorted(Path(config["runs"]).glob("run_*")):
            graph_path = run / "graph.json"
            evidence_path = run / "graph_evidence.json"
            if not graph_path.is_file() or not evidence_path.is_file():
                continue
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            nodes = {node["node_id"]: node for node in graph.get("nodes", [])}
            for node in graph.get("nodes", []):
                location = node.get("semantic_location_hint", "")
                for affordance in node.get("business_affordances", []):
                    action_id = affordance.get("action_name") or affordance.get("action_id")
                    if action_id:
                        candidates.add((site, location, action_id))
            for event in graph.get("execution_events", []):
                attempt_count += 1
                action = event.get("action", {})
                action_id = action.get("semantic_id") or action.get("action_id")
                semantic = event.get("semantic_observation") or {}
                location = semantic.get("source_location") or nodes.get(
                    event.get("source_node_id"), {}
                ).get("semantic_location_hint", "")
                key = (site, location, action_id)
                candidates.add(key)
                detail = evidence.get("execution_events", {}).get(
                    event.get("evidence_ref", ""), {}
                )
                metadata = detail.get("execution_trace", {}).get("metadata", {})
                if metadata.get("backend_reported_success") is True:
                    executor.add(key)
                complete = _artifact_exists(
                    root, metadata.get("before_screenshot_path")
                ) and _artifact_exists(root, metadata.get("after_screenshot_path"))
                evidence_complete_count += int(complete)
                outcome = (
                    metadata.get("action_outcome_trace", {}).get("llm_response") or {}
                ).get("outcome")
                if complete and outcome == "success":
                    evidence_admitted.add(key)
        admissions = {
            "proposal_as_fact": set(candidates),
            "executor_success_as_fact": executor,
            "evidence_grounded": evidence_admitted,
        }
        errors = {
            method: {
                "false_positives": [list(key) for key in sorted(admitted - supported)],
                "false_negatives": [list(key) for key in sorted(supported - admitted)],
            }
            for method, admitted in admissions.items()
        }
        site_results[site] = {
            "candidate_functions": len(candidates),
            "supported_functions": len(supported),
            "attempts": attempt_count,
            "evidence_complete_attempts": evidence_complete_count,
            "metrics": compute_admission_metrics(
                candidates=candidates, supported=supported, admissions=admissions
            ),
            "errors": errors,
        }
        all_candidates |= candidates
        all_supported |= supported
        all_executor |= executor
        all_evidence |= evidence_admitted
    overall_admissions = {
        "proposal_as_fact": all_candidates,
        "executor_success_as_fact": all_executor,
        "evidence_grounded": all_evidence,
    }
    return {
        "aggregation_key": ["site", "semantic_location", "canonical_action_id"],
        "gold_rule": (
            "supported when at least one valid grouped attempt has "
            "function_exists=yes and functional_outcome=success"
        ),
        "admission_rules": {
            "proposal_as_fact": "admit every proposed candidate function",
            "executor_success_as_fact": (
                "admit when at least one attempt has backend_reported_success=true"
            ),
            "evidence_grounded": (
                "admit when at least one evidence-complete attempt has "
                "system outcome=success"
            ),
        },
        "sites": site_results,
        "overall": {
            "candidate_functions": len(all_candidates),
            "supported_functions": len(all_supported),
            "metrics": compute_admission_metrics(
                candidates=all_candidates,
                supported=all_supported,
                admissions=overall_admissions,
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path("paper/experiments/results/E003/final/c1_metrics.json"),
    )
    args = parser.parse_args()
    root = Path.cwd()
    configs = {
        "saucedemo": {
            "runs": root / "outputs/paper/formal/E003_c1_v1/saucedemo",
            "package": root / "outputs/paper/formal/E003_c1_v1/annotation_package_saucedemo_v2",
            "gold": root / "paper/experiments/results/E003/final/gold/saucedemo.csv",
            "legacy_run_grouping": True,
        },
        "practice-shopping": {
            "runs": root / "outputs/paper/formal/E003_c1_v4/practice_shopping",
            "package": root / "outputs/paper/formal/E003_c1_v4/practice_shopping/annotation_package_practice_shopping_v4",
            "gold": root / "paper/experiments/results/E003/final/gold/practice_shopping.csv",
            "legacy_run_grouping": False,
        },
    }
    result = analyze_experiment(root=root, site_configs=configs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
