from __future__ import annotations

import logging
import time
from typing import Any

from ai_web_explorer import config
from ai_web_explorer.grounded_web.graph import BrowserAction


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


class LegacyActionExecutor:
    """Sync Playwright-style executor for already-grounded browser actions.

    This reuses the original ai-web-explorer operation pattern: locate the
    element, scroll it into view, perform click/fill/select, then wait briefly.
    It does not call LLMs or choose actions.
    """

    def __init__(
        self,
        page: Any,
        *,
        timeout: int = config.PLAYWRIGHT_TIMEOUT,
        sleep_seconds: float = config.ACTION_SLEEP_TIME,
    ) -> None:
        self._page = page
        self._timeout = timeout
        self._sleep_seconds = sleep_seconds

    def execute_browser_action(self, action: BrowserAction) -> bool:
        if action.locator is None:
            return False

        try:
            if action.action_kind == "click":
                self._click(action.locator)
            elif action.action_kind == "fill":
                self._fill(
                    action.locator,
                    _first_input_value(action.input_values) or "test",
                )
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return False
                self._select(action.locator, value)
            elif action.action_kind == "fill_then_click":
                for selector, value in action.input_values.items():
                    self._fill(selector, value)
                self._click(action.locator)
            else:
                return False

            if self._sleep_seconds > 0:
                time.sleep(self._sleep_seconds)
            return True
        except Exception:
            logging.exception("Failed to execute grounded browser action")
            return False

    def _first_locator(self, selector: str):
        locator = self._page.locator(selector).first
        locator.scroll_into_view_if_needed(timeout=self._timeout)
        return locator

    def _click(self, selector: str) -> None:
        self._first_locator(selector).click(timeout=self._timeout)

    def _fill(self, selector: str, value: str) -> None:
        self._first_locator(selector).fill(value, timeout=self._timeout)

    def _select(self, selector: str, value: str) -> None:
        self._first_locator(selector).select_option(value, timeout=self._timeout)
