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
    assert result.business_affordances[0].evidence == (
        "The page shows product cards with Add to cart buttons."
    )


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
