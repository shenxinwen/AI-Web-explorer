from ai_web_explorer.grounded_web.exploration_semantics import (
    validate_final_order_authorization,
)


def test_final_order_authorization_requires_explicit_allow_flag():
    assert validate_final_order_authorization(
        start_url="https://practiceautomatedtesting.com/shopping",
        allowed=False,
    ) is False


def test_final_order_authorization_allows_any_site_when_enabled():
    assert validate_final_order_authorization(
        start_url="https://practiceautomatedtesting.com/shopping",
        allowed=True,
    ) is True
    assert validate_final_order_authorization(
        start_url="https://www.saucedemo.com/",
        allowed=True,
    ) is True
    assert validate_final_order_authorization(
        start_url="https://fixture.test/shop?run=pilot",
        allowed=True,
    ) is True
