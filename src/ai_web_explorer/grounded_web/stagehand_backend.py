from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandObservedAction,
    StagehandProvider,
    StagehandStepTrace,
    stagehand_action_to_browser_action,
    stagehand_trace_metadata,
)


class StagehandAutomationBackend:
    app_name: str

    def __init__(
        self,
        *,
        base_backend: AutomationBackend,
        provider: StagehandProvider,
        goal: str,
    ) -> None:
        self.base_backend = base_backend
        self.provider = provider
        self.goal = goal
        self.app_name = base_backend.app_name
        self.last_execution_error: str | None = None
        self.last_execution_metadata: dict[str, Any] = {}
        self._observed_actions_by_id: dict[str, StagehandObservedAction] = {}

    async def observe_state(self) -> StateSnapshot:
        state = await self.base_backend.observe_state()
        if hasattr(self.base_backend, "last_state_facts"):
            self.last_state_facts = getattr(self.base_backend, "last_state_facts")
        return state

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        observed = await self.provider.observe_next_action(
            instruction=self.goal,
            state=state,
        )
        records: list[dict[str, Any]] = []
        for index, stagehand_action in enumerate(observed):
            action = stagehand_action_to_browser_action(
                stagehand_action,
                index=index,
            )
            self._observed_actions_by_id[action.semantic_id] = stagehand_action
            records.append(
                {
                    "semantic_id": action.semantic_id,
                    "description": action.description,
                    "locator": action.locator,
                    "action_kind": action.action_kind,
                    "input_values": dict(action.input_values),
                    "explored": False,
                    "metadata": {
                        "action_source": "stagehand",
                        "stagehand_method": stagehand_action.method,
                    },
                }
            )
        return records

    async def execute(self, action: BrowserAction | dict[str, Any]) -> bool:
        semantic_id = (
            action.semantic_id
            if isinstance(action, BrowserAction)
            else str(action.get("semantic_id", ""))
        )
        stagehand_action = self._observed_actions_by_id.get(semantic_id)
        if stagehand_action is None:
            self.last_execution_error = "stagehand_action_not_found"
            self.last_execution_metadata = {
                "action_source": "stagehand",
                "stagehand_error": self.last_execution_error,
            }
            return False
        try:
            result = await self.provider.act(stagehand_action)
        except Exception as error:
            self.last_execution_error = str(error)
            trace = StagehandStepTrace(
                instruction=self.goal,
                observed_action=stagehand_action,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            return False
        trace = StagehandStepTrace(
            instruction=self.goal,
            observed_action=stagehand_action,
            act_result=result,
        )
        self.last_execution_metadata = stagehand_trace_metadata(trace)
        self.last_execution_error = None if result.success else result.message
        return result.success

    async def capture_screenshot(self, label: str) -> str | None:
        capture = getattr(self.base_backend, "capture_screenshot", None)
        if capture is None:
            return None
        return await capture(label)
