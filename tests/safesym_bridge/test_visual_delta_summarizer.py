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
        before_signature={"cart_has_items": False, "cart_count": 0},
        after_signature={"cart_has_items": True, "cart_count": 1},
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        assert "Add one item to the cart." not in prompt
        assert "cart_has_items" not in prompt
        assert "cart_count" not in prompt
        assert '"profile"' not in prompt
        assert "visible_change_summary" not in prompt
        assert "evidence" not in prompt
        assert before_screenshot_path == "before.png"
        assert after_screenshot_path == "after.png"
        return (
            '{"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"confidence":0.86}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.planning_delta.candidate_added_facts == ["cart_has_items"]
    assert result.planning_delta.verified_added_facts == []
    assert result.trace.status == "summarized"
    assert "visual_change_summary" not in result.trace.to_dict()


def test_visual_delta_prompt_describes_set_difference_and_allows_empty_sets():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("business_intent", None, "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )
    prompts = []

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        prompts.append(prompt)
        return '{"candidate_added_facts":[],"candidate_removed_facts":[]}'

    summarize_visual_delta(request, provider=provider)

    prompt = prompts[0]
    assert "visible after the action and not before" in prompt
    assert "visible before the action and not after" in prompt
    assert "unchanged" in prompt
    assert "Both lists may be empty" in prompt
    assert "supporting_facts" not in prompt
    assert "business_relevance" not in prompt
    assert "meaningful_change" not in prompt
    assert '"candidate_added_facts"' in prompt
    assert '"candidate_removed_facts"' in prompt


def test_visual_delta_prompt_defines_bounded_change_kinds_without_profile_authority():
    request = VisualDeltaRequest(
        goal="Observe the page.",
        action=BrowserAction("business_intent", None, "observe"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )
    prompts = []

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        prompts.append(prompt)
        return '{"candidate_added_facts":[],"candidate_removed_facts":[],"visual_change_kind":"presentation"}'

    result = summarize_visual_delta(request, provider=provider)

    assert result.visual_change_kind == "presentation"
    prompt = prompts[0]
    assert "presentation" in prompt
    assert "state_indicator" in prompt
    assert "surface" in prompt
    assert "mixed" in prompt
    assert "unknown" in prompt
    assert "cart_has_items" not in prompt
    assert "planning_facts" not in prompt


def test_visual_delta_uses_unknown_for_invalid_change_kind_and_failed_observation():
    request = VisualDeltaRequest(
        goal="Observe the page.",
        action=BrowserAction("business_intent", None, "observe"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def invalid_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return '{"candidate_added_facts":[],"candidate_removed_facts":[],"visual_change_kind":"unsupported"}'

    invalid = summarize_visual_delta(request, provider=invalid_provider)
    assert invalid.visual_change_kind == "unknown"

    def failing_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        raise RuntimeError("unavailable")

    failed = summarize_visual_delta(request, provider=failing_provider)
    assert failed.visual_change_kind == "unknown"


def test_summarize_visual_delta_does_not_generate_business_transition_fields():
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
        assert "business_action_name" not in prompt
        assert "business_relevance" not in prompt
        assert "meaningful_change" not in prompt
        return (
            '{"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"confidence":0.9}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.business_transition is None


def test_summarize_visual_delta_normalizes_explanatory_business_relevance():
    request = VisualDeltaRequest(
        goal="Open product details.",
        action=BrowserAction("business_intent", None, "view_product_details"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        assert "business_relevance_enum" not in prompt
        return (
            '{"business_action_name":"view_product_details",'
            '"business_relevance":"This is a key product selection step.",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["product_details_visible"],'
            '"candidate_removed_facts":[],'
            '"confidence":0.8}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.business_transition is None


def test_summarize_visual_delta_records_vlm_fact_as_generated_until_verified():
    request = VisualDeltaRequest(
        goal="Open product details.",
        action=BrowserAction("business_intent", None, "view_product_details"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"business_action_name":"view_product_details",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["product_details_visible"],'
            '"candidate_removed_facts":[],'
            '"confidence":0.8}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.trace.error_type is None
    assert result.planning_delta.candidate_added_facts == ["product_details_visible"]
    assert result.planning_delta.profile_fact_ids == []
    assert result.planning_delta.generated_fact_ids == []
    assert result.business_transition is None


def test_summarize_visual_delta_keeps_all_vlm_facts_generated():
    request = VisualDeltaRequest(
        goal="Open product details.",
        action=BrowserAction("business_intent", None, "view_product_details"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":["cart_has_items","product_details_visible"],'
            '"candidate_removed_facts":["modal_absent"],'
            '"confidence":0.8}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.planning_delta.candidate_added_facts == [
        "cart_has_items",
        "product_details_visible",
    ]
    assert result.planning_delta.candidate_removed_facts == ["modal_absent"]
    assert result.planning_delta.profile_fact_ids == []
    assert result.planning_delta.generated_fact_ids == []


def test_summarize_visual_delta_drops_facts_reported_in_both_sets():
    request = VisualDeltaRequest(
        goal="Observe the page.",
        action=BrowserAction("business_intent", None, "observe"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":["cart_has_items","same_fact"],'
            '"candidate_removed_facts":["same_fact"]}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.planning_delta.candidate_added_facts == ["cart_has_items"]
    assert result.planning_delta.candidate_removed_facts == []


def test_summarize_visual_delta_accepts_fact_only_response():
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
            '"confidence":0.6}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.planning_delta.candidate_added_facts == ["cart_has_items"]


def test_summarize_visual_delta_ignores_non_string_fact_objects():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("click", "button.add", "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":[{"fact_id":"cart_has_items"}],'
            '"candidate_removed_facts":[{"fact":"cart_empty"}],'
            '"confidence":"high"}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.planning_delta.candidate_added_facts == []
    assert result.planning_delta.candidate_removed_facts == []
    assert result.planning_delta.evidence == []


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
