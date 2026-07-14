from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
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

    assert draft.node_id == "inventory"
    assert draft.page_description == "inventory page"
    assert draft.page_frame.page_type == "inventory"
    assert draft.state_schema == {"cart_count": [0], "is_logged_in": [True]}
    assert draft.last_state_snapshot == {"cart_count": 0, "is_logged_in": True}
    assert draft.interactable_elements[0]["semantic_id"] == "product_add_to_cart"
