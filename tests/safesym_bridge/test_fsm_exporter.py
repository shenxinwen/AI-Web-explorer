from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm, schema_type_for
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


def test_schema_type_for_basic_json_values():
    assert schema_type_for(True) == "boolean"
    assert schema_type_for(1) == "number"
    assert schema_type_for("abc") == "string"
    assert schema_type_for(None) == "string"


def test_build_fsm_groups_actions_under_source_pages():
    transition = ObservedTransition(
        source=snapshot(
            "checkout_overview",
            {"$.cart_count": 1, "$.order_review_ready": True},
        ),
        target=snapshot(
            "checkout_complete",
            {
                "$.cart_count": 1,
                "$.order_review_ready": True,
                "$.order_created": True,
            },
        ),
        action=ObservedAction(
            raw_description="Click Finish",
            semantic_id="order_place_confirm",
            playwright_calls=[],
        ),
        preconditions=[
            {"path": "$.cart_count", "cond": "gt", "value": 0},
            {"path": "$.order_review_ready", "cond": "eq", "value": True},
        ],
        effects=[
            {"path": "$.order_created", "op": "set", "value": True},
        ],
    )

    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=[transition],
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
                    "$.order_created": "boolean",
                    "$.order_review_ready": "boolean",
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
            },
            {
                "id": "checkout_complete",
                "signature_schema": {
                    "$.cart_count": "number",
                    "$.order_created": "boolean",
                    "$.order_review_ready": "boolean",
                },
                "actions": [],
            },
        ],
    }


def test_saucedemo_mvp_transitions_export_target_actions():
    transitions = build_saucedemo_mvp_transitions()
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=transitions,
    )
    data = fsm.to_dict()

    actions = [action for page in data["pages"] for action in page["actions"]]
    action_ids = [action["id"] for action in actions]

    assert action_ids == [
        "login_submit",
        "product_add_to_cart",
        "cart_open",
        "cart_checkout_start",
        "checkout_info_submit",
        "order_place_confirm",
    ]

    add_to_cart = next(
        action for action in actions if action["id"] == "product_add_to_cart"
    )
    assert add_to_cart["from"] == "inventory"
    assert add_to_cart["to"] == "inventory"
    assert add_to_cart["is_navigation"] is False
    assert add_to_cart["effects"] == [
        {"path": "$.cart_count", "op": "set", "value": 1}
    ]

    order_confirm = next(
        action for action in actions if action["id"] == "order_place_confirm"
    )
    assert order_confirm["preconditions"] == [
        {"path": "$.cart_count", "cond": "gt", "value": 0},
        {"path": "$.order_review_ready", "cond": "eq", "value": True},
    ]
    assert order_confirm["effects"] == [
        {"path": "$.order_created", "op": "set", "value": True}
    ]
