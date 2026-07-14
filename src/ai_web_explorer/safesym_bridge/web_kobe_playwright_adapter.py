from __future__ import annotations

import re
from typing import Any

from ai_web_explorer.safesym_bridge.dom_observer import extract_dom_interactables
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "page"


async def _optional_inner_text(page, selector: str) -> str | None:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return None
    return (await locator.first.inner_text()).strip()


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


class WebKobePlaywrightAdapter:
    def __init__(
        self,
        page,
        *,
        app_name: str = "web",
        page_id: str | None = None,
    ):
        self.page = page
        self.app_name = app_name
        self.page_id = page_id

    async def observe_state(self) -> StateSnapshot:
        title = await self.page.title()
        page_id = self.page_id or _slug(title or self.page.url)
        signature: dict[str, Any] = {}

        cart_text = await _optional_inner_text(self.page, '[data-state="cart-count"]')
        if cart_text is None:
            cart_text = await _optional_inner_text(self.page, "#cart-count")
        if cart_text is not None:
            match = re.search(r"-?\d+", cart_text)
            cart_count = int(match.group(0)) if match else 0
            signature["cart_count"] = cart_count
            signature["cart_nonempty"] = cart_count > 0

        return StateSnapshot(
            page_id=page_id,
            url=self.page.url,
            title=title,
            signature=signature,
        )

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        candidates = await extract_dom_interactables(self.page)
        actions = browser_actions_from_candidates(candidates)
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "action_kind": action.action_kind,
                "explored": False,
            }
            for action in actions
        ]

    async def execute(self, action: BrowserAction) -> bool:
        if action.locator is None:
            return False
        locator = self.page.locator(action.locator).first
        try:
            if action.action_kind == "click":
                await locator.click()
            elif action.action_kind == "fill":
                await locator.fill(_first_input_value(action.input_values) or "test")
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return False
                await locator.select_option(value)
            else:
                return False
            await self.page.wait_for_timeout(100)
            return True
        except Exception:
            return False
