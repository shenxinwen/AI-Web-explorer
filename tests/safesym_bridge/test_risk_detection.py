import json

import pytest

from ai_web_explorer.grounded_web.risk_detection import (
    DEFAULT_RISK_TAXONOMY_PATH,
    RISK_ASSESSMENT_SYSTEM_PROMPT,
    RiskAssessment,
    RiskDetectionRequest,
    RiskTaxonomy,
    load_risk_taxonomy,
    render_risk_assessment_user_prompt,
    summarize_risk_assessments,
)


EXPECTED_RISK_TYPES = {
    "destructive_change",
    "financial_transaction",
    "external_communication",
    "account_and_permission",
    "sensitive_data",
}


def test_default_taxonomy_loads_the_five_versioned_risk_types():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    assert taxonomy.schema_version == "risk-taxonomy-v1"
    assert set(taxonomy.categories) == EXPECTED_RISK_TYPES
    assert all(category.description for category in taxonomy.categories.values())
    assert all(category.positive_examples for category in taxonomy.categories.values())
    assert all(category.non_examples for category in taxonomy.categories.values())


def test_financial_taxonomy_treats_entering_checkout_as_potential_risk():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)
    category = taxonomy.categories["financial_transaction"]

    assert any("checkout" in example.lower() for example in category.positive_examples)
    assert not any("checkout" in example.lower() for example in category.non_examples)


def test_prompt_encodes_conservative_binary_policy_without_site_hardcoding():
    prompt = RISK_ASSESSMENT_SYSTEM_PROMPT
    normalized_prompt = " ".join(prompt.split())

    assert "enter or prepare" in normalized_prompt
    assert "prefer marking the action as risky" in normalized_prompt
    assert "potential_risk" in prompt
    assert "one concise sentence" in normalized_prompt
    assert "amazon" not in prompt.lower()
    assert "Examples:" not in prompt


def test_user_prompt_contains_only_label_and_serialized_taxonomy():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    prompt = render_risk_assessment_user_prompt("Continue to checkout", taxonomy)

    assert "Continue to checkout" in prompt
    assert '"financial_transaction"' in prompt
    assert "screenshot_path" not in prompt


def test_taxonomy_rejects_a_category_without_non_examples(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "risk-taxonomy-v1",
                "categories": [
                    {
                        "risk_type": "destructive_change",
                        "description": "Permanent data changes.",
                        "positive_examples": ["Delete an account."],
                        "non_examples": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non_examples"):
        load_risk_taxonomy(path)


def test_detection_request_contains_only_screenshot_label_and_taxonomy():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    request = RiskDetectionRequest(
        screenshot_path="before.png",
        candidate_label="Permanently delete the current account.",
        taxonomy=taxonomy,
    )

    assert request.to_dict() == {
        "screenshot_path": "before.png",
        "candidate_label": "Permanently delete the current account.",
        "taxonomy": taxonomy.to_dict(),
    }


def test_risk_assessment_requires_a_definite_supported_judgment():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    assessment = RiskAssessment.from_dict(
        {
            "potential_risk": True,
            "risk_type": "destructive_change",
            "evidence": "The page warns that deletion cannot be undone.",
        },
        taxonomy=taxonomy,
    )

    assert assessment.to_dict() == {
        "potential_risk": True,
        "risk_type": "destructive_change",
        "evidence": "The page warns that deletion cannot be undone.",
    }


def test_risk_assessment_rejects_a_non_boolean_judgment():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)
    payload = {
        "potential_risk": "unknown",
        "risk_type": "destructive_change",
        "evidence": "Visible irreversible deletion warning.",
    }

    with pytest.raises(ValueError, match="potential_risk"):
        RiskAssessment.from_dict(payload, taxonomy=taxonomy)


def test_no_risk_is_a_definite_assessment_without_a_risk_type():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    assessment = RiskAssessment.from_dict(
        {
            "potential_risk": False,
            "risk_type": None,
            "evidence": "The action only changes the local product sorting order.",
        },
        taxonomy=taxonomy,
    )

    assert assessment.potential_risk is False
    assert assessment.risk_type is None


def test_no_risk_rejects_a_risk_type():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    with pytest.raises(ValueError, match="risk_type must be null"):
        RiskAssessment.from_dict(
            {
                "potential_risk": False,
                "risk_type": "destructive_change",
                "evidence": "No consequential side effect is visible.",
            },
            taxonomy=taxonomy,
        )


def test_summary_counts_binary_judgments_and_detected_risk_types():
    assessments = [
        RiskAssessment(True, "destructive_change", "Deletion warning."),
        RiskAssessment(True, "sensitive_data", "Password fields."),
        RiskAssessment(False, None, "Local sorting only."),
    ]

    assert summarize_risk_assessments(assessments) == {
        "total_assessments": 3,
        "risks_detected": 2,
        "risk_type_counts": {
            "destructive_change": 1,
            "sensitive_data": 1,
        },
    }


def test_taxonomy_round_trips_without_adding_runtime_state():
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)

    restored = RiskTaxonomy.from_dict(taxonomy.to_dict())

    assert restored == taxonomy
