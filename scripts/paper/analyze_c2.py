"""Compute frozen E004 C2 metrics from human-reviewed attempt annotations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _apply_coverage_ledger(
    annotations: list[dict[str, str]], coverage_ledger_path: Path
) -> None:
    attempts_by_key = {
        (
            row["run_id"],
            row["site"],
            row["condition"],
            row["attempt_index"],
        ): row
        for row in annotations
    }
    for entry in _rows(coverage_ledger_path):
        core_attempts = entry.get("core_attempts", "")
        pairs = (
            (item.split("@", 1) for item in core_attempts.split(";") if item)
            if core_attempts
            else [(entry["core_id"], entry["first_supported_attempt"])]
        )
        for core_id, attempt_index in pairs:
            key = (
                entry["run_id"], entry["site"], entry["condition"], attempt_index
            )
            row = attempts_by_key.get(key)
            if row is None:
                raise ValueError(f"coverage ledger references unknown attempt: {key}")
            row["evidence_label"] = "supported"
            row["core_match_status"] = "matched"
            row["core_id"] = core_id


def analyze(
    annotation_path: Path | list[Path],
    core_dir: Path,
    coverage_ledger_path: Path | None = None,
) -> dict:
    annotation_paths = (
        annotation_path if isinstance(annotation_path, list) else [annotation_path]
    )
    annotations = [
        row for path in annotation_paths for row in _rows(path)
    ]
    if coverage_ledger_path is not None:
        _apply_coverage_ledger(annotations, coverage_ledger_path)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        grouped[(row["run_id"], row["site"], row["condition"])].append(row)

    core_totals = {}
    for path in core_dir.glob("*.csv"):
        core_totals[path.stem] = len(_rows(path))

    runs = []
    for (run_id, site, condition), attempts in sorted(grouped.items()):
        attempts.sort(key=lambda row: int(row.get("attempt_index") or 0))
        supported_keys: set[tuple[str, str]] = set()
        supported_core: set[str] = set()
        growth = []
        for row in attempts:
            if (
                row.get("evidence_label", "").strip().lower() == "supported"
                and _truthy(row.get("evidence_complete"))
            ):
                supported_keys.add(
                    (row.get("semantic_location", ""), row.get("canonical_action_id", ""))
                )
                if row.get("core_match_status", "").strip().lower() == "matched":
                    core_id = row.get("core_id", "").strip()
                    if core_id:
                        supported_core.add(core_id)
            growth.append(len(supported_core))

        attempt_count = len(attempts)
        core_total = core_totals.get(site, 0)
        runs.append({
            "run_id": run_id,
            "site": site,
            "condition": condition,
            "candidate_attempts": attempt_count,
            "supported_functions": len(supported_keys),
            "covered_functions": len(supported_core),
            "supported_noncore_count": len(supported_keys) - len(supported_core),
            "function_total": core_total,
            "function_coverage": (
                len(supported_core) / core_total if core_total else None
            ),
            "effective_attempt_rate": (
                len(supported_core) / attempt_count if attempt_count else None
            ),
            "failed_attempts": sum(
                row.get("executor_status", "").strip().lower() == "failed"
                for row in attempts
            ),
            "evidence_incomplete_attempts": sum(
                not _truthy(row.get("evidence_complete")) for row in attempts
            ),
            "coverage_growth_curve": growth,
        })
    return {"schema_version": "e004-c2-metrics-v1", "runs": runs}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path, nargs="+")
    parser.add_argument("--core-dir", type=Path, required=True)
    parser.add_argument("--coverage-ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.annotations, args.core_dir, args.coverage_ledger)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
