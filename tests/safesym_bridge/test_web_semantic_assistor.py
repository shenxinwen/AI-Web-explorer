from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)


def test_deterministic_semantic_assistor_builds_listing_state_draft():
    snapshot = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"cart_count": 0, "is_logged_in": True},
    )

    draft = DeterministicSemanticAssistor(app="saucedemo").describe_state(
        snapshot=snapshot,
        interactables=[
            {
                "semantic_id": "product_add_to_cart",
                "description": "Add to cart",
                "locator": 'button[data-test^="add-to-cart"]',
                "explored": False,
            }
        ],
    )

    assert draft.node_id.startswith("inventory__")
    assert draft.page_description == "inventory page"
    assert draft.page_frame.page_type == "inventory"
    assert draft.state_schema == {"cart_count": [0], "is_logged_in": [True]}
    assert draft.last_state_snapshot == {"cart_count": 0, "is_logged_in": True}
    assert draft.interactable_elements[0]["semantic_id"] == "product_add_to_cart"


def test_deterministic_semantic_assistor_uses_same_node_id_for_same_state():
    first = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"cart_count": 0, "is_logged_in": True},
    )
    second = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"is_logged_in": True, "cart_count": 0},
    )

    assistor = DeterministicSemanticAssistor(app="saucedemo")

    assert (
        assistor.describe_state(snapshot=first, interactables=[]).node_id
        == assistor.describe_state(snapshot=second, interactables=[]).node_id
    )


def test_deterministic_semantic_assistor_uses_different_node_id_for_changed_state():
    assistor = DeterministicSemanticAssistor(app="saucedemo")

    empty = assistor.describe_state(
        snapshot=StateSnapshot(
            page_id="inventory",
            url="https://www.saucedemo.com/inventory.html",
            title="Swag Labs",
            signature={"cart_count": 0},
        ),
        interactables=[],
    )
    filled = assistor.describe_state(
        snapshot=StateSnapshot(
            page_id="inventory",
            url="https://www.saucedemo.com/inventory.html",
            title="Swag Labs",
            signature={"cart_count": 1},
        ),
        interactables=[],
    )

    assert empty.node_id != filled.node_id
