import csv
import json
from pathlib import Path

from scripts.paper.prepare_c3_pilot import prepare_pilot


def test_prepare_pilot_stratifies_each_site_and_is_reproducible(tmp_path: Path):
    samples = []
    labels = []
    for site in ("a", "b"):
        for index in range(12):
            sample_id = f"{site}{index:02d}"
            samples.append({"sample_id": sample_id, "site": site})
            labels.append({
                "sample_id": sample_id,
                "potential_risk": "true" if index < 6 else "false",
                "risk_type": "sensitive_data" if index < 6 else "",
                "evidence": "e",
                "notes": "",
            })
    manifest = tmp_path / "samples.json"
    annotations = tmp_path / "annotations.csv"
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    with annotations.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=labels[0])
        writer.writeheader()
        writer.writerows(labels)

    first = prepare_pilot(manifest, annotations, tmp_path / "one", per_site=10, seed=7)
    second = prepare_pilot(manifest, annotations, tmp_path / "two", per_site=10, seed=7)

    assert [sample["sample_id"] for sample in first] == [sample["sample_id"] for sample in second]
    for site in ("a", "b"):
        selected = [sample for sample in first if sample["site"] == site]
        assert len(selected) == 10
        selected_ids = {sample["sample_id"] for sample in selected}
        assert sum(row["potential_risk"] == "true" for row in labels if row["sample_id"] in selected_ids) == 5
