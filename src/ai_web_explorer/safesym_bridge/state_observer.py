from __future__ import annotations

from urllib.parse import urlparse

from ai_web_explorer.safesym_bridge.models import StateSnapshot


def page_id_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if path in {"", "/"}:
        return "login"
    if path.endswith("/inventory.html"):
        return "inventory"
    if path.endswith("/cart.html"):
        return "cart"
    if path.endswith("/checkout-step-one.html"):
        return "checkout_info"
    if path.endswith("/checkout-step-two.html"):
        return "checkout_overview"
    if path.endswith("/checkout-complete.html"):
        return "checkout_complete"
    return "unknown"


def parse_cart_count(text: str | None) -> int:
    if not text or not text.strip():
        return 0
    return int(text.strip())


def signature_from_observed_values(
    page_id: str,
    values: dict[str, object],
) -> dict[str, object]:
    username_value = str(values.get("username_value") or "")
    password_value = str(values.get("password_value") or "")
    first_name = str(values.get("checkout_first_name") or "")
    last_name = str(values.get("checkout_last_name") or "")
    postal_code = str(values.get("checkout_postal_code") or "")
    cart_count = int(values.get("cart_count") or 0)

    checkout_started = page_id in {
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }
    order_review_ready = page_id in {"checkout_overview", "checkout_complete"}
    order_created = page_id == "checkout_complete"

    return {
        "$.username_filled": bool(username_value),
        "$.password_filled": bool(password_value),
        "$.is_logged_in": page_id
        in {
            "inventory",
            "cart",
            "checkout_info",
            "checkout_overview",
            "checkout_complete",
        },
        "$.cart_count": cart_count,
        "$.checkout_started": checkout_started,
        "$.checkout_info_filled": bool(first_name and last_name and postal_code),
        "$.order_review_ready": order_review_ready,
        "$.order_created": order_created,
    }
