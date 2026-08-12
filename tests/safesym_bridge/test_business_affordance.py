import dataclasses
import json
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.exploration_semantics import (
    practice_shopping_feasibility_profile,
)


def test_exploration_and_prompts_do_not_consume_trace_planning_inputs():
    module_sources = []
    for module_name in (
        "ai_web_explorer.grounded_web.explorer",
        "ai_web_explorer.grounded_web.business_affordance",
        "ai_web_explorer.grounded_web.stagehand_prompt",
    ):
        module = __import__(module_name, fromlist=["__file__"])
        module_sources.append(Path(module.__file__).read_text(encoding="utf-8"))

    for source in module_sources:
        assert "trace_pddl" not in source
        assert "goal_checkpoint" not in source
        assert "problem.pddl" not in source


def test_trace_compiler_does_not_consume_non_trace_graph_fields():
    module = __import__(
        "ai_web_explorer.safesym_bridge.trace_pddl",
        fromlist=["__file__"],
    )
    source = Path(module.__file__).read_text(encoding="utf-8")

    for token in (
        "observed_delta",
        "schema_delta",
        "visual_change_kind",
        "planning_delta",
        "planning_transition",
        "node_label",
        "page_frame",
        "business_affordance",
    ):
        assert token not in source


def test_summarize_visual_affordances_maps_provider_json():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
    )

    def provider(prompt, *, current_screenshot_path):
        assert "representative business actions" in prompt
        assert current_screenshot_path == "current.png"
        return (
            '{"state_label":"product_list_sorted",'
            '"page_mode":"multi_region","regions":['
            '{"region_id":"region_1","purpose":"Manage visible items",'
            '"actions":['
            '{"intent":"add_item_to_cart",'
            '"label":"Add to cart",'
            '"target":"button labeled Add to cart on a visible item",'
            '"supporting_facts":["item_control_visible","cart_control_visible"]},'
            '{"intent":"open_cart",'
            '"label":"Cart",'
            '"target":"cart link"}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.state_summary is None
    assert result.state_label == "product_list_sorted"
    assert [item.action_name for item in result.business_affordances] == [
        "add_item_to_cart",
        "open_cart",
    ]
    assert result.business_affordances[0].relevance_hint == "unknown"
    assert result.business_affordances[0].target_hint == (
        "button labeled Add to cart on a visible item"
    )
    assert result.business_affordances[0].supporting_facts == [
        "item_control_visible",
        "cart_control_visible",
    ]


@pytest.mark.parametrize(
    "external_goal",
    ["Reach checkout immediately", "Delete the selected document"],
)
def test_visual_affordance_prompt_prioritizes_breadth_without_external_task_goal(
    external_goal,
):
    request = VisualAffordanceRequest(
        goal=external_goal,
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        instruction = payload["instruction"]
        action_schema = payload["output_schema"]["regions"][0]["actions"][0]

        assert "breadth of functional coverage" in instruction
        assert "one representative action per functional family" in instruction
        assert "new surface, object, dialog, page, or workflow stage" in instruction
        assert "local refinement" in instruction
        assert "concrete visible target" in instruction
        assert action_schema["relevance_hint"] == "core | supporting | low_value"
        assert action_schema["confidence"] == "number from 0.0 to 1.0"

        assert "profile" not in payload
        assert "current_planning_facts" not in payload
        assert request.goal not in prompt
        assert "pddl" not in prompt.lower()
        assert "graph" not in prompt.lower()
        assert "web-kobe" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        assert "cart_has_items" not in prompt
        return '{"page_mode":"uncertain","regions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"


def test_visual_affordance_request_has_no_profile_or_planning_state_fields():
    field_names = {
        field.name for field in dataclasses.fields(VisualAffordanceRequest)
    }
    assert "profile" not in field_names
    assert "current_planning_facts" not in field_names


def test_visual_affordance_prompt_treats_max_actions_as_upper_bound():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
        current_signature={"url_path": "/inventory"},
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
            '"supporting_facts":["item_visible"]},'
            '{"intent":"close_product_details","target":"Close",'
            '"supporting_facts":[]}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert [item.action_name for item in result.business_affordances] == [
        "add_to_cart",
        "close_product_details",
    ]


def test_visual_affordance_prompt_requests_top_level_state_label():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        assert payload["output_schema"]["state_label"] == (
            "short snake_case visible state name"
        )
        return '{"state_label":"product_list_sorted","regions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.state_label == "product_list_sorted"


def test_visual_affordance_ignores_non_string_state_label_without_losing_actions():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return (
            '{"state_label":{"name":"not-a-label"},"regions":['
            '{"actions":[{"intent":"sort_products","target":"Sort"}]}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.state_label is None
    assert [item.action_name for item in result.business_affordances] == [
        "sort_products"
    ]


def test_summarize_visual_affordances_enforces_max_actions_upper_bound():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        current_screenshot_path="current.png",
        max_actions=2,
    )

    def provider(prompt, *, current_screenshot_path):
        return (
            '{"page_mode":"multi_region","regions":['
            '{"region_id":"region_1","purpose":"First region",'
            '"actions":['
            '{"intent":"first_action","target":"First",'
            '"supporting_facts":["first_visible"]},'
            '{"intent":"second_action","target":"Second",'
            '"supporting_facts":["second_visible"]},'
            '{"intent":"third_action","target":"Third",'
            '"supporting_facts":["third_visible"]}'
            ']}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert [item.action_name for item in result.business_affordances] == [
        "first_action",
        "second_action",
    ]


def _targeted_request():
    return VisualAffordanceRequest(
        goal="Explore useful website functionality.",
        current_screenshot_path="after.png",
        max_actions=8,
        scan_kind="targeted",
        semantic_location="shopping",
        existing_action_ids=["open_empty_cart", "add_to_cart"],
        completed_action_ids=["add_to_cart"],
        added_business_facts=["cart_has_items"],
        removed_business_facts=[],
        semantic_profile_context=practice_shopping_feasibility_profile().to_prompt_context(),
    )


def test_targeted_scan_requests_only_business_delta_changes():
    request = _targeted_request()

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        assert payload["scan_kind"] == "targeted"
        assert payload["business_delta"]["added"] == ["cart_has_items"]
        assert "SafeSym" not in payload["instruction"]
        return '{"location_id":"shopping","newly_enabled":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.location_id == "shopping"
    assert result.business_affordances == []


def test_targeted_scan_parses_semantic_replacement():
    result = summarize_visual_affordances(
        _targeted_request(),
        provider=lambda *_args, **_kwargs: json.dumps(
            {
                "location_id": "shopping",
                "newly_enabled": [
                    {
                        "intent": "open_checkout",
                        "label": "Cart",
                        "target": "cart button",
                        "confidence": 0.9,
                        "supporting_facts": ["cart_has_items"],
                    }
                ],
                "semantically_changed": [
                    {
                        "old_action": "open_empty_cart",
                        "new_action": "open_checkout",
                    }
                ],
                "disabled": ["open_empty_cart"],
            }
        ),
    )

    assert [item.action_name for item in result.business_affordances] == [
        "open_checkout"
    ]
    assert result.replacements == [("open_empty_cart", "open_checkout")]
    assert result.disabled_action_ids == ["open_empty_cart"]


def test_summarize_visual_affordances_rejects_non_object_response():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return '["add_item_to_cart"]'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "parse_error"
    assert result.business_affordances == []


def test_summarize_visual_affordances_normalizes_supporting_facts():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return (
            '{"regions":[{"actions":[{"intent":"inspect",'
            '"supporting_facts":[" visible_control ","","   ",'
            '"visible_control","second_fact","third_fact","fourth_fact",'
            '"fifth_fact","sixth_fact","seventh_fact","eighth_fact",'
            '"ninth_fact"]}]}]}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.business_affordances[0].supporting_facts == [
        "visible_control",
        "second_fact",
        "third_fact",
        "fourth_fact",
        "fifth_fact",
        "sixth_fact",
        "seventh_fact",
        "eighth_fact",
        "ninth_fact",
    ][:8]


def test_summarize_visual_affordances_ignores_removed_candidate_fields():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return '{"business_affordances":[{"action_name":"legacy_action","expected_change":"legacy"}]}'

    result = summarize_visual_affordances(request, provider=provider)

    affordance = result.business_affordances[0]
    assert affordance.action_name == "legacy_action"
    assert "expected_change" not in affordance.to_dict()
    assert "evidence" not in affordance.to_dict()
