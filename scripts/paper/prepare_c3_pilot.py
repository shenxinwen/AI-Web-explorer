"""Select a deterministic, label-balanced C3 readiness pilot."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any


def prepare_pilot(
    manifest_path: Path,
    annotations_path: Path,
    destination: Path,
    *,
    per_site: int = 10,
    seed: int = 20260920,
) -> list[dict[str, Any]]:
    if per_site % 2:
        raise ValueError("per_site must be even for a balanced pilot")
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    with annotations_path.open(encoding="utf-8-sig", newline="") as handle:
        labels = {row["sample_id"]: row for row in csv.DictReader(handle)}
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for site in sorted({sample["site"] for sample in samples}):
        site_samples = [sample for sample in samples if sample["site"] == site]
        positives = [sample for sample in site_samples if labels[sample["sample_id"]]["potential_risk"].lower() == "true"]
        negatives = [sample for sample in site_samples if labels[sample["sample_id"]]["potential_risk"].lower() == "false"]
        half = per_site // 2
        if len(positives) < half or len(negatives) < half:
            raise ValueError(f"site {site} lacks samples for a balanced pilot")
        rng.shuffle(positives)
        rng.shuffle(negatives)
        chosen_ids = {sample["sample_id"] for sample in positives[:half] + negatives[:half]}
        selected.extend(sample for sample in site_samples if sample["sample_id"] in chosen_ids)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "pilot_samples.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destination / "pilot_sample_ids.txt").write_text(
        "\n".join(sample["sample_id"] for sample in selected) + "\n", encoding="utf-8"
    )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--per-site", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260920)
    args = parser.parse_args()
    samples = prepare_pilot(
        args.manifest, args.annotations, args.destination,
        per_site=args.per_site, seed=args.seed,
    )
    print(f"Selected {len(samples)} C3 pilot samples.")


if __name__ == "__main__":
    main()
