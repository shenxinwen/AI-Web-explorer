from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_summary import build_state_summary


def test_build_state_summary_includes_page_controls_and_planning_facts():
    snapshot = StateSnapshot(
        page_id="products",
        url="https://shop.test/products?sort=price",
        title="Products",
        signature={
            "url_path": "/products",
            "cart_count": 1,
            "modal_open": False,
        },
    )
    interactables = [
        {
            "semantic_id": "add_to_cart_backpack",
            "description": "Add backpack to cart",
            "action_kind": "click",
        },
        {
            "semantic_id": "open_cart",
            "description": "Open cart",
            "action_kind": "click",
        },
    ]

    summary = build_state_summary(
        snapshot=snapshot,
        interactables=interactables,
        active_planning_facts=["cart_has_items"],
        visual_summary="Cart badge shows 1 item.",
    )

    assert "url_path: /products" in summary.text
    assert "title: Products" in summary.text
    assert "planning_facts: cart_has_items" in summary.text
    assert "controls: Add backpack to cart; Open cart" in summary.text
    assert "visual: Cart badge shows 1 item." in summary.text
    assert summary.context_markers == ("cart_non_empty",)
    assert summary.planning_facts == ("cart_has_items",)
