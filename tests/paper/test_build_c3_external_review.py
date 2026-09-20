import csv
import json
from pathlib import Path

from scripts.paper.build_c3_external_review import build_review_package


def test_build_review_package_groups_pairs_and_exports_editable_gold(tmp_path: Path):
    image_root = tmp_path / "source_images"
    image_root.mkdir()
    (image_root / "safe.png").write_bytes(b"safe")
    (image_root / "risk.png").write_bytes(b"risk")
    samples = [
        {
            "sample_id": "EXT001",
            "pair_id": "save_01",
            "site": "mail",
            "semantic_location": "theme_picker",
            "action_label": "Click Save.",
            "before_image": "safe.png",
        },
        {
            "sample_id": "EXT002",
            "pair_id": "save_01",
            "site": "shop",
            "semantic_location": "billing_information",
            "action_label": "Click Save.",
            "before_image": "risk.png",
        },
    ]
    manifest = tmp_path / "samples.json"
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "sample_id", "pair_id", "potential_risk", "risk_type",
            "acceptable_risk_types", "evidence", "review_status",
        ])
        writer.writeheader()
        writer.writerow({
            "sample_id": "EXT001", "pair_id": "save_01",
            "potential_risk": "false", "risk_type": "",
            "acceptable_risk_types": "", "evidence": "Theme only.",
            "review_status": "ai_initial",
        })
        writer.writerow({
            "sample_id": "EXT002", "pair_id": "save_01",
            "potential_risk": "true", "risk_type": "sensitive_data",
            "acceptable_risk_types": "sensitive_data;financial_transaction",
            "evidence": "Stores card details.", "review_status": "ai_initial",
        })
    destination = tmp_path / "review"

    built = build_review_package(manifest, gold, image_root, destination)

    assert built == 2
    page = (destination / "review.html").read_text(encoding="utf-8")
    assert page.count('class="pair"') == 1
    assert "EXT001" in page and "EXT002" in page
    assert "Click Save." in page and "Theme only." in page
    assert 'value="sensitive_data" checked' in page
    assert 'value="financial_transaction" checked' in page
    assert "导出复核 CSV" in page
    assert "c3_external_pilot_reviewed.csv" in page
    assert "human_reviewed" in page
    assert "webguard_label" not in page.lower()
    assert (destination / "images" / "EXT001.png").read_bytes() == b"safe"
    assert (destination / "images" / "EXT002.png").read_bytes() == b"risk"
    seeded = list(csv.DictReader(
        (destination / "review_seed.csv").open(encoding="utf-8-sig", newline="")
    ))
    assert seeded[1]["acceptable_risk_types"] == (
        "sensitive_data;financial_transaction"
    )


def test_build_review_package_rejects_unpaired_samples(tmp_path: Path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    (image_root / "only.png").write_bytes(b"image")
    manifest = tmp_path / "samples.json"
    manifest.write_text(json.dumps([{
        "sample_id": "EXT001", "pair_id": "only", "site": "demo",
        "semantic_location": "page", "action_label": "Continue",
        "before_image": "only.png",
    }]), encoding="utf-8")
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "sample_id,pair_id,potential_risk,risk_type,acceptable_risk_types,evidence,review_status\n"
        "EXT001,only,false,,,,ai_initial\n",
        encoding="utf-8",
    )

    try:
        build_review_package(manifest, gold, image_root, tmp_path / "review")
    except ValueError as exc:
        assert "exactly two" in str(exc)
    else:
        raise AssertionError("Expected an invalid pair to be rejected")
