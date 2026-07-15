from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.playwright_backend import (
    WebKobePlaywrightAdapter as _GroundedWebKobePlaywrightAdapter,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_adapter import static_actions_for_state
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state


def _saucedemo_action_records(state: StateSnapshot) -> list[dict[str, Any]]:
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


class WebKobePlaywrightAdapter(_GroundedWebKobePlaywrightAdapter):
    """Compatibility wrapper with SauceDemo profile support.

    Generic code should import `ai_web_explorer.grounded_web.playwright_backend`.
    This wrapper keeps existing SafeSym/SauceDemo callers working.
    """

    def __init__(
        self,
        page,
        *,
        app_name: str = "web",
        page_id: str | None = None,
        state_observer=None,
        action_provider=None,
    ):
        if app_name == "saucedemo" and state_observer is None:
            state_observer = observe_saucedemo_state
        if app_name == "saucedemo" and action_provider is None:
            action_provider = _saucedemo_action_records
        super().__init__(
            page,
            app_name=app_name,
            page_id=page_id,
            state_observer=state_observer,
            action_provider=action_provider,
        )


__all__ = ["WebKobePlaywrightAdapter"]
