from __future__ import annotations

import re


def _normalize_fallback(raw_description: str) -> str:
    text = raw_description.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown_action"


def semantic_id_for(raw_description: str) -> str:
    text = raw_description.strip().lower()

    if "login" in text:
        return "login_submit"
    if "add to cart" in text:
        return "product_add_to_cart"
    if "shopping cart" in text or text in {"cart", "open cart", "click cart"}:
        return "cart_open"
    if "checkout" in text and "continue" not in text:
        return "cart_checkout_start"
    if "continue" in text and "checkout" in text:
        return "checkout_info_submit"
    if "finish" in text or "place order" in text or "confirm order" in text:
        return "order_place_confirm"

    return _normalize_fallback(raw_description)
