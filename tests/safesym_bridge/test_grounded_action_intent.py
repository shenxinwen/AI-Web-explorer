from ai_web_explorer.grounded_web.action_intent import (
    ActionExpectation,
    ActionIntent,
    evaluate_outcome,
    resolve_action_intent,
)
from ai_web_explorer.grounded_web.capability_graph import ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction


def test_resolve_action_intent_prefers_semantic_id_and_kind():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id="submit_search",
        target_description=None,
        input_values={},
        expectation=None,
        source="rule_based",
    )
    actions = [
        BrowserAction(
            action_kind="fill",
            locator="#query",
            semantic_id="query_input",
            description="Search query",
        ),
        BrowserAction(
            action_kind="click",
            locator="#submit",
            semantic_id="submit_search",
            description="Search",
        ),
    ]

    resolved = resolve_action_intent(intent, actions)

    assert resolved == actions[1]


def test_resolve_action_intent_falls_back_to_description_match():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id=None,
        target_description="search",
        input_values={},
        expectation=None,
        source="rule_based",
    )
    actions = [
        {
            "semantic_id": "submit_search",
            "description": "Search",
            "locator": "#submit",
            "action_kind": "click",
            "input_values": {},
        }
    ]

    resolved = resolve_action_intent(intent, actions)

    assert resolved is not None
    assert resolved.semantic_id == "submit_search"
    assert resolved.locator == "#submit"


def test_resolve_action_intent_returns_none_for_missing_target():
    intent = ActionIntent(
        action_kind="click",
        target_semantic_id="missing",
        target_description=None,
        input_values={},
        expectation=None,
        source="rule_based",
    )

    assert resolve_action_intent(intent, []) is None


def test_intent_input_values_override_resolved_action_values():
    intent = ActionIntent(
        action_kind="fill",
        target_semantic_id="query_input",
        target_description=None,
        input_values={"#query": "kobe"},
        expectation=None,
        source="rule_based",
    )
    action = BrowserAction(
        action_kind="fill",
        locator="#query",
        semantic_id="query_input",
        input_values={"#query": "test"},
        description="Query",
    )

    resolved = resolve_action_intent(intent, [action])

    assert resolved is not None
    assert resolved.input_values == {"#query": "kobe"}


def test_fill_then_click_intent_can_resolve_to_click_target():
    intent = ActionIntent(
        action_kind="fill_then_click",
        target_description="search",
        input_values={"#query": "kobe"},
        expectation=None,
        source="rule_based",
    )
    action = BrowserAction(
        action_kind="click",
        locator='[data-action="run-search"]',
        semantic_id="button_search",
        description="Search",
    )

    resolved = resolve_action_intent(intent, [action])

    assert resolved is not None
    assert resolved.action_kind == "fill_then_click"
    assert resolved.locator == '[data-action="run-search"]'
    assert resolved.input_values == {"#query": "kobe"}


def test_evaluate_outcome_failed_execution_preserves_error():
    outcome = evaluate_outcome(
        execution_success=False,
        execution_error="locator_not_visible",
        deltas=[],
        expectation=None,
    )

    assert outcome.status == "failed_execution"
    assert outcome.reason == "locator_not_visible"
    assert outcome.matched_expectation is False


def test_evaluate_outcome_no_observed_change():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[],
        expectation=None,
    )

    assert outcome.status == "no_observed_change"
    assert outcome.matched_expectation is None


def test_evaluate_outcome_field_changed_matches_delta():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[
            ObservedDelta(
                field="result_count",
                before=0,
                after=3,
                delta_type="numeric_changed",
            )
        ],
        expectation=ActionExpectation(kind="field_changed", field="result_count"),
    )

    assert outcome.status == "succeeded"
    assert outcome.matched_expectation is True


def test_evaluate_outcome_field_equals_mismatch_is_unexpected_change():
    outcome = evaluate_outcome(
        execution_success=True,
        execution_error=None,
        deltas=[
            ObservedDelta(
                field="status",
                before="idle",
                after="error",
                delta_type="value_changed",
            )
        ],
        expectation=ActionExpectation(
            kind="field_equals",
            field="status",
            expected_value="complete",
        ),
    )

    assert outcome.status == "unexpected_change"
    assert outcome.matched_expectation is False
