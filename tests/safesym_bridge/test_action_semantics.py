import pytest

from ai_web_explorer.safesym_bridge.action_semantics import semantic_id_for


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Click the Login button", "login_submit"),
        ("click Add to cart for Sauce Labs Backpack", "product_add_to_cart"),
        ("Click the shopping cart link", "cart_open"),
        ("Click Checkout", "cart_checkout_start"),
        ("Click Continue on checkout information", "checkout_info_submit"),
        ("Click Finish", "order_place_confirm"),
    ],
)
def test_semantic_id_for_known_saucedemo_actions(raw, expected):
    assert semantic_id_for(raw) == expected


def test_semantic_id_for_unknown_action_returns_normalized_fallback():
    assert semantic_id_for("Open Product Details") == "open_product_details"
