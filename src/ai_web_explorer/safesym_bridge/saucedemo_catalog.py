from __future__ import annotations

from ai_web_explorer.safesym_bridge.action_catalog import (
    ActionDefinition,
    DomainActionCatalog,
)


def create_saucedemo_action_catalog() -> DomainActionCatalog:
    return DomainActionCatalog(
        {
            ("login", "login_submit"): ActionDefinition(
                raw_description="Click the Login button",
                execution_kind="fill_then_click",
                values={
                    "#user-name": "standard_user",
                    "#password": "secret_sauce",
                },
                position="login form",
                priority=0,
            ),
            ("inventory", "product_add_to_cart"): ActionDefinition(
                raw_description="Click Add to cart",
                execution_kind="click",
                position="product list",
                priority=0,
            ),
            ("inventory", "cart_open"): ActionDefinition(
                raw_description="Click the shopping cart link",
                execution_kind="click",
                position="top right",
                priority=1,
            ),
            ("cart", "cart_checkout_start"): ActionDefinition(
                raw_description="Click Checkout",
                execution_kind="click",
                position="cart actions",
                priority=0,
            ),
            ("checkout_info", "checkout_info_submit"): ActionDefinition(
                raw_description="Click Continue on checkout information",
                execution_kind="fill_then_click",
                values={
                    "#first-name": "Safe",
                    "#last-name": "Sym",
                    "#postal-code": "12345",
                },
                position="checkout form",
                priority=0,
            ),
            ("checkout_overview", "order_place_confirm"): ActionDefinition(
                raw_description="Click Finish",
                execution_kind="click",
                position="checkout summary",
                priority=0,
            ),
        }
    )
