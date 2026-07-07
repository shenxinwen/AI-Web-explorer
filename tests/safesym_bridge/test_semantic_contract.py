from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import ObservedTransition
from ai_web_explorer.safesym_bridge.semantic_contract import (
    validate_observed_fsm_contract,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_observed_contract_allows_extra_effects_but_requires_order_created():
    fixed = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )
    observed_transitions = [
        _with_extra_order_finish_effect(transition)
        for transition in build_saucedemo_mvp_transitions()
    ]
    observed = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=observed_transitions,
    )

    result = validate_observed_fsm_contract(fixed=fixed, observed=observed)

    assert result.ok is True
    assert result.errors == []


def test_observed_contract_rejects_missing_order_created_effect():
    fixed = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )
    observed_transitions = [
        _without_order_created_effect(transition)
        for transition in build_saucedemo_mvp_transitions()
    ]
    observed = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=observed_transitions,
    )

    result = validate_observed_fsm_contract(fixed=fixed, observed=observed)

    assert result.ok is False
    assert (
        "observed order_place_confirm is missing required effect "
        "{'path': '$.order_created', 'op': 'set', 'value': True}"
    ) in result.errors


def _with_extra_order_finish_effect(
    transition: ObservedTransition,
) -> ObservedTransition:
    if transition.action.semantic_id != "order_place_confirm":
        return transition
    return ObservedTransition(
        source=transition.source,
        target=transition.target,
        action=transition.action,
        preconditions=transition.preconditions,
        effects=[
            {"path": "$.cart_count", "op": "set", "value": 0},
            *transition.effects,
        ],
    )


def _without_order_created_effect(
    transition: ObservedTransition,
) -> ObservedTransition:
    if transition.action.semantic_id != "order_place_confirm":
        return transition
    return ObservedTransition(
        source=transition.source,
        target=transition.target,
        action=transition.action,
        preconditions=transition.preconditions,
        effects=[],
    )
