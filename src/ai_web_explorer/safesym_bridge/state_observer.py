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

# 调用css选择器获取input的value，如果没有找到元素，则返回空字符串
async def _input_value_or_empty(page, selector: str) -> str:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return ""
    return await locator.input_value()


async def _inner_text_or_empty(page, selector: str) -> str:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return ""
    return await locator.inner_text()


async def observe_saucedemo_state(page) -> StateSnapshot:
    page_id = page_id_from_url(page.url)
    title = await page.title()
    cart_badge_text = await _inner_text_or_empty(page, ".shopping_cart_badge")
    
    # 检测当前page的状态，获取各种输入框的值和购物车数量等信息
    values = {
        "username_value": await _input_value_or_empty(page, "#user-name"),
        "password_value": await _input_value_or_empty(page, "#password"),
        "cart_count": parse_cart_count(cart_badge_text),
        "checkout_first_name": await _input_value_or_empty(page, "#first-name"),
        "checkout_last_name": await _input_value_or_empty(page, "#last-name"),
        "checkout_postal_code": await _input_value_or_empty(page, "#postal-code"),
    }
    
    return StateSnapshot(
        page_id=page_id,
        url=page.url,
        title=title,
        signature=signature_from_observed_values(page_id, values),
    )
