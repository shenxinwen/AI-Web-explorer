from __future__ import annotations

"""Fixed SauceDemo MVP fixtures used by compatibility and regression paths."""

from ai_web_explorer.safesym_bridge.action_semantics import semantic_id_for
from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)

SAUCEDEMO_TASK: dict[str, object] = {
    "app": "saucedemo",
    "start_url": "https://www.saucedemo.com/",
    "goal": "complete_checkout",
    "credentials": {
        "username": "standard_user",
        "password": "secret_sauce",
    },
}


def _snapshot(page_id: str, signature: dict[str, object]) -> StateSnapshot:
    url_by_page = {
        "login": "https://www.saucedemo.com/",
        "inventory": "https://www.saucedemo.com/inventory.html",
        "cart": "https://www.saucedemo.com/cart.html",
        "checkout_info": "https://www.saucedemo.com/checkout-step-one.html",
        "checkout_overview": "https://www.saucedemo.com/checkout-step-two.html",
        "checkout_complete": "https://www.saucedemo.com/checkout-complete.html",
    }
    return StateSnapshot(
        page_id=page_id,
        url=url_by_page[page_id],
        title="Swag Labs",
        signature=signature,
    )


def _transition(
    before: StateSnapshot,
    after: StateSnapshot,
    raw_description: str,
) -> ObservedTransition:
    action_id = semantic_id_for(raw_description)
    return ObservedTransition(
        source=before,
        target=after,
        action=ObservedAction(
            raw_description=raw_description,
            semantic_id=action_id,
            playwright_calls=[],
        ),
        preconditions=preconditions_for(action_id),
        effects=infer_effects(before, after),
    )


def build_saucedemo_mvp_transitions() -> list[ObservedTransition]:
    login_ready = _snapshot(
        "login",
        {
            "$.username_filled": True,
            "$.password_filled": True,
            "$.is_logged_in": False,
            "$.cart_count": 0,
        },
    )
    inventory_empty = _snapshot(
        "inventory",
        {
            "$.username_filled": True,
            "$.password_filled": True,
            "$.is_logged_in": True,
            "$.cart_count": 0,
        },
    )
    inventory_with_cart = _snapshot(
        "inventory",
        {
            "$.is_logged_in": True,
            "$.cart_count": 1,
        },
    )
    cart = _snapshot(
        "cart",
        {
            "$.is_logged_in": True,
            "$.cart_count": 1,
        },
    )
    checkout_info_empty = _snapshot(
        "checkout_info",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": False,
        },
    )
    checkout_info_filled = _snapshot(
        "checkout_info",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": True,
        },
    )
    checkout_overview = _snapshot(
        "checkout_overview",
        {
            "$.cart_count": 1,
            "$.checkout_started": True,
            "$.checkout_info_filled": True,
            "$.order_review_ready": True,
            "$.order_created": False,
        },
    )
    checkout_complete = _snapshot(
        "checkout_complete",
        {
            "$.cart_count": 1,
            "$.order_review_ready": True,
            "$.order_created": True,
        },
    )

    return [
        _transition(login_ready, inventory_empty, "Click the Login button"),
        _transition(inventory_empty, inventory_with_cart, "Click Add to cart"),
        _transition(inventory_with_cart, cart, "Click the shopping cart link"),
        _transition(cart, checkout_info_empty, "Click Checkout"),
        _transition(
            checkout_info_filled,
            checkout_overview,
            "Click Continue on checkout information",
        ),
        _transition(checkout_overview, checkout_complete, "Click Finish"),
    ]
