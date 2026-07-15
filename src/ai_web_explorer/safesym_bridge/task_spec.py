from __future__ import annotations

"""Fixed SauceDemo MVP transitions used by graph/PDDL regression paths."""

from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.grounded_web.models import (
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
    semantic_id: str,
) -> ObservedTransition:
    return ObservedTransition(
        source=before,
        target=after,
        action=ObservedAction(
            raw_description=raw_description,
            semantic_id=semantic_id,
            playwright_calls=[],
        ),
        preconditions=preconditions_for(semantic_id),
        effects=infer_effects(before, after),
    )


def build_saucedemo_mvp_transitions() -> list[ObservedTransition]:
    login_ready = _snapshot(
        "login",
        {
            "username_filled": True,
            "password_filled": True,
            "is_logged_in": False,
            "cart_count": 0,
        },
    )
    inventory_empty = _snapshot(
        "inventory",
        {
            "username_filled": True,
            "password_filled": True,
            "is_logged_in": True,
            "cart_count": 0,
        },
    )
    inventory_with_cart = _snapshot(
        "inventory",
        {
            "is_logged_in": True,
            "cart_count": 1,
        },
    )
    cart = _snapshot(
        "cart",
        {
            "is_logged_in": True,
            "cart_count": 1,
        },
    )
    checkout_info_empty = _snapshot(
        "checkout_info",
        {
            "cart_count": 1,
            "checkout_started": True,
            "checkout_info_filled": False,
        },
    )
    checkout_info_filled = _snapshot(
        "checkout_info",
        {
            "cart_count": 1,
            "checkout_started": True,
            "checkout_info_filled": True,
        },
    )
    checkout_overview = _snapshot(
        "checkout_overview",
        {
            "cart_count": 1,
            "checkout_started": True,
            "checkout_info_filled": True,
            "order_review_ready": True,
            "order_created": False,
        },
    )
    checkout_complete = _snapshot(
        "checkout_complete",
        {
            "cart_count": 1,
            "order_review_ready": True,
            "order_created": True,
        },
    )

    return [
        _transition(
            login_ready, inventory_empty, "Click the Login button", "login_submit"
        ),
        _transition(
            inventory_empty,
            inventory_with_cart,
            "Click Add to cart",
            "product_add_to_cart",
        ),
        _transition(
            inventory_with_cart,
            cart,
            "Click the shopping cart link",
            "cart_open",
        ),
        _transition(cart, checkout_info_empty, "Click Checkout", "cart_checkout_start"),
        _transition(
            checkout_info_filled,
            checkout_overview,
            "Click Continue on checkout information",
            "checkout_info_submit",
        ),
        _transition(
            checkout_overview,
            checkout_complete,
            "Click Finish",
            "order_place_confirm",
        ),
    ]
