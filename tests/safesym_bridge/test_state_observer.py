from ai_web_explorer.safesym_bridge.state_observer import (
    observe_saucedemo_state,
    page_id_from_url,
    parse_cart_count,
    signature_from_observed_values,
)
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_page_id_from_saucedemo_urls():
    assert page_id_from_url("https://www.saucedemo.com/") == "login"
    assert page_id_from_url("https://www.saucedemo.com/inventory.html") == "inventory"
    assert page_id_from_url("https://www.saucedemo.com/cart.html") == "cart"
    assert (
        page_id_from_url("https://www.saucedemo.com/checkout-step-one.html")
        == "checkout_info"
    )
    assert (
        page_id_from_url("https://www.saucedemo.com/checkout-step-two.html")
        == "checkout_overview"
    )
    assert (
        page_id_from_url("https://www.saucedemo.com/checkout-complete.html")
        == "checkout_complete"
    )


def test_parse_cart_count_defaults_to_zero_for_empty_badge():
    assert parse_cart_count(None) == 0
    assert parse_cart_count("") == 0
    assert parse_cart_count(" ") == 0


def test_parse_cart_count_reads_integer_badge():
    assert parse_cart_count("1") == 1
    assert parse_cart_count(" 3 ") == 3


def test_signature_from_observed_values_for_checkout_complete():
    signature = signature_from_observed_values(
        "checkout_complete",
        {
            "username_value": "",
            "password_value": "",
            "cart_count": 1,
            "checkout_first_name": "",
            "checkout_last_name": "",
            "checkout_postal_code": "",
        },
    )

    assert signature["$.is_logged_in"] is True
    assert signature["$.cart_count"] == 1
    assert signature["$.checkout_started"] is True
    assert signature["$.order_review_ready"] is True
    assert signature["$.order_created"] is True


class FakeLocator:
    def __init__(self, *, value="", text="", count=1):
        self._value = value
        self._text = text
        self._count = count

    async def count(self):
        return self._count

    async def input_value(self):
        return self._value

    async def inner_text(self):
        return self._text


class FakePage:
    url = "https://www.saucedemo.com/inventory.html"

    async def title(self):
        return "Swag Labs"

    def locator(self, selector):
        locators = {
            "#user-name": FakeLocator(value=""),
            "#password": FakeLocator(value=""),
            ".shopping_cart_badge": FakeLocator(text="1", count=1),
            "#first-name": FakeLocator(value="", count=0),
            "#last-name": FakeLocator(value="", count=0),
            "#postal-code": FakeLocator(value="", count=0),
        }
        return locators[selector]


@pytest.mark.anyio
async def test_observe_saucedemo_state_reads_page_snapshot():
    snapshot = await observe_saucedemo_state(FakePage())

    assert snapshot.page_id == "inventory"
    assert snapshot.url == "https://www.saucedemo.com/inventory.html"
    assert snapshot.title == "Swag Labs"
    assert snapshot.signature["$.cart_count"] == 1
    assert snapshot.signature["$.is_logged_in"] is True
