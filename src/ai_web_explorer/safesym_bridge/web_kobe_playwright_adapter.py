from __future__ import annotations

import re
from typing import Any

from ai_web_explorer.safesym_bridge.dom_observer import extract_dom_interactables
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_adapter import static_actions_for_state
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state
from ai_web_explorer.safesym_bridge.web_action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "page"


def _coerce_state_value(value: str) -> Any:
    stripped = value.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    return stripped


async def _optional_inner_text(page, selector: str) -> str | None:
    locator = page.locator(selector)
    if await locator.count() == 0:
        return None
    return (await locator.first.inner_text()).strip()


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


async def _data_state_signature(page) -> dict[str, Any]:
    signature: dict[str, Any] = {}
    try:
        locator = page.locator("[data-state]")
        count = await locator.count()
    except Exception:
        return signature

    for index in range(count):
        element = locator.nth(index)
        try:
            raw_key = await element.get_attribute("data-state")
        except Exception:
            raw_key = None
        if not raw_key:
            continue
        key = _slug(raw_key)
        text = (await element.inner_text()).strip()
        if text:
            signature[key] = _coerce_state_value(text)
        try:
            signature[f"{key}_visible"] = await element.is_visible()
        except Exception:
            pass
    return signature


class WebKobePlaywrightAdapter:
    """Playwright-backed AutomationBackend for Web-KOBE exploration.

    This class operates the browser and exposes grounded page observations and
    actions. Exploration strategy, graph recording, and SafeSym/PDDL projection
    stay in the Web-KOBE layer.
    """

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
        if self.app_name == "saucedemo":
            snapshot = await observe_saucedemo_state(self.page)
            if self.page_id is not None:
                return StateSnapshot(
                    page_id=self.page_id,
                    url=snapshot.url,
                    title=snapshot.title,
                    signature=snapshot.signature,
                )
            return snapshot

        title = await self.page.title()
        page_id = self.page_id or _slug(title or self.page.url)
        signature: dict[str, Any] = await _data_state_signature(self.page)

        if "cart_count" not in signature:
            cart_text = await _optional_inner_text(self.page, '[data-state="cart-count"]')
            if cart_text is None:
                cart_text = await _optional_inner_text(self.page, "#cart-count")
            if cart_text is not None:
                match = re.search(r"-?\d+", cart_text)
                cart_count = int(match.group(0)) if match else 0
                signature["cart_count"] = cart_count

        if "cart_count" in signature:
            signature["cart_nonempty"] = int(signature["cart_count"]) > 0

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
        if self.app_name == "saucedemo":
            return [
                {
                    "semantic_id": action.semantic_id,
                    "description": action.raw_description,
                    "locator": action.selector,
                    "action_kind": action.execution_kind,
                    "input_values": dict(action.values),
                    "explored": False,
                }
                for action in static_actions_for_state(state)
            ]

        candidates = await extract_dom_interactables(self.page)
        actions = browser_actions_from_candidates(candidates)
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "action_kind": action.action_kind,
                "input_values": dict(action.input_values),
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
            elif action.action_kind == "fill_then_click":
                for selector, value in action.input_values.items():
                    await self.page.locator(selector).first.fill(value)
                await locator.click()
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
