import json
from pathlib import Path

import pytest

from scripts.paper.run_c3_ablation import (
    CONDITIONS,
    build_messages,
    parse_prediction,
    run_one_sample,
)
from ai_web_explorer.grounded_web.risk_detection import RISK_ASSESSMENT_SYSTEM_PROMPT


TAXONOMY = {
    "schema_version": "risk-taxonomy-v1",
    "categories": [
        {
            "risk_type": "financial_transaction",
            "description": "Entering or advancing a paid workflow.",
            "positive_examples": ["Proceed to checkout."],
            "non_examples": ["Browse prices."],
        }
    ],
}


@pytest.mark.parametrize(
    ("condition", "has_image", "has_taxonomy"),
    [
        ("action_only", False, False),
        ("action_taxonomy", False, True),
        ("action_visual", True, False),
        ("full", True, True),
    ],
)
def test_build_messages_isolates_ablation_inputs(
    tmp_path: Path, condition: str, has_image: bool, has_taxonomy: bool
):
    image = tmp_path / "before.png"
    image.write_bytes(b"image")

    messages = build_messages("Proceed to checkout", image, TAXONOMY, condition)
    serialized = json.dumps(messages)

    assert ("image_url" in serialized) is has_image
    assert ("Entering or advancing a paid workflow." in serialized) is has_taxonomy
    assert "Proceed to checkout" in serialized
    assert "financial_transaction" in serialized


def test_full_condition_reuses_deployed_system_prompt_exactly(tmp_path: Path):
    image = tmp_path / "before.png"
    image.write_bytes(b"image")

    messages = build_messages("Proceed to checkout", image, TAXONOMY, "full")

    assert messages[0]["content"] == RISK_ASSESSMENT_SYSTEM_PROMPT


def test_nonvisual_condition_does_not_claim_visual_context(tmp_path: Path):
    image = tmp_path / "before.png"
    image.write_bytes(b"image")

    messages = build_messages("Proceed to checkout", image, TAXONOMY, "action_taxonomy")

    assert "visual context" not in messages[0]["content"]


def test_parse_prediction_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown risk_type"):
        parse_prediction(
            '{"potential_risk":true,"risk_type":"other","evidence":"x"}',
            {"financial_transaction"},
        )


def test_run_one_sample_preserves_success_artifacts(tmp_path: Path):
    image = tmp_path / "before.png"
    image.write_bytes(b"image")

    def complete(**kwargs):
        return {
            "content": '{"potential_risk":true,"risk_type":"financial_transaction","evidence":"Checkout is visible."}',
            "model": "gpt-4o-verified",
            "response_id": "resp-1",
        }

    status = run_one_sample(
        sample={"sample_id": "S001", "action_label": "Proceed to checkout"},
        condition="full",
        screenshot_path=image,
        taxonomy=TAXONOMY,
        output_root=tmp_path / "out",
        model="gpt-4o",
        complete=complete,
    )

    attempt = tmp_path / "out" / "full" / "S001" / "attempt_01"
    assert status["status"] == "valid"
    assert json.loads((attempt / "prediction.json").read_text())["potential_risk"] is True
    assert json.loads((attempt / "status.json").read_text())["model"] == "gpt-4o-verified"


def test_run_one_sample_preserves_failure_directory(tmp_path: Path):
    image = tmp_path / "before.png"
    image.write_bytes(b"image")

    def fail(**kwargs):
        raise RuntimeError("provider unavailable")

    status = run_one_sample(
        sample={"sample_id": "S001", "action_label": "Proceed to checkout"},
        condition="action_only",
        screenshot_path=image,
        taxonomy=TAXONOMY,
        output_root=tmp_path / "out",
        model="gpt-4o",
        complete=fail,
    )

    attempt = tmp_path / "out" / "action_only" / "S001" / "attempt_01"
    assert status["status"] == "failed"
    assert json.loads((attempt / "status.json").read_text())["error_type"] == "RuntimeError"
    assert not (attempt / "prediction.json").exists()
    assert set(CONDITIONS) == {"action_only", "action_taxonomy", "action_visual", "full"}
