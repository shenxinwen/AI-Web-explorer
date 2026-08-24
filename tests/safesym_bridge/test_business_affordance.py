import dataclasses
import json
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    summarize_visual_affordances,
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
    )

    def provider(prompt, *, current_screenshot_path):
        payload = json.loads(prompt)
        instruction = payload["instruction"]
        assert payload["output_schema"] == {
            "location_id": "short stable snake_case active surface name",
            "actions": [
                {
                    "action_id": "stable_snake_case_action",
                    "description": "one precise visible semantic operation",
                    "target": "visible target",
                    "execution_policy": "single_instance | composite",
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
        assert "directly executable" in instruction
        assert "active interaction surface" in instruction
        assert "limit is not a quota" in instruction
        assert "independently" in instruction
        assert "indispensable direct prerequisite" in instruction
        assert "independent-field order" in instruction
        assert current_screenshot_path == "current.png"
        return json.dumps(
            {
                "location_id": "account_form",
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
    assert result.location_id == "account_form"
    assert [item.action_name for item in result.business_affordances] == [
        "fill_identity",
        "submit_form",
    ]
    assert result.requires_by_action_id == {
        "fill_identity": [],
        "submit_form": ["fill_identity"],
    }


def test_initial_prompt_contains_validated_domain_neutral_few_shots():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
        max_actions=8,
    )
    captured = {}

    def provider(prompt, *, current_screenshot_path):
        captured["prompt"] = prompt
        return '{"actions":[]}'

    result = summarize_visual_affordances(request, provider=provider)
    payload = json.loads(captured["prompt"])
    examples = json.dumps(payload["few_shot_examples"])

    assert set(payload) == {
        "instruction",
        "max_candidates",
        "output_schema",
        "few_shot_examples",
    }
    assert set(payload["output_schema"]) == {"location_id", "actions"}
    assert payload["output_schema"]["actions"][0]["execution_policy"] == (
        "single_instance | composite"
    )
    assert "active surface" in payload["instruction"]
    assert "item counts" in payload["instruction"]
    assert len(payload["few_shot_examples"]) == 5
    assert "active interaction surface" in payload["instruction"]
    assert "limit is not a quota" in payload["instruction"]
    assert "independently" in payload["instruction"]
    assert "grouping is mandatory" in payload["instruction"].lower()
    assert "execution parameter" in payload["instruction"].lower()
    assert "exactly one instance" in payload["instruction"].lower()
    assert "batch" not in payload["instruction"].lower()
    assert "execution_policy" in payload["instruction"]
    assert "single_instance" in payload["instruction"]
    assert "composite" in payload["instruction"]
    assert "distinct atomic steps" in payload["instruction"]
    assert "selectable value" in payload["instruction"].lower()
    assert "result subset" in payload["instruction"].lower()
    assert "sort field or direction" in payload["instruction"].lower()
    assert "prefer precision over recall" in payload["instruction"].lower()
    assert "controls whose meaning cannot be determined confidently" in payload[
        "instruction"
    ].lower()
    assert "hidden or speculative actions" in payload["instruction"].lower()
    assert "group related fields" in payload["instruction"].lower()
    assert "successful or informational page" in payload["instruction"].lower()
    assert "text describing success, completion, history" in payload[
        "instruction"
    ].lower()
    assert "two independent filters" in payload["instruction"].lower()
    assert "maximum action count is an upper bound" in payload[
        "instruction"
    ].lower()
    assert "shopping-cart icon" in payload["instruction"].lower()
    assert "open_cart or view_cart" in payload["instruction"].lower()
    assert "badge is not required" in payload["instruction"].lower()
    assert "profile" not in captured["prompt"].lower()
    assert "checkout" not in captured["prompt"].lower()
    assert "payment" not in captured["prompt"].lower()
    for token in (
        "Create Project",
        "complete_project_details",
        "data-table toolbar",
        "Export Complete",
        "download_report",
        "open_record",
        "open_record_a",
        "filter_results",
        "filter_by_status",
        "sort_newest",
    ):
        assert token in examples
    for token in (
        "Add to cart",
        "shopping cart",
        "enter_credentials",
        "Username and Password fields",
    ):
        assert token not in examples
    for example in payload["few_shot_examples"]:
        action_items = example.get("actions") or example.get("correct_actions") or []
        for item in action_items:
            if isinstance(item, dict):
                assert item["execution_policy"] in {
                    "single_instance",
                    "composite",
                }
    assert result.trace.status == "summarized"


def test_initial_scan_parses_execution_policy_into_affordance():
    request = VisualAffordanceRequest(
        goal="Explore visible business capabilities.",
        current_screenshot_path="current.png",
    )

    def provider(prompt, *, current_screenshot_path):
        return json.dumps(
            {
                "actions": [
                    {
                        "action_id": "enter_credentials",
                        "description": "Fill in the username and password fields.",
                        "target": "Username and Password fields",
                        "execution_policy": "composite",
                        "requires": [],
                    }
                ]
            }
        )

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.business_affordances[0].execution_policy == "composite"


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

        assert "group visible controls by semantic effect" in instruction
        assert "concrete object is an execution parameter" in instruction
        assert "at most 5 actions" in instruction
        assert action_schema["action_id"] == "stable_snake_case_action"
        assert set(action_schema) == {
            "action_id",
            "description",
            "target",
            "execution_policy",
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

    captured = {}

    def provider(prompt, *, current_screenshot_path):
        captured["prompt"] = prompt
        return '{"actions":[]}'

    result = summarize_visual_affordances(request, provider=provider)

    assert result.trace.status == "summarized"
    assert result.business_affordances == []
    prompt = captured["prompt"]
    assert "at most 5 actions" in prompt
    assert "profile" not in prompt.lower()


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


def test_summarize_visual_affordances_rejects_response_over_max_actions():
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

    assert result.business_affordances == []
    assert result.trace.status == "failed"
    assert result.trace.error_type == "response_contract_error"
    assert result.trace.error_message == "initial response exceeds the action limit"


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
