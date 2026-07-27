from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Literal

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
        execution_mode: Literal["observed_action", "business_milestone"] = (
            "observed_action"
        ),
        business_milestone_max_steps: int = 5,
        goal_provider: Callable[[int], str] | None = None,
        business_step_metadata_provider: Callable[[int], dict[str, Any]]
        | None = None,
    ) -> None:
        self.base_backend = base_backend
        self.provider = provider
        self.goal = goal
        self.execution_mode = execution_mode
        self.business_milestone_max_steps = business_milestone_max_steps
        self.goal_provider = goal_provider
        self.business_step_metadata_provider = business_step_metadata_provider
        self.app_name = base_backend.app_name
        self.last_execution_error: str | None = None
        self.last_execution_metadata: dict[str, Any] = {}
        self._observed_actions_by_id: dict[str, StagehandObservedAction] = {}
        self._business_goals_by_id: dict[str, str] = {}
        self._business_metadata_by_id: dict[str, dict[str, Any]] = {}
        self._business_milestone_counter = 0

    async def observe_state(self) -> StateSnapshot:
        state = await self.base_backend.observe_state()
        if hasattr(self.base_backend, "last_state_facts"):
            self.last_state_facts = getattr(self.base_backend, "last_state_facts")
        return state

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        if self.execution_mode == "business_milestone":
            self._business_milestone_counter += 1
            step_number = self._business_milestone_counter
            semantic_id = f"stagehand_business_milestone_{step_number:03d}"
            goal = (
                self.goal_provider(step_number)
                if self.goal_provider is not None
                else self.goal
            )
            step_metadata = (
                dict(self.business_step_metadata_provider(step_number))
                if self.business_step_metadata_provider is not None
                else {}
            )
            self._business_goals_by_id[semantic_id] = goal
            self._business_metadata_by_id[semantic_id] = step_metadata
            experiment_step_id = step_metadata.get("experiment_step_id")
            canonical_action_name = str(
                experiment_step_id or "advance_business_milestone"
            )
            action_label = (
                canonical_action_name.replace("_", " ")
                if experiment_step_id
                else "Advance one business milestone"
            )
            return [
                {
                    "semantic_id": semantic_id,
                    "description": goal,
                    "locator": None,
                    "action_kind": "business_intent",
                    "input_values": {},
                    "action_label": action_label,
                    "canonical_action_name": canonical_action_name,
                    "naming_provenance": {"source": "stagehand_business_milestone"},
                    "explored": False,
                    "metadata": {
                        "action_source": "stagehand",
                        "stagehand_execution_mode": "business_milestone",
                        **step_metadata,
                    },
                }
            ]

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
                    "action_label": action.action_label,
                    "canonical_action_name": action.canonical_action_name,
                    "naming_provenance": action.naming_provenance,
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
        if self.execution_mode == "business_milestone" and semantic_id.startswith(
            "stagehand_business_milestone_"
        ):
            goal = self._business_goals_by_id.get(semantic_id, self.goal)
            metadata = self._business_metadata_by_id.get(semantic_id, {})
            return await self._execute_business_milestone(goal, metadata)

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

    async def _execute_business_milestone(
        self,
        goal: str,
        step_metadata: dict[str, Any],
    ) -> bool:
        try:
            execute_instruction = getattr(self.provider, "execute_instruction", None)
            if execute_instruction is not None:
                result = await execute_instruction(
                    goal,
                    max_steps=self.business_milestone_max_steps,
                )
            else:
                act_instruction = getattr(self.provider, "act_instruction")
                result = await act_instruction(goal)
        except Exception as error:
            self.last_execution_error = str(error)
            trace = StagehandStepTrace(
                instruction=goal,
                observed_action=None,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            self.last_execution_metadata["stagehand_execution_mode"] = (
                "business_milestone"
            )
            self.last_execution_metadata.update(step_metadata)
            return False
        trace = StagehandStepTrace(
            instruction=goal,
            observed_action=None,
            act_result=result,
        )
        self.last_execution_metadata = stagehand_trace_metadata(trace)
        self.last_execution_metadata["stagehand_execution_mode"] = "business_milestone"
        self.last_execution_metadata.update(step_metadata)
        self.last_execution_error = None if result.success else result.message
        return result.success

    async def capture_screenshot(self, label: str) -> str | None:
        capture = getattr(self.base_backend, "capture_screenshot", None)
        if capture is None:
            return None
        return await capture(label)
