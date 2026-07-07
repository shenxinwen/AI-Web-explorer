from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)


def test_state_snapshot_stores_signature():
    snapshot = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"$.cart_count": 1, "$.is_logged_in": True},
    )

    assert snapshot.page_id == "inventory"
    assert snapshot.signature["$.cart_count"] == 1
    assert snapshot.signature["$.is_logged_in"] is True


def test_observed_transition_stores_before_action_and_after():
    before = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"$.cart_count": 0},
    )
    after = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"$.cart_count": 1},
    )
    action = ObservedAction(
        raw_description="Click Add to cart",
        semantic_id="product_add_to_cart",
    )

    transition = ObservedTransition(
        source=before,
        target=after,
        action=action,
        effects=[{"path": "$.cart_count", "op": "set", "value": 1}],
    )

    assert transition.source.signature["$.cart_count"] == 0
    assert transition.target.signature["$.cart_count"] == 1
    assert transition.action.semantic_id == "product_add_to_cart"
    assert transition.effects == [{"path": "$.cart_count", "op": "set", "value": 1}]
