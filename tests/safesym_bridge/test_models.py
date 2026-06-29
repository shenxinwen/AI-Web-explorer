from ai_web_explorer.safesym_bridge.models import (
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
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


def test_safesym_fsm_to_dict_uses_expected_json_shape():
    action = SafeSymAction(
        id="order_place_confirm",
        name="order_place_confirm",
        from_page="checkout_overview",
        to_page="checkout_complete",
        is_navigation=True,
        preconditions=[
            {"path": "$.cart_count", "cond": "gt", "value": 0},
            {"path": "$.order_review_ready", "cond": "eq", "value": True},
        ],
        effects=[
            {"path": "$.order_created", "op": "set", "value": True},
        ],
    )
    page = SafeSymPage(
        id="checkout_overview",
        signature_schema={
            "$.cart_count": "number",
            "$.order_review_ready": "boolean",
            "$.order_created": "boolean",
        },
        actions=[action],
    )
    fsm = SafeSymFsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        pages=[page],
    )

    assert fsm.to_dict() == {
        "meta": {
            "app": "saucedemo",
            "initial_page_id": "login",
            "terminal_pages": ["checkout_complete"],
        },
        "pages": [
            {
                "id": "checkout_overview",
                "signature_schema": {
                    "$.cart_count": "number",
                    "$.order_review_ready": "boolean",
                    "$.order_created": "boolean",
                },
                "actions": [
                    {
                        "id": "order_place_confirm",
                        "name": "order_place_confirm",
                        "from": "checkout_overview",
                        "to": "checkout_complete",
                        "is_navigation": True,
                        "preconditions": [
                            {"path": "$.cart_count", "cond": "gt", "value": 0},
                            {
                                "path": "$.order_review_ready",
                                "cond": "eq",
                                "value": True,
                            },
                        ],
                        "effects": [
                            {"path": "$.order_created", "op": "set", "value": True},
                        ],
                    }
                ],
            }
        ],
    }
