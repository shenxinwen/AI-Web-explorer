from __future__ import annotations

from ai_web_explorer.safesym_bridge.models import Condition, Effect, StateSnapshot

_PRECONDITIONS: dict[str, list[Condition]] = {
    "login_submit": [
        {"path": "$.username_filled", "cond": "eq", "value": True},
        {"path": "$.password_filled", "cond": "eq", "value": True},
    ],
    "product_add_to_cart": [
        {"path": "$.is_logged_in", "cond": "eq", "value": True},
    ],
    "cart_checkout_start": [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
    ],
    "checkout_info_submit": [
        {"path": "$.checkout_info_filled", "cond": "eq", "value": True},
    ],
    "order_place_confirm": [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ],
}


def infer_effects(before: StateSnapshot, after: StateSnapshot) -> list[Effect]:
    effects: list[Effect] = []
    paths = sorted(after.signature)
    for path in paths:
        before_value = before.signature.get(path)
        after_value = after.signature.get(path)
        if before_value != after_value:
            effects.append({"path": path, "op": "set", "value": after_value})
    return effects


def preconditions_for(action_id: str) -> list[Condition]:
    return [dict(condition) for condition in _PRECONDITIONS.get(action_id, [])]
