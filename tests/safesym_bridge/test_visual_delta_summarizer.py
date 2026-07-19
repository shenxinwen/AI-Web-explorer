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
            '"candidate_added_facts":["cart_nonempty"],'
            '"candidate_removed_facts":["cart_empty"],'
            '"evidence":["cart badge shows one item"],'
            '"confidence":0.86}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.planning_delta.candidate_added_facts == ["cart_nonempty"]
    assert result.planning_delta.verified_added_facts == []
    assert result.trace.status == "summarized"
    assert result.trace.llm_response["visible_change_summary"] == (
        "Cart count changed from 0 to 1."
    )


def test_summarize_visual_delta_rejects_unknown_profile_facts():
    request = VisualDeltaRequest(
        goal="Add one item to the cart.",
        action=BrowserAction("click", "button.add", "add_to_cart"),
        profile=ecommerce_checkout_profile(),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":["made_up_fact"],'
            '"candidate_removed_facts":["cart_empty"],'
            '"evidence":["cart badge changed"],'
            '"confidence":0.6}'
        )

    result = summarize_visual_delta(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "unknown_fact"
    assert result.planning_delta.candidate_added_facts == []
