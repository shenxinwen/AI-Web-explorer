from __future__ import annotations

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_naming import (
    SemanticNamingRequest,
    apply_transition_naming,
    prompt_for_semantic_naming,
    apply_semantic_naming,
    normalize_semantic_naming_response,
)


def test_normalize_semantic_naming_response_keeps_human_names_separate_from_ids():
    result = normalize_semantic_naming_response(
        {
            "node_label": "Checkout Overview",
            "state_summary": "User is reviewing the order before final purchase.",
            "action_label": "Continue to review",
            "canonical_action_name": "Continue To Review",
            "confidence": 0.8,
        }
    )

    assert result.node_label == "checkout_overview"
    assert result.state_summary == "User is reviewing the order before final purchase."
    assert result.action_label == "Continue to review"
    assert result.canonical_action_name == "continue_to_review"
    assert result.naming_provenance == {
        "source": "llm_semantic_naming",
        "confidence": 0.8,
    }


def test_apply_semantic_naming_updates_readable_fields_without_changing_runtime_id():
    request = SemanticNamingRequest(
        goal="Reach checkout overview.",
        state=StateSnapshot(
            page_id="inventory",
            url="https://example.test/inventory",
            title="Inventory",
            signature={"cart_count": 0},
        ),
        action=BrowserAction(
            action_kind="click",
            locator="#add-to-cart",
            semantic_id="stagehand_003_click_add_to_cart",
            description="click Add to cart",
        ),
    )

    node_fields, renamed_action = apply_semantic_naming(
        request,
        provider=lambda _request: {
            "node_label": "Product List",
            "state_summary": "Product catalog with empty cart.",
            "action_label": "Add item to cart",
            "canonical_action_name": "product_add_to_cart",
        },
    )

    assert node_fields["node_label"] == "product_list"
    assert node_fields["state_summary"] == "Product catalog with empty cart."
    assert renamed_action is not None
    assert renamed_action.semantic_id == "stagehand_003_click_add_to_cart"
    assert renamed_action.locator == "#add-to-cart"
    assert renamed_action.action_label == "Add item to cart"
    assert renamed_action.canonical_action_name == "product_add_to_cart"


def test_prompt_for_transition_naming_uses_minimal_generic_evidence():
    request = SemanticNamingRequest(
        goal="Complete a task on the website.",
        state=StateSnapshot(
            page_id="before",
            url="https://example.test/before",
            title="Before",
            signature={"internal": "ignored"},
        ),
        action=BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="stagehand_business_milestone_001",
            description="Advance one business milestone.",
        ),
        visual_change_summary="The page changed from a sign-in form to an account dashboard.",
        naming_task="transition",
    )

    prompt = prompt_for_semantic_naming(request)

    assert "The page changed from a sign-in form to an account dashboard." in prompt
    assert "lower_snake_case" in prompt
    assert "business-level transition" in prompt
    assert "add_product_to_cart" not in prompt
    assert "internal" not in prompt


def test_apply_transition_naming_updates_action_without_changing_runtime_id():
    action = BrowserAction(
        action_kind="business_intent",
        locator=None,
        semantic_id="stagehand_business_milestone_001",
        description="Advance one business milestone.",
        canonical_action_name="advance_business_milestone",
    )

    renamed = apply_transition_naming(
        action=action,
        goal="Complete a task on the website.",
        visual_change_summary=(
            "The page changed from a sign-in form to an account dashboard."
        ),
        provider=lambda _request: {
            "action_label": "Log in",
            "canonical_action_name": "log_in",
            "confidence": 0.9,
        },
    )

    assert renamed.semantic_id == "stagehand_business_milestone_001"
    assert renamed.action_kind == "business_intent"
    assert renamed.action_label == "Log in"
    assert renamed.canonical_action_name == "log_in"
    assert renamed.naming_provenance == {
        "source": "llm_transition_naming",
        "confidence": 0.9,
    }
