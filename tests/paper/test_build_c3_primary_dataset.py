import csv
import json
from pathlib import Path

from scripts.paper.build_c3_primary_dataset import build_primary_dataset


def test_primary_dataset_keeps_first_action_per_run_location(tmp_path: Path):
    samples = [
        {"sample_id": "S001", "site": "a", "run_id": "run_01", "semantic_location": "cart", "action_id": "checkout"},
        {"sample_id": "S002", "site": "a", "run_id": "run_01", "semantic_location": "cart", "action_id": "checkout"},
        {"sample_id": "S003", "site": "a", "run_id": "run_02", "semantic_location": "cart", "action_id": "checkout"},
        {"sample_id": "S004", "site": "a", "run_id": "run_01", "semantic_location": "checkout", "action_id": "checkout"},
    ]
    labels = [
        {"sample_id": sample["sample_id"], "potential_risk": "true", "risk_type": "financial_transaction", "evidence": "e", "notes": ""}
        for sample in samples
    ]
    manifest = tmp_path / "samples.json"
    annotations = tmp_path / "annotations.csv"
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    with annotations.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=labels[0])
        writer.writeheader()
        writer.writerows(labels)

    selected, excluded = build_primary_dataset(
        manifest,
        annotations,
        tmp_path / "primary_samples.json",
        tmp_path / "primary_annotations.csv",
        tmp_path / "excluded.csv",
    )

    assert [sample["sample_id"] for sample in selected] == ["S001", "S003", "S004"]
    assert excluded == [{
        "sample_id": "S002",
        "kept_sample_id": "S001",
        "reason": "duplicate_within_run_location_action",
    }]


def test_primary_dataset_preserves_labels_for_selected_samples(tmp_path: Path):
    samples = [{"sample_id": "S001", "site": "a", "run_id": "r", "semantic_location": "cart", "action_id": "checkout"}]
    manifest = tmp_path / "samples.json"
    annotations = tmp_path / "annotations.csv"
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    annotations.write_text(
        "sample_id,potential_risk,risk_type,evidence,notes\nS001,true,financial_transaction,visible checkout,\n",
        encoding="utf-8",
    )

    build_primary_dataset(
        manifest,
        annotations,
        tmp_path / "primary_samples.json",
        tmp_path / "primary_annotations.csv",
        tmp_path / "excluded.csv",
    )

    with (tmp_path / "primary_annotations.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{
        "sample_id": "S001",
        "potential_risk": "true",
        "risk_type": "financial_transaction",
        "evidence": "visible checkout",
        "notes": "",
    }]
