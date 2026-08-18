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
        assert "semantic actions" in prompt
        assert current_screenshot_path == "current.png"
        return (
            '{"actions":['
            '{"action_id":"add_item_to_cart",'
            '"description":"Add a visible item to the cart",'
            '"target":"button labeled Add to cart on a visible item",'
            '"requires":[]},'
            '{"action_id":"open_cart",'
            '"description":"Open the cart",'
            '"target":"cart link", "requires":[]}'
            ']}'
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.state_summary is None
    assert result.state_label is None
    assert [item.action_name for item in result.business_affordances] == [
        "add_item_to_cart",
        "open_cart",
    ]
    assert result.requires_by_action_id == {
        "add_item_to_cart": [],
        "open_cart": [],
    }
    assert result.business_affordances[0].target_hint == (
        "button labeled Add to cart on a visible item"
    )
    assert result.business_affordances[0].supporting_facts == []


def test_initial_scan_parses_minimal_action_dependencies_without_planning_inputs():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
        max_actions=8,
        semantic_profile_context={"profile_id": "must_not_be_prompted"},
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        instruction = payload["instruction"]
        assert payload["output_schema"] == {
            "actions": [
                {
                    "action_id": "stable_snake_case_action",
                    "description": "one precise visible semantic operation",
                    "target": "visible target",
                    "requires": ["other_action_id"],
                }
            ]
        }
        assert "profile" not in prompt.lower()
        assert "contract" not in prompt.lower()
        assert "goal" not in prompt.lower()
        assert "regions" not in prompt.lower()
        assert "page_mode" not in prompt.lower()
        assert "relevance_hint" not in prompt.lower()
        assert "supporting_facts" not in prompt.lower()
        assert "confidence" not in prompt.lower()
        assert "directly executable" not in instruction
        assert "required fields" in instruction
        assert "disabled controls" in instruction
        assert "visible workflow structure" in instruction
        assert "login" in instruction
        assert "checkout" in instruction
        assert "domain common sense" not in instruction
        assert "typical workflow order" not in instruction
        assert current_screenshot_path == "current.png"
        return json.dumps(
            {
                "actions": [
                    {
                        "action_id": "fill_identity",
                        "description": "Fill the visible identity form",
                        "target": "identity form",
                        "requires": [],
                    },
                    {
                        "action_id": "submit_form",
                        "description": "Submit the visible form",
                        "target": "submit button",
                        "requires": ["fill_identity"],
                    },
                ]
            }
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert [item.action_name for item in result.business_affordances] == [
        "fill_identity",
        "submit_form",
    ]
    assert result.requires_by_action_id == {
        "fill_identity": [],
        "submit_form": ["fill_identity"],
    }


@pytest.mark.parametrize(
    "actions",
    [
        [{"action_id": "submit_form", "description": "Submit", "target": "button", "requires": ["missing"]}],
        [{"action_id": "submit_form", "description": "Submit", "target": "button", "requires": ["submit_form"]}],
        [
            {"action_id": "first", "description": "First", "target": "one", "requires": ["second"]},
            {"action_id": "second", "description": "Second", "target": "two", "requires": ["first"]},
        ],
    ],
)
def test_initial_scan_rejects_invalid_action_dependency_graph(actions):
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    result = summarize_visual_affordances(
        request,
        provider=lambda *_args, **_kwargs: json.dumps({"actions": actions}),
    )

    assert result.trace.status == "failed"
    assert result.trace.error_type == "response_contract_error"
    assert result.business_affordances == []


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
        action_schema = payload["output_schema"]["actions"][0]

        assert "distinct functional family" in instruction
        assert "at most 8 actions" in instruction
        assert action_schema["action_id"] == "stable_snake_case_action"
        assert set(action_schema) == {
            "action_id",
            "description",
            "target",
            "requires",
        }

        assert "profile" not in payload
        assert "current_planning_facts" not in payload
        assert request.goal not in prompt
        assert "pddl" not in prompt.lower()
        assert "graph" not in prompt.lower()
        assert "web-kobe" not in prompt.lower()
        assert "cart_has_items" not in prompt
        return '{"actions":[]}'

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
        assert "at most 8 actions" in prompt
        assert "Do not infer actions from common website patterns" in prompt
        assert "profile" not in prompt.lower()
        assert "checkout" not in prompt.lower()
        return '{"actions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.business_affordances == []


def test_visual_affordance_prompt_has_only_minimal_action_schema():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        assert set(payload["output_schema"]) == {"actions"}
        return '{"actions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.state_label is None


def test_visual_affordance_ignores_non_string_state_label_without_losing_actions():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return '{"actions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.state_label is None
    assert result.business_affordances == []


def test_summarize_visual_affordances_enforces_max_actions_upper_bound():
    request = VisualAffordanceRequest(
        goal="Explore shopping capabilities.",
        current_screenshot_path="current.png",
        max_actions=2,
    )

    def provider(prompt, *, current_screenshot_path):
        return json.dumps(
            {
                "actions": [
                    {"action_id": "first_action", "description": "First", "target": "First", "requires": []},
                    {"action_id": "second_action", "description": "Second", "target": "Second", "requires": []},
                    {"action_id": "third_action", "description": "Third", "target": "Third", "requires": []},
                ]
            }
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


def test_summarize_visual_affordances_normalizes_action_ids_and_requires():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return json.dumps(
            {
                "actions": [
                    {
                        "action_id": " Inspect Action ",
                        "description": "Inspect",
                        "target": "visible control",
                        "requires": ["", " Inspect Action "],
                    }
                ]
            }
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "failed"
    assert result.trace.error_type == "response_contract_error"


@pytest.mark.parametrize(
    "response",
    [
        '{"regions":[{"actions":[{"intent":"legacy_action","target":"button"}]}]}',
        '{"business_affordances":[{"action_name":"legacy_action","target_hint":"button"}]}',
    ],
)
def test_initial_scan_rejects_legacy_candidate_shapes(response):
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    result = summarize_visual_affordances(
        request,
        provider=lambda *_args, **_kwargs: response,
    )

    assert result.trace.status == "failed"
    assert result.trace.error_type == "response_contract_error"
    assert result.business_affordances == []


@pytest.mark.parametrize(
    "response",
    [
        '{"actions":[{"action_id":"fill_form","description":"Fill","target":"form"}]}',
        '{"actions":[{"action_id":"fill_form","description":"Fill","target":"form","requires":"other"}]}',
        '{"actions":[],"extra":"unexpected"}',
        '{"actions":[{"action_id":"fill_form","description":"Fill","target":"form","requires":[],"extra":true}]}',
        '{"actions":[{"action_id":"fill_form","description":"Fill","target":"form","requires":[1]}]}',
        '{"actions":[{"action_id":"fill_form","description":"Fill","target":"form","requires":[{}]}]}',
    ],
)
def test_initial_scan_rejects_non_strict_actions_contract(response):
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    result = summarize_visual_affordances(
        request,
        provider=lambda *_args, **_kwargs: response,
    )

    assert result.trace.status == "failed"
    assert result.trace.error_type == "response_contract_error"
    assert result.business_affordances == []
    assert result.requires_by_action_id == {}


def test_non_initial_scan_keeps_legacy_affordance_read_compatibility():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
        scan_kind="supplement",
    )

    def provider(prompt, *, current_screenshot_path):
        return '{"business_affordances":[{"action_name":"legacy_action","expected_change":"legacy"}]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.business_affordances[0].action_name == "legacy_action"
    assert "expected_change" not in result.business_affordances[0].to_dict()
