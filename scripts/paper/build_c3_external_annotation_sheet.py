"""Build a prediction- and source-label-blind C3 annotation CSV."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


COLUMNS = [
    "sample_id",
    "action_label",
    "screenshot_path",
    "potential_risk",
    "acceptable_risk_types",
    "evidence",
    "notes",
    "review_status",
]


def build_annotation_sheet(
    manifest_path: Path,
    screenshot_dir: Path,
    output_path: Path,
    seed: int = 20260920,
) -> int:
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for sample in samples:
        matches = sorted(screenshot_dir.glob(f'{sample["sample_id"]}.*'))
        if len(matches) != 1:
            raise FileNotFoundError(
                f'Expected exactly one screenshot for {sample["sample_id"]}'
            )
        rows.append({
            "sample_id": sample["sample_id"],
            "action_label": sample["action_label"],
            "screenshot_path": str(matches[0].resolve()),
            "potential_risk": "",
            "acceptable_risk_types": "",
            "evidence": "",
            "notes": "",
            "review_status": "",
        })
    random.Random(seed).shuffle(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260920)
    args = parser.parse_args()
    count = build_annotation_sheet(
        args.manifest, args.screenshots, args.output, args.seed
    )
    print(f"Built blind annotation sheet for {count} samples at {args.output.resolve()}")


if __name__ == "__main__":
    main()
