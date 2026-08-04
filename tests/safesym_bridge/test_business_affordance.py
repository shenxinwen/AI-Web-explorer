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
        assert "next-step business actions" in prompt
        assert current_screenshot_path == "current.png"
        return (
            '{"business_affordances":['
            '{"action_name":"add_item_to_cart",'
                '"relevance_hint":"core",'
                '"target_hint":"button labeled Add to cart on a product card",'
                '"expected_change":"Cart item count increases.",'
                '"evidence":"The page shows product cards with Add to cart buttons.",'
                '"confidence":0.9},'
            '{"action_name":"open_cart",'
            '"relevance_hint":"core",'
            '"target_hint":"shopping cart link",'
            '"evidence":"A cart icon is visible in the header.",'
            '"confidence":0.8}'
            "],"
            '"state_summary":"Product listing page with cart controls."}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.state_summary == "Product listing page with cart controls."
    assert [item.action_name for item in result.business_affordances] == [
        "add_item_to_cart",
        "open_cart",
    ]
    assert result.business_affordances[0].relevance_hint == "core"
    assert result.business_affordances[0].target_hint == (
        "button labeled Add to cart on a product card"
    )
    assert result.business_affordances[0].expected_change == (
        "Cart item count increases."
    )
    assert result.business_affordances[0].evidence == (
        "The page shows product cards with Add to cart buttons."
    )


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
        assert "visible page evidence" in prompt
        assert "expected_change" in prompt
        assert "profile" not in payload
        assert "current_planning_facts" not in payload
        assert "planning_facts" not in prompt
        assert "profile facts" not in prompt.lower()
        assert "already tried" not in prompt.lower()
        assert "already_done" not in prompt
        assert "should_create_node" not in prompt
        assert "create new node" not in prompt.lower()
        assert "new business-state node" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        assert "cart_has_items" not in prompt
        return '{"business_affordances":[],"state_summary":"Product list."}'

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
        assert "current active business surface" in prompt
        assert "focused surface" in prompt
        assert "selected object" in prompt
        assert "Do not infer actions from common website patterns" in prompt
        assert "profile facts" not in prompt.lower()
        assert "product details" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        return (
            '{"business_affordances":['
            '{"action_name":"add_to_cart","relevance_hint":"core"},'
            '{"action_name":"close_product_details","relevance_hint":"supporting"}'
            "],"
            '"state_summary":"Product details modal."}'
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
            '{"business_affordances":['
            '{"action_name":"first_action","relevance_hint":"core"},'
            '{"action_name":"second_action","relevance_hint":"supporting"},'
            '{"action_name":"third_action","relevance_hint":"supporting"}'
            "],"
            '"state_summary":"Page with too many proposed actions."}'
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
