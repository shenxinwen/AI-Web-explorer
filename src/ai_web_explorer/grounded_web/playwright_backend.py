from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from ai_web_explorer.grounded_web.action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.grounded_web.dom_observer import extract_dom_interactables
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_facts import (
    facts_from_structure,
    state_signature_from_facts,
)
from ai_web_explorer.grounded_web.state_signature import slug_identifier
from ai_web_explorer.grounded_web.structure import observe_page_structure

StateObserver = Callable[[Any], Awaitable[StateSnapshot]]
ActionProvider = Callable[[StateSnapshot], list[BrowserAction | dict[str, Any]]]


def _first_input_value(values: dict[str, str]) -> str | None:
    if not values:
        return None
    return next(iter(values.values()))


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
        screenshot_dir: str | Path | None = None,
    ):
        self.page = page
        self.app_name = app_name
        self.page_id = page_id
        self.state_observer = state_observer
        self.action_provider = action_provider
        self.screenshot_dir = (
            Path(screenshot_dir) if screenshot_dir is not None else None
        )
        self.last_execution_error: str | None = None
        self.last_structure_observation = None
        self.last_state_facts = None

    async def observe_state(self) -> StateSnapshot:
        if self.state_observer is not None:
            self.last_structure_observation = None
            self.last_state_facts = None
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
        structure = await observe_page_structure(self.page, page_id=page_id)
        facts = facts_from_structure(structure)
        signature = state_signature_from_facts(facts)
        self.last_structure_observation = structure
        self.last_state_facts = facts

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
                "action_label": action.action_label,
                "canonical_action_name": action.canonical_action_name,
                "naming_provenance": action.naming_provenance,
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

    async def go_back(self) -> bool:
        self.last_execution_error = None
        try:
            response = await self.page.go_back(
                wait_until="domcontentloaded",
                timeout=1000,
            )
            if response is None:
                return self._fail_execution("browser_back_unavailable")
            await self.page.wait_for_timeout(100)
            return True
        except Exception as exc:
            return self._fail_execution(f"browser_back_error:{type(exc).__name__}")

    async def reset_to(self, url: str) -> bool:
        self.last_execution_error = None
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=5000)
            await self.page.wait_for_timeout(100)
            return True
        except Exception as exc:
            return self._fail_execution(f"reset_error:{type(exc).__name__}")

    async def capture_screenshot(self, label: str) -> str | None:
        if self.screenshot_dir is None:
            return None
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / f"{label}.png"
        await self.page.screenshot(path=str(path))
        return str(path)


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
            "action_label": action.action_label,
            "canonical_action_name": action.canonical_action_name,
            "naming_provenance": action.naming_provenance,
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
        "action_label": action.get("action_label"),
        "canonical_action_name": action.get("canonical_action_name"),
        "naming_provenance": action.get("naming_provenance"),
        "metadata": dict(action.get("metadata") or {}),
        "explored": bool(action.get("explored", False)),
    }
