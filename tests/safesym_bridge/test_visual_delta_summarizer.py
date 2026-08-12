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
        assert '"semantic_evidence"' in prompt
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


def test_visual_delta_extracts_location_role_and_completion_fact():
    request = VisualDeltaRequest(
        goal="Sort the products.",
        action=BrowserAction("click", "button.sort", "sort_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":[],"candidate_removed_facts":[],'
            '"visual_change_kind":"presentation",'
            '"action_role":"presentation_capability",'
            '"source_location":"shopping","target_location":"shopping",'
            '"completion_facts":["products_sorted"],'
            '"candidate_required_facts":[],"preserved_facts":[],'
            '"semantic_evidence":["The visible product order changed."],'
            '"semantic_confidence":0.92}'
        )

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is not None
    assert result.semantic_observation.source_location == "shopping"
    assert result.semantic_observation.target_location == "shopping"
    assert result.semantic_observation.completion_facts == ["products_sorted"]


def test_confirmed_anchor_allows_navigation_to_new_active_surface():
    request = VisualDeltaRequest(
        goal="Open checkout.",
        action=BrowserAction("click", "button.checkout", "open_checkout"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="shopping",
        source_location_hint_confirmed=True,
        allowed_location_ids=["shopping", "checkout"],
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"action_role":"navigation","source_location":"shopping",'
            '"target_location":"checkout"}'
        )

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is not None
    assert result.semantic_observation.source_location == "shopping"
    assert result.semantic_observation.target_location == "checkout"


def test_visual_delta_rejects_completion_fact_for_non_presentation_role():
    request = VisualDeltaRequest(
        goal="Open checkout.",
        action=BrowserAction("click", "button.checkout", "open_checkout"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"candidate_added_facts":[],"candidate_removed_facts":[],'
            '"action_role":"navigation","source_location":"shopping",'
            '"target_location":"checkout","completion_facts":["products_sorted"]}'
        )

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is not None
    assert result.semantic_observation.completion_facts == []


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
    assert "ordering" in prompt
    assert "filtering" in prompt
    assert "pagination" in prompt
    assert "Both lists may be empty" in prompt
    assert "supporting_facts" not in prompt
    assert "business_relevance" not in prompt
    assert "meaningful_change" not in prompt
    assert '"candidate_added_facts"' in prompt
    assert '"candidate_removed_facts"' in prompt


def test_visual_delta_prompt_declares_role_contract_and_location_anchor():
    request = VisualDeltaRequest(
        goal="Filter products.",
        action=BrowserAction("click", "button.filter", "filter_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="shopping",
        allowed_location_ids=["shopping", "checkout"],
        current_location_context="Product listing surface",
    )
    prompts = []

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        prompts.append(prompt)
        return '{"action_role":"presentation_capability","source_location":"shopping","target_location":"shopping"}'

    result = summarize_visual_delta(request, provider=provider)
    prompt = prompts[0]
    for role in (
        "presentation_capability",
        "state_mutation",
        "navigation",
        "guarded_navigation",
        "form_completion",
        "commit",
        "unknown",
    ):
        assert role in prompt
    assert "source_location_hint" in prompt
    assert "shopping" in prompt
    assert "allowed_location_ids" in prompt
    assert result.semantic_observation is not None
    assert result.semantic_observation.source_location == "shopping"
    assert result.semantic_observation.target_location == "shopping"


def test_visual_delta_rejects_invalid_role_and_location_drift():
    request = VisualDeltaRequest(
        goal="Filter products.",
        action=BrowserAction("click", "button.filter", "filter_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="shopping",
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return '{"action_role":"filtering","source_location":"filters_panel","target_location":"search_results"}'

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is None


def test_visual_delta_rejects_presentation_drift_from_first_entry_anchor():
    request = VisualDeltaRequest(
        goal="Filter products.",
        action=BrowserAction("click", "button.filter", "filter_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="product_list",
        source_location_hint_confirmed=True,
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"action_role":"presentation_capability",'
            '"source_location":"filters_panel","target_location":"search_results"}'
        )

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is None


def test_visual_delta_rejects_all_semantics_when_location_anchor_is_unresolved():
    request = VisualDeltaRequest(
        goal="Sort products.",
        action=BrowserAction("click", "button.sort", "sort_products"),
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        source_location_hint="product_list",
        source_location_hint_confirmed=False,
        source_location_anchor_unresolved=True,
    )

    def provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"action_role":"presentation_capability",'
            '"source_location":"product_list","target_location":"product_list"}'
        )

    result = summarize_visual_delta(request, provider=provider)
    assert result.semantic_observation is None


def test_first_entry_sibling_presentations_share_one_anchor_fail_closed():
    responses = [
        '{"action_role":"presentation_capability","source_location":"filters_panel","target_location":"search_results"}',
        '{"action_role":"presentation_capability","source_location":"sort_panel","target_location":"products"}',
    ]
    results = []
    for response in responses:
        request = VisualDeltaRequest(
            goal="Explore listing controls.",
            action=BrowserAction("click", None, "presentation_action"),
            before_screenshot_path="before.png",
            after_screenshot_path="after.png",
            source_location_hint="product_list",
            source_location_hint_confirmed=True,
        )

        def provider(prompt, *, before_screenshot_path, after_screenshot_path):
            return response

        results.append(summarize_visual_delta(request, provider=provider))

    assert [result.semantic_observation for result in results] == [None, None]


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

    assert not hasattr(result, "business_transition")


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

    assert not hasattr(result, "business_transition")


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
    assert not hasattr(result, "business_transition")


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
