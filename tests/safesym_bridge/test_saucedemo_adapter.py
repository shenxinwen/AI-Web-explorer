from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_adapter import SauceDemoAdapter


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(page_id: str, *, order_created: bool = False) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title=page_id,
        signature={
            "$.username_filled": False,
            "$.password_filled": False,
            "$.is_logged_in": page_id != "login",
            "$.cart_count": 0,
            "$.checkout_started": page_id.startswith("checkout"),
            "$.checkout_info_filled": False,
            "$.order_review_ready": page_id
            in {
                "checkout_overview",
                "checkout_complete",
            },
            "$.order_created": order_created,
        },
    )


async def collect_ids(page_id: str) -> list[str]:
    adapter = SauceDemoAdapter()
    actions = await adapter.list_actions(object(), snapshot(page_id))
    return [action.semantic_id for action in actions]


def test_adapter_metadata():
    adapter = SauceDemoAdapter()

    assert adapter.app_name == "saucedemo"
    assert adapter.start_node == "login"
    assert adapter.start_url == "https://www.saucedemo.com/"


async def test_login_actions():
    assert await collect_ids("login") == ["login_submit"]


async def test_inventory_actions():
    assert await collect_ids("inventory") == ["product_add_to_cart", "cart_open"]


async def test_cart_actions():
    assert await collect_ids("cart") == ["cart_checkout_start"]


async def test_checkout_info_actions():
    assert await collect_ids("checkout_info") == ["checkout_info_submit"]


async def test_checkout_overview_actions():
    assert await collect_ids("checkout_overview") == ["order_place_confirm"]


async def test_checkout_complete_has_no_actions():
    assert await collect_ids("checkout_complete") == []


def test_goal_detection_requires_complete_page_and_order_created():
    adapter = SauceDemoAdapter()

    assert adapter.is_goal_state(snapshot("checkout_complete", order_created=True))
    assert not adapter.is_goal_state(snapshot("checkout_complete", order_created=False))
    assert not adapter.is_goal_state(snapshot("checkout_overview", order_created=True))
