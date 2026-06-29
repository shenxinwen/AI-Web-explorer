from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


def test_infer_effects_returns_set_for_changed_values_only():
    before = snapshot(
        "inventory",
        {"$.is_logged_in": True, "$.cart_count": 0},
    )
    after = snapshot(
        "inventory",
        {"$.is_logged_in": True, "$.cart_count": 1},
    )

    assert infer_effects(before, after) == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]


def test_infer_effects_sorts_paths_for_stable_json():
    before = snapshot("a", {"$.z": False, "$.a": False})
    after = snapshot("b", {"$.z": True, "$.a": True})

    assert infer_effects(before, after) == [
        {"path": "$.a", "op": "set", "value": True},
        {"path": "$.z", "op": "set", "value": True},
    ]


def test_preconditions_for_order_place_confirm():
    assert preconditions_for("order_place_confirm") == [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ]


def test_preconditions_for_unknown_action_are_empty():
    assert preconditions_for("open_product_details") == []
