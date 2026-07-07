from __future__ import annotations

from ai_web_explorer.safesym_bridge.models import SafeSymAction, SafeSymFsm
from ai_web_explorer.safesym_bridge.validator import ValidationResult

ORDER_CREATED_EFFECT = {"path": "$.order_created", "op": "set", "value": True}


def validate_observed_fsm_contract(
    *,
    fixed: SafeSymFsm,
    observed: SafeSymFsm,
) -> ValidationResult:
    errors: list[str] = []
    fixed_actions = _actions_by_id(fixed)
    observed_actions = _actions_by_id(observed)

    if set(fixed_actions) != set(observed_actions):
        missing = sorted(set(fixed_actions) - set(observed_actions))
        extra = sorted(set(observed_actions) - set(fixed_actions))
        if missing:
            errors.append(f"observed FSM is missing actions: {missing}")
        if extra:
            errors.append(f"observed FSM has unexpected actions: {extra}")

    for action_id in sorted(set(fixed_actions) & set(observed_actions)):
        fixed_action = fixed_actions[action_id]
        observed_action = observed_actions[action_id]
        if fixed_action.from_page != observed_action.from_page:
            errors.append(
                f"action {action_id} from mismatch: "
                f"{fixed_action.from_page} != {observed_action.from_page}"
            )
        if fixed_action.to_page != observed_action.to_page:
            errors.append(
                f"action {action_id} to mismatch: "
                f"{fixed_action.to_page} != {observed_action.to_page}"
            )

    _validate_order_place_confirm(fixed_actions, observed_actions, errors)
    return ValidationResult(ok=not errors, errors=errors)


def _actions_by_id(fsm: SafeSymFsm) -> dict[str, SafeSymAction]:
    return {action.id: action for page in fsm.pages for action in page.actions}


def _validate_order_place_confirm(
    fixed_actions: dict[str, SafeSymAction],
    observed_actions: dict[str, SafeSymAction],
    errors: list[str],
) -> None:
    fixed_action = fixed_actions.get("order_place_confirm")
    observed_action = observed_actions.get("order_place_confirm")
    if fixed_action is None or observed_action is None:
        return

    if fixed_action.preconditions != observed_action.preconditions:
        errors.append(
            "order_place_confirm preconditions mismatch: "
            f"{fixed_action.preconditions} != {observed_action.preconditions}"
        )
    if ORDER_CREATED_EFFECT not in observed_action.effects:
        errors.append(
            "observed order_place_confirm is missing required effect "
            f"{ORDER_CREATED_EFFECT}"
        )
