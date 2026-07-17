from ai_web_explorer.safesym_bridge.state_observer import (
    observe_saucedemo_state,
    page_id_from_url,
    parse_cart_count,
    signature_from_observed_values,
    web_observation_from_saucedemo_values,
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

    assert signature["is_logged_in"] is True
    assert signature["cart_count"] == 1
    assert signature["checkout_started"] is True
    assert signature["order_review_ready"] is True
    assert signature["order_created"] is True


def test_signature_tracks_individual_checkout_info_fields():
    signature = signature_from_observed_values(
        "checkout_info",
        {
            "username_value": "",
            "password_value": "",
            "cart_count": 1,
            "checkout_first_name": "Safe",
            "checkout_last_name": "",
            "checkout_postal_code": "",
        },
    )

    assert signature["checkout_first_name_filled"] is True
    assert signature["checkout_last_name_filled"] is False
    assert signature["checkout_postal_code_filled"] is False
    assert signature["checkout_info_filled"] is False


def test_saucedemo_web_observation_exports_existing_signature():
    observation = web_observation_from_saucedemo_values(
        page_id="checkout_overview",
        url="https://www.saucedemo.com/checkout-step-two.html",
        title="Swag Labs",
        values={
            "username_value": "",
            "password_value": "",
            "cart_count": 1,
            "cart_badge_text": "1",
            "checkout_first_name": "Ada",
            "checkout_last_name": "Lovelace",
            "checkout_postal_code": "12345",
        },
    )

    assert observation.identity.page_id == "checkout_overview"
    assert observation.to_signature() == {
        "username_filled": False,
        "password_filled": False,
        "is_logged_in": True,
        "cart_count": 1,
        "checkout_started": True,
        "checkout_first_name_filled": True,
        "checkout_last_name_filled": True,
        "checkout_postal_code_filled": True,
        "checkout_info_filled": True,
        "order_review_ready": True,
        "order_created": False,
    }


def test_saucedemo_web_observation_records_fact_evidence():
    observation = web_observation_from_saucedemo_values(
        page_id="cart",
        url="https://www.saucedemo.com/cart.html",
        title="Swag Labs",
        values={
            "username_value": "",
            "password_value": "",
            "cart_count": 1,
            "cart_badge_text": "1",
            "checkout_first_name": "",
            "checkout_last_name": "",
            "checkout_postal_code": "",
        },
    )

    cart_count = observation.facts["cart_count"]
    assert cart_count.value == 1
    assert cart_count.evidence[0].source == "dom"
    assert cart_count.evidence[0].selector == ".shopping_cart_badge"
    assert cart_count.evidence[0].text == "1"

    order_created = observation.facts["order_created"]
    assert order_created.derived is True
    assert order_created.evidence[0].source == "url"
    assert order_created.evidence[0].url == "https://www.saucedemo.com/cart.html"


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
    assert snapshot.signature["cart_count"] == 1
    assert snapshot.signature["is_logged_in"] is True
