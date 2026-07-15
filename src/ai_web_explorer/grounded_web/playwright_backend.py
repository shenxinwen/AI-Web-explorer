from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from ai_web_explorer.grounded_web.action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.grounded_web.dom_observer import extract_dom_interactables
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_signature import (
    coerce_state_value,
    slug_identifier,
)

StateObserver = Callable[[Any], Awaitable[StateSnapshot]]
ActionProvider = Callable[[StateSnapshot], list[BrowserAction | dict[str, Any]]]


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
        key = slug_identifier(raw_key, fallback="state")
        text = (await element.inner_text()).strip()
        if text:
            signature[key] = coerce_state_value(text)
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
        state_observer: StateObserver | None = None,
        action_provider: ActionProvider | None = None,
    ):
        self.page = page
        self.app_name = app_name
        self.page_id = page_id
        self.state_observer = state_observer
        self.action_provider = action_provider
        self.last_execution_error: str | None = None

    async def observe_state(self) -> StateSnapshot:
        if self.state_observer is not None:
            snapshot = await self.state_observer(self.page)
            if self.page_id is not None:
                return StateSnapshot(
                    page_id=self.page_id,
                    url=snapshot.url,
                    title=snapshot.title,
                    signature=snapshot.signature,
                )
            return snapshot

        title = await self.page.title()
        page_id = self.page_id or slug_identifier(
            title or self.page.url, fallback="page"
        )
        signature: dict[str, Any] = await _data_state_signature(self.page)

        if "cart_count" not in signature:
            cart_text = await _optional_inner_text(
                self.page, '[data-state="cart-count"]'
            )
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
        if self.action_provider is not None:
            return [
                _interactable_record(action) for action in self.action_provider(state)
            ]

        candidates = await extract_dom_interactables(self.page)
        actions = browser_actions_from_candidates(candidates)
        return [
            {
                "semantic_id": action.semantic_id,
                "description": action.description,
                "locator": action.locator,
                "locator_strategy": candidate.locator_strategy,
                "action_kind": action.action_kind,
                "input_values": dict(action.input_values),
                "metadata": dict(candidate.metadata),
                "explored": False,
            }
            for candidate, action in zip(candidates, actions, strict=True)
        ]

    def _fail_execution(self, error: str) -> bool:
        self.last_execution_error = error
        return False

    async def _settle_page(self) -> None:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=1000)
        except Exception:
            self.last_execution_error = "page_settle_timeout"
        await self.page.wait_for_timeout(100)

    async def execute(self, action: BrowserAction) -> bool:
        self.last_execution_error = None
        if action.locator is None:
            return self._fail_execution("no_locator")
        locator = self.page.locator(action.locator)
        try:
            if await locator.count() == 0:
                return self._fail_execution("locator_not_found")

            target = locator.first
            if hasattr(target, "is_visible") and not await target.is_visible():
                return self._fail_execution("locator_not_visible")
            if hasattr(target, "is_enabled") and not await target.is_enabled():
                return self._fail_execution("locator_disabled")
            if hasattr(target, "scroll_into_view_if_needed"):
                await target.scroll_into_view_if_needed()

            if action.action_kind == "click":
                await target.click()
            elif action.action_kind == "fill":
                await target.fill(_first_input_value(action.input_values) or "test")
            elif action.action_kind == "fill_then_click":
                for selector, value in action.input_values.items():
                    fill_target = self.page.locator(selector).first
                    if hasattr(fill_target, "scroll_into_view_if_needed"):
                        await fill_target.scroll_into_view_if_needed()
                    await fill_target.fill(value)
                await target.click()
            elif action.action_kind == "select":
                value = _first_input_value(action.input_values)
                if value is None:
                    return self._fail_execution("missing_select_value")
                await target.select_option(value)
            else:
                return self._fail_execution("unsupported_action_kind")
            await self._settle_page()
            return (
                self.last_execution_error is None
                or self.last_execution_error == "page_settle_timeout"
            )
        except Exception as exc:
            return self._fail_execution(f"playwright_error:{type(exc).__name__}")


PlaywrightBackend = WebKobePlaywrightAdapter


def _interactable_record(action: BrowserAction | dict[str, Any]) -> dict[str, Any]:
    if isinstance(action, BrowserAction):
        return {
            "semantic_id": action.semantic_id,
            "description": action.description,
            "locator": action.locator,
            "locator_strategy": None,
            "action_kind": action.action_kind,
            "input_values": dict(action.input_values),
            "metadata": {},
            "explored": False,
        }
    return {
        "semantic_id": action.get("semantic_id"),
        "description": action.get("description"),
        "locator": action.get("locator"),
        "locator_strategy": action.get("locator_strategy"),
        "action_kind": action.get("action_kind"),
        "input_values": dict(action.get("input_values") or {}),
        "metadata": dict(action.get("metadata") or {}),
        "explored": bool(action.get("explored", False)),
    }
