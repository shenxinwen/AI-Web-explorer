import json

from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile


def test_summarize_visual_affordances_maps_provider_json():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        profile=ecommerce_checkout_profile(),
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
        current_planning_facts=["product_list_visible"],
    )

    def provider(prompt, *, current_screenshot_path):
        assert "representative business actions" in prompt
        assert current_screenshot_path == "current.png"
        return (
            '{"page_mode":"multi_region","regions":['
            '{"region_id":"region_1","purpose":"Manage visible items",'
            '"actions":['
            '{"intent":"add_item_to_cart",'
            '"label":"Add to cart",'
            '"target":"button labeled Add to cart on a visible item",'
            '"expected_effect":"The selected item is added."},'
            '{"intent":"open_cart",'
            '"label":"Cart",'
            '"target":"cart link",'
            '"expected_effect":"The cart surface opens."}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.state_summary is None
    assert [item.action_name for item in result.business_affordances] == [
        "add_item_to_cart",
        "open_cart",
    ]
    assert result.business_affordances[0].relevance_hint == "unknown"
    assert result.business_affordances[0].target_hint == (
        "button labeled Add to cart on a visible item"
    )
    assert result.business_affordances[0].expected_change == (
        "The selected item is added."
    )
    assert result.business_affordances[0].evidence is None


def test_visual_affordance_prompt_keeps_vlm_stateless_about_graph_and_profile():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        profile=ecommerce_checkout_profile(),
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
        current_planning_facts=["product_list_visible"],
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        assert "functional regions" in prompt
        assert "representative business actions" in prompt
        assert "expected_effect" in prompt
        assert "profile" not in payload
        assert "current_planning_facts" not in payload
        assert request.goal not in prompt
        assert "profile" not in prompt.lower()
        assert "pddl" not in prompt.lower()
        assert "graph" not in prompt.lower()
        assert "web-kobe" not in prompt.lower()
        assert "relevance_hint" not in prompt
        assert "confidence" not in prompt
        assert "checkout" not in prompt.lower()
        assert "cart_has_items" not in prompt
        return '{"page_mode":"uncertain","regions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"


def test_visual_affordance_prompt_treats_max_actions_as_upper_bound():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        profile=ecommerce_checkout_profile(),
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
        current_planning_facts=["product_details_visible"],
        max_actions=5,
    )

    def provider(prompt, *, current_screenshot_path):
        assert "upper bound, not a quota" in prompt
        assert "Return fewer actions when fewer are actually available" in prompt
        assert "multi_region" in prompt
        assert "single_surface" in prompt
        assert "Do not infer actions from common website patterns" in prompt
        assert "profile" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        return (
            '{"page_mode":"single_surface","regions":['
            '{"region_id":"region_1","purpose":"Focused object actions",'
            '"actions":['
            '{"intent":"add_to_cart","target":"Add to cart",'
            '"expected_effect":"The item is added."},'
            '{"intent":"close_product_details","target":"Close",'
            '"expected_effect":"The focused surface closes."}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert [item.action_name for item in result.business_affordances] == [
        "add_to_cart",
        "close_product_details",
    ]


def test_summarize_visual_affordances_enforces_max_actions_upper_bound():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        profile=ecommerce_checkout_profile(),
        current_screenshot_path="current.png",
        max_actions=2,
    )

    def provider(prompt, *, current_screenshot_path):
        return (
            '{"page_mode":"multi_region","regions":['
            '{"region_id":"region_1","purpose":"First region",'
            '"actions":['
            '{"intent":"first_action","target":"First",'
            '"expected_effect":"First effect"},'
            '{"intent":"second_action","target":"Second",'
            '"expected_effect":"Second effect"},'
            '{"intent":"third_action","target":"Third",'
            '"expected_effect":"Third effect"}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert [item.action_name for item in result.business_affordances] == [
        "first_action",
        "second_action",
    ]


def test_summarize_visual_affordances_rejects_non_object_response():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        profile=ecommerce_checkout_profile(),
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return '["add_item_to_cart"]'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "parse_error"
    assert result.business_affordances == []
