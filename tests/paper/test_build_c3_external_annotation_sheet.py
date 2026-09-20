import csv
import json
from pathlib import Path

from scripts.paper.build_c3_external_annotation_sheet import build_annotation_sheet


def test_build_annotation_sheet_is_shuffled_blind_and_complete(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    samples = [
        {
            "sample_id": f"EXTF{index:03d}",
            "subset": "context_pair",
            "pair_id": f"PAIR{(index + 1) // 2:03d}",
            "site": "demo",
            "action_label": f"Click action {index}.",
            "source_screenshot_id": f"source-{index}",
        }
        for index in range(1, 7)
    ]
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    for sample in samples:
        (screenshot_dir / f'{sample["sample_id"]}.png').write_bytes(b"image")

    count = build_annotation_sheet(
        manifest, screenshot_dir, tmp_path / "annotations.csv", seed=20260920
    )

    assert count == 6
    with (tmp_path / "annotations.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
        columns = handle.seek(0)  # Keep the file handle exercised on Windows.
    assert len(rows) == 6
    assert [row["sample_id"] for row in rows] != [
        sample["sample_id"] for sample in samples
    ]
    assert set(rows[0]) == {
        "sample_id", "action_label", "screenshot_path", "potential_risk",
        "acceptable_risk_types", "evidence", "notes", "review_status",
    }
    serialized = json.dumps(rows).lower()
    assert "pair_id" not in serialized
    assert "source_screenshot_id" not in serialized
    assert "webguard" not in serialized
    assert all(not row["potential_risk"] for row in rows)


def test_build_annotation_sheet_rejects_missing_screenshot(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{
        "sample_id": "EXTF001", "action_label": "Click Save."
    }]), encoding="utf-8")
    (tmp_path / "screenshots").mkdir()

    try:
        build_annotation_sheet(
            manifest, tmp_path / "screenshots", tmp_path / "annotations.csv"
        )
    except FileNotFoundError as exc:
        assert "EXTF001" in str(exc)
    else:
        raise AssertionError("Expected missing screenshot to fail")
