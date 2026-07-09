from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_catalog import (
    create_saucedemo_action_catalog,
)
from ai_web_explorer.safesym_bridge.semantic_resolver import SemanticMatch


def snapshot(page_id: str) -> StateSnapshot:
    return StateSnapshot(page_id, "", page_id, {})


def candidate(
    candidate_id: str,
    locator: str,
) -> DomInteractableCandidate:
    return DomInteractableCandidate(
        id=candidate_id,
        kind="button",
        locator=locator,
        locator_strategy="test",
        name="",
        visible=True,
        enabled=True,
        metadata={},
    )


def test_saucedemo_catalog_owns_login_values():
    catalog = create_saucedemo_action_catalog()
    login = candidate("dom_login", "#login-button")

    actions = catalog.build_actions(
        snapshot("login"),
        [SemanticMatch("dom_login", "login_submit", 1.0, "saucedemo_rule")],
        [login],
    )

    assert actions[0].execution_kind == "fill_then_click"
    assert actions[0].values == {
        "#user-name": "standard_user",
        "#password": "secret_sauce",
    }


def test_saucedemo_catalog_preserves_inventory_priority():
    catalog = create_saucedemo_action_catalog()
    cart = candidate("dom_cart", ".shopping_cart_link")
    add = candidate(
        "dom_add",
        '[data-test="add-to-cart-sauce-labs-backpack"]',
    )

    actions = catalog.build_actions(
        snapshot("inventory"),
        [
            SemanticMatch("dom_cart", "cart_open", 1.0, "saucedemo_rule"),
            SemanticMatch(
                "dom_add",
                "product_add_to_cart",
                1.0,
                "saucedemo_rule",
            ),
        ],
        [cart, add],
    )

    assert [action.semantic_id for action in actions] == [
        "product_add_to_cart",
        "cart_open",
    ]


@pytest.mark.parametrize(
    ("page_id", "token", "semantic_id", "execution_kind"),
    [
        ("cart", "checkout", "cart_checkout_start", "click"),
        ("checkout_info", "continue", "checkout_info_submit", "fill_then_click"),
        ("checkout_overview", "finish", "order_place_confirm", "click"),
    ],
)
def test_saucedemo_catalog_builds_checkout_actions(
    page_id,
    token,
    semantic_id,
    execution_kind,
):
    catalog = create_saucedemo_action_catalog()
    source = candidate(f"dom_{token}", f'[data-test="{token}"]')

    actions = catalog.build_actions(
        snapshot(page_id),
        [SemanticMatch(source.id, semantic_id, 1.0, "saucedemo_rule")],
        [source],
    )

    assert actions[0].semantic_id == semantic_id
    assert actions[0].execution_kind == execution_kind


def test_saucedemo_catalog_owns_checkout_information_values():
    catalog = create_saucedemo_action_catalog()
    source = candidate("dom_continue", "#continue")

    actions = catalog.build_actions(
        snapshot("checkout_info"),
        [
            SemanticMatch(
                "dom_continue",
                "checkout_info_submit",
                1.0,
                "saucedemo_rule",
            )
        ],
        [source],
    )

    assert actions[0].values == {
        "#first-name": "Safe",
        "#last-name": "Sym",
        "#postal-code": "12345",
    }
