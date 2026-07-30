from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.visual_delta import (
    VisualDeltaRequest,
    summarize_visual_delta,
)


def test_summarize_visual_delta_maps_provider_json_to_candidate_planning_delta():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction(
            action_kind="click",
            locator="button.add",
            semantic_id="add_to_cart",
            description="Add to cart",
        ),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        before_signature={"cart_count": 0},
        after_signature={"cart_count": 1},
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        assert "Add one item to the cart." in prompt
        assert before_screenshot_path == "before.png"
        assert after_screenshot_path == "after.png"
        return (
            '{"visible_change_summary":"Cart count changed from 0 to 1.",'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"evidence":["cart badge shows one item"],'
            '"confidence":0.86}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.planning_delta.candidate_added_facts == ["cart_has_items"]
    assert result.planning_delta.verified_added_facts == []
    assert result.trace.status == "summarized"
    assert result.trace.visual_change_summary == "Cart count changed from 0 to 1."
    assert result.trace.llm_response["visible_change_summary"] == (
        "Cart count changed from 0 to 1."
    )


def test_summarize_visual_delta_maps_business_transition_fields():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction(
            action_kind="click",
            locator="button.add",
            semantic_id="add_to_cart",
            description="Add to cart",
        ),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        assert "business_action_name" in prompt
        assert "business_relevance" in prompt
        assert "meaningful_change" in prompt
        return (
            '{"visible_change_summary":"Bluetooth Headphones were added to cart.",'
            '"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"evidence":["cart badge changed from 0 to 1"],'
            '"confidence":0.9}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.business_transition is not None
    assert result.business_transition.action_name == "add_item_to_cart"
    assert result.business_transition.relevance == "core"
    assert result.business_transition.meaningful_change is True
    assert result.business_transition.judge_source == "vlm"
    assert result.business_transition.summary == (
        "Bluetooth Headphones were added to cart."
    )
    assert result.business_transition.evidence == ["cart badge changed from 0 to 1"]
    assert result.business_transition.confidence == 0.9


def test_summarize_visual_delta_records_generated_facts_without_failing():
    request = VisualDeltaRequest(
        goal="Open product details.",
        action=BrowserAction("business_intent", None, "view_product_details"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"visible_change_summary":"A product detail modal opened.",'
            '"business_action_name":"view_product_details",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["product_details_visible"],'
            '"candidate_removed_facts":[],'
            '"evidence":["product detail modal is visible"],'
            '"confidence":0.8}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.trace.error_type is None
    assert result.planning_delta.candidate_added_facts == ["product_details_visible"]
    assert result.planning_delta.profile_fact_ids == []
    assert result.planning_delta.generated_fact_ids == ["product_details_visible"]
    assert result.business_transition is not None
    assert result.business_transition.action_name == "view_product_details"
    assert result.business_transition.relevance == "core"
    assert result.business_transition.meaningful_change is True


def test_summarize_visual_delta_splits_profile_and_generated_facts():
    request = VisualDeltaRequest(
        goal="Open product details.",
        action=BrowserAction("business_intent", None, "view_product_details"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"visible_change_summary":"Product details show an add-to-cart button.",'
            '"candidate_added_facts":["cart_has_items","product_details_visible"],'
            '"candidate_removed_facts":["modal_absent"],'
            '"evidence":["product detail modal is visible"],'
            '"confidence":0.8}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.planning_delta.candidate_added_facts == [
        "cart_has_items",
        "product_details_visible",
    ]
    assert result.planning_delta.candidate_removed_facts == ["modal_absent"]
    assert result.planning_delta.profile_fact_ids == ["cart_has_items"]
    assert result.planning_delta.generated_fact_ids == [
        "product_details_visible",
        "modal_absent",
    ]


def test_summarize_visual_delta_requires_visible_change_summary():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("click", "button.add", "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"evidence":["cart badge changed"],'
            '"confidence":0.6}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "missing_visual_change_summary"
    assert result.planning_delta.candidate_added_facts == []


def test_summarize_visual_delta_accepts_object_summary_and_fact_objects():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("click", "button.add", "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"visible_change_summary":{'
            '"before":{"cart_count":0},'
            '"after":{"cart_count":1}},'
            '"candidate_added_facts":[{"fact_id":"cart_has_items"}],'
            '"candidate_removed_facts":[],'
            '"evidence":[{"description":"cart badge changed from 0 to 1"}],'
            '"confidence":"high"}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.trace.visual_change_summary == (
        '{"after": {"cart_count": 1}, "before": {"cart_count": 0}}'
    )
    assert result.planning_delta.candidate_added_facts == ["cart_has_items"]
    assert result.planning_delta.candidate_removed_facts == []
    assert result.planning_delta.evidence == ["cart badge changed from 0 to 1"]


def test_summarize_visual_delta_captures_provider_errors_without_raising():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("click", "button.add", "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        raise RuntimeError("network unavailable")

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "provider_error"
    assert result.trace.error_message == "network unavailable"
    assert result.planning_delta.candidate_added_facts == []
