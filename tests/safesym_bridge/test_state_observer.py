from ai_web_explorer.safesym_bridge.state_observer import (
    page_id_from_url,
    parse_cart_count,
    signature_from_observed_values,
)


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
