"""Freeze the C3 primary set by excluding within-run repeated actions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read_annotations(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("annotation CSV has no header")
        rows = list(reader)
    by_id = {row["sample_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("annotation CSV contains duplicate sample IDs")
    return list(reader.fieldnames), by_id


def build_primary_dataset(
    manifest_path: Path,
    annotations_path: Path,
    primary_manifest_path: Path,
    primary_annotations_path: Path,
    exclusion_ledger_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("sample manifest must be a list")
    annotation_fields, annotations = _read_annotations(annotations_path)

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    first_by_key: dict[tuple[str, str, str, str], str] = {}
    for sample in samples:
        sample_id = str(sample.get("sample_id", ""))
        if sample_id not in annotations:
            raise ValueError(f"missing annotation for sample: {sample_id}")
        key = (
            str(sample.get("site", "")),
            str(sample.get("run_id", "")),
            str(sample.get("semantic_location", "")),
            str(sample.get("action_id", "")),
        )
        kept_sample_id = first_by_key.get(key)
        if kept_sample_id is not None:
            excluded.append({
                "sample_id": sample_id,
                "kept_sample_id": kept_sample_id,
                "reason": "duplicate_within_run_location_action",
            })
            continue
        first_by_key[key] = sample_id
        selected.append(sample)

    primary_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    primary_manifest_path.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with primary_annotations_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=annotation_fields)
        writer.writeheader()
        writer.writerows(annotations[sample["sample_id"]] for sample in selected)
    with exclusion_ledger_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["sample_id", "kept_sample_id", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(excluded)
    return selected, excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    selected, excluded = build_primary_dataset(
        args.manifest,
        args.annotations,
        args.destination / "c3_primary_samples.json",
        args.destination / "c3_primary_annotations_ai_initial.csv",
        args.destination / "c3_excluded_within_run_repeats.csv",
    )
    print(f"Selected {len(selected)} primary samples; excluded {len(excluded)} repeats.")


if __name__ == "__main__":
    main()
