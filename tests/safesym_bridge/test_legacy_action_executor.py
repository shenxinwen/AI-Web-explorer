from __future__ import annotations

from ai_web_explorer.safesym_bridge.legacy_action_executor import (
    LegacyActionExecutor,
)
from ai_web_explorer.grounded_web.graph import BrowserAction


class FakeLocator:
    def __init__(self, selector: str, calls: list[tuple]) -> None:
        self.selector = selector
        self.calls = calls
        self.first = self

    def scroll_into_view_if_needed(self, *, timeout: int) -> None:
        self.calls.append(("scroll", self.selector, timeout))

    def click(self, *, timeout: int) -> None:
        self.calls.append(("click", self.selector, timeout))

    def fill(self, value: str, *, timeout: int) -> None:
        self.calls.append(("fill", self.selector, value, timeout))

    def select_option(self, value: str, *, timeout: int) -> None:
        self.calls.append(("select", self.selector, value, timeout))


class FailingLocator(FakeLocator):
    def click(self, *, timeout: int) -> None:
        raise RuntimeError("click failed")


class FakePage:
    def __init__(self, *, failing_selector: str | None = None) -> None:
        self.calls: list[tuple] = []
        self.failing_selector = failing_selector

    def locator(self, selector: str):
        if selector == self.failing_selector:
            return FailingLocator(selector, self.calls)
        return FakeLocator(selector, self.calls)


def _executor(page: FakePage) -> LegacyActionExecutor:
    return LegacyActionExecutor(page, timeout=123, sleep_seconds=0)


def test_click_action_scrolls_then_clicks_target_locator() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="click",
        locator="#buy",
        semantic_id="buy",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#buy", 123),
        ("click", "#buy", 123),
    ]


def test_fill_action_uses_first_input_value() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill",
        locator="#email",
        semantic_id="fill_email",
        input_values={"#email": "student@example.com"},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#email", 123),
        ("fill", "#email", "student@example.com", 123),
    ]


def test_fill_action_uses_safe_default_when_no_value_is_available() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill",
        locator="#search",
        semantic_id="fill_search",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#search", 123),
        ("fill", "#search", "test", 123),
    ]


def test_select_action_uses_first_input_value() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="select",
        locator="#country",
        semantic_id="select_country",
        input_values={"#country": "US"},
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#country", 123),
        ("select", "#country", "US", 123),
    ]


def test_select_action_without_value_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="select",
        locator="#country",
        semantic_id="select_country",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_fill_then_click_fills_each_field_then_clicks_target() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="fill_then_click",
        locator="#submit",
        semantic_id="submit_login",
        input_values={
            "#username": "standard_user",
            "#password": "secret_sauce",
        },
    )

    assert _executor(page).execute_browser_action(action) is True

    assert page.calls == [
        ("scroll", "#username", 123),
        ("fill", "#username", "standard_user", 123),
        ("scroll", "#password", 123),
        ("fill", "#password", "secret_sauce", 123),
        ("scroll", "#submit", 123),
        ("click", "#submit", 123),
    ]


def test_action_without_locator_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="click",
        locator=None,
        semantic_id="missing_locator",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_unsupported_action_kind_returns_false() -> None:
    page = FakePage()
    action = BrowserAction(
        action_kind="hover",
        locator="#menu",
        semantic_id="hover_menu",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False

    assert page.calls == []


def test_playwright_operation_exception_returns_false() -> None:
    page = FakePage(failing_selector="#buy")
    action = BrowserAction(
        action_kind="click",
        locator="#buy",
        semantic_id="buy",
        input_values={},
    )

    assert _executor(page).execute_browser_action(action) is False
