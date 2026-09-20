import csv
import json
from pathlib import Path

import pytest

from scripts.paper.build_c3_initial_annotations import (
    build_initial_annotations,
    classify_sample,
)


@pytest.mark.parametrize(
    ("action_id", "location", "expected"),
    [
        ("add_to_cart", "shopping_results_page", ("false", "")),
        ("remove_item", "cart_page", ("false", "")),
        ("proceed_to_checkout", "cart_page", ("true", "financial_transaction")),
        ("place_order", "checkout_form", ("true", "financial_transaction")),
        ("enter_password", "login_form", ("true", "sensitive_data")),
        ("complete_billing_information", "checkout_form", ("true", "sensitive_data")),
        ("complete_payment_details", "checkout_form", ("true", "sensitive_data")),
    ],
)
def test_classify_sample_applies_frozen_c3_boundaries(action_id, location, expected):
    label = classify_sample({
        "action_id": action_id,
        "semantic_location": location,
        "action_label": action_id.replace("_", " "),
    })

    assert (label["potential_risk"], label["risk_type"]) == expected
    assert label["evidence"]


def test_build_initial_annotations_writes_every_sample_without_predictions(tmp_path: Path):
    samples = [
        {
            "sample_id": "S001",
            "site": "demo",
            "action_id": "add_to_cart",
            "semantic_location": "shopping_results_page",
            "action_label": "Add one item to the cart.",
        },
        {
            "sample_id": "S002",
            "site": "demo",
            "action_id": "place_order",
            "semantic_location": "checkout_form",
            "action_label": "Place the order.",
        },
    ]
    manifest = tmp_path / "samples.json"
    manifest.write_text(json.dumps(samples), encoding="utf-8")
    destination = tmp_path / "annotations.csv"

    build_initial_annotations(manifest, destination)

    with destination.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["sample_id"] for row in rows] == ["S001", "S002"]
    assert rows[0]["potential_risk"] == "false"
    assert rows[1]["risk_type"] == "financial_transaction"
    assert all("system_prediction" not in row for row in rows)


def test_classify_sample_rejects_unreviewed_action():
    with pytest.raises(ValueError, match="unreviewed C3 action"):
        classify_sample({
            "action_id": "unknown_action",
            "semantic_location": "unknown",
            "action_label": "Do something unknown.",
        })
