import pytest

from ai_web_explorer.grounded_web.exploration_semantics import (
    validate_final_order_authorization,
)


def test_final_order_authorization_requires_explicit_allow_flag():
    assert validate_final_order_authorization(
        start_url="https://practiceautomatedtesting.com/shopping",
        allowed=False,
    ) is False


def test_final_order_authorization_accepts_only_controlled_shopping_url():
    assert validate_final_order_authorization(
        start_url="https://practiceautomatedtesting.com/shopping",
        allowed=True,
    ) is True

    for start_url in (
        "https://practiceautomatedtesting.com/",
        "https://practiceautomatedtesting.com/shopping?redirect=order",
        "https://evil.practiceautomatedtesting.com/shopping",
    ):
        with pytest.raises(ValueError, match="controlled test URL"):
            validate_final_order_authorization(start_url=start_url, allowed=True)
