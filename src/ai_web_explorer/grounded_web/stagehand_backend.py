from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Literal

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandProvider,
    StagehandStepTrace,
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
        business_step_metadata_provider: Callable[[int], dict[str, Any]] | None = None,
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
        self._exploration_context_prompt: str | None = None
        self._business_goals_by_id: dict[str, str] = {}
        self._business_metadata_by_id: dict[str, dict[str, Any]] = {}
        self._business_milestone_counter = 0

    def set_exploration_context(self, prompt_block: str | None) -> None:
        self._exploration_context_prompt = prompt_block

    async def observe_state(self) -> StateSnapshot:
        state = await self.base_backend.observe_state()
        if hasattr(self.base_backend, "last_state_facts"):
            self.last_state_facts = getattr(self.base_backend, "last_state_facts")
        return state

    async def go_back(self) -> bool:
        go_back = getattr(self.base_backend, "go_back", None)
        if go_back is None:
            self.last_execution_error = "browser_back_unavailable"
            self.last_execution_metadata = {
                "action_source": "stagehand",
                "stagehand_execution_mode": "browser_back",
                "stagehand_error": self.last_execution_error,
            }
            return False
        success = await go_back()
        self.last_execution_error = getattr(
            self.base_backend,
            "last_execution_error",
            None,
        )
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_execution_mode": "browser_back",
            "backend_reported_success": success,
        }
        return success

    async def reset_to(self, url: str) -> bool:
        reset_to = getattr(self.base_backend, "reset_to", None)
        if reset_to is None:
            self.last_execution_error = "reset_unavailable"
            success = False
        else:
            success = await reset_to(url)
            self.last_execution_error = getattr(
                self.base_backend,
                "last_execution_error",
                None,
            )
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_execution_mode": "entry_reset",
            "backend_reported_success": success,
        }
        return success

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

        if self.execution_mode == "observed_action":
            return await self.base_backend.list_interactables(state)

    async def execute(self, action: BrowserAction | dict[str, Any]) -> bool:
        semantic_id = (
            action.semantic_id
            if isinstance(action, BrowserAction)
            else str(action.get("semantic_id", ""))
        )
        action_kind = (
            action.action_kind
            if isinstance(action, BrowserAction)
            else str(action.get("action_kind", ""))
        )
        if self.execution_mode == "business_milestone" and semantic_id.startswith(
            "stagehand_business_milestone_"
        ):
            goal = self._business_goals_by_id.get(semantic_id, self.goal)
            metadata = self._business_metadata_by_id.get(semantic_id, {})
            return await self._execute_business_milestone(goal, metadata)
        if action_kind == "business_intent":
            instruction = (
                action.description
                if isinstance(action, BrowserAction)
                else str(action.get("description") or semantic_id)
            )
            return await self._execute_business_intent(
                instruction or semantic_id,
                {"business_action_id": semantic_id},
            )

        self.last_execution_error = "stagehand_business_intent_required"
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_error": self.last_execution_error,
            "stagehand_semantic_id": semantic_id,
        }
        return False

    async def _execute_business_intent(
        self,
        instruction: str,
        step_metadata: dict[str, Any],
    ) -> bool:
        return await self._execute_instruction(
            instruction,
            execution_mode="business_intent",
            step_metadata=step_metadata,
        )

    async def _execute_business_milestone(
        self,
        goal: str,
        step_metadata: dict[str, Any],
    ) -> bool:
        return await self._execute_instruction(
            goal,
            execution_mode="business_milestone",
            step_metadata=step_metadata,
        )

    async def _execute_instruction(
        self,
        instruction: str,
        *,
        execution_mode: str,
        step_metadata: dict[str, Any],
    ) -> bool:
        if self._exploration_context_prompt:
            instruction = "\n\n".join([instruction, self._exploration_context_prompt])
        try:
            execute_instruction = getattr(self.provider, "execute_instruction", None)
            if execute_instruction is not None:
                result = await execute_instruction(
                    instruction,
                    max_steps=self.business_milestone_max_steps,
                )
            else:
                act_instruction = getattr(self.provider, "act_instruction")
                result = await act_instruction(instruction)
        except Exception as error:
            self.last_execution_error = str(error)
            trace = StagehandStepTrace(
                instruction=instruction,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            self.last_execution_metadata["stagehand_execution_mode"] = execution_mode
            self.last_execution_metadata.update(step_metadata)
            return False
        trace = StagehandStepTrace(
            instruction=instruction,
            act_result=result,
        )
        self.last_execution_metadata = stagehand_trace_metadata(trace)
        self.last_execution_metadata["stagehand_execution_mode"] = execution_mode
        self.last_execution_metadata.update(step_metadata)
        self.last_execution_error = None if result.success else result.message
        return result.success

    async def capture_screenshot(self, label: str) -> str | None:
        capture = getattr(self.base_backend, "capture_screenshot", None)
        if capture is None:
            return None
        return await capture(label)
