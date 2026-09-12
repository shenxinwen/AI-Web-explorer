from __future__ import annotations

import asyncio
from typing import Any
from typing import Literal

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandProvider,
    StagehandObservedAction,
    StagehandStepTrace,
    stagehand_trace_metadata,
)


def _agent_business_instruction(semantic_id: str, atomic_instruction: str) -> str:
    return " ".join(
        [
            f"Execute only this selected business action: {semantic_id}.",
            atomic_instruction,
            "Stop after the first visible completion or clear failure.",
            "Do not continue to the next business goal.",
        ]
    )


def _execution_policy(action: BrowserAction | dict[str, Any]) -> str:
    value = (
        action.execution_policy
        if isinstance(action, BrowserAction)
        else action.get("execution_policy")
    )
    return "composite" if str(value or "").strip().lower() == "composite" else (
        "single_instance"
    )


def _instruction_with_execution_instance(
    instruction: str,
    execution_instance: str | None,
) -> str:
    instance = str(execution_instance or "").strip()
    if not instance or instance in instruction:
        return instruction
    return f"{instruction.rstrip()} Execute this specific instance: {instance}."


class StagehandAutomationBackend:
    app_name: str

    def __init__(
        self,
        *,
        base_backend: AutomationBackend,
        provider: StagehandProvider,
        goal: str,
        execution_mode: Literal[
            "observed_action", "observe_act"
        ] = (
            "observed_action"
        ),
        action_timeout_seconds: float | None = None,
        site_input_context: str | None = None,
        post_action_settle_ms: int | None = None,
    ) -> None:
        if execution_mode not in {"observed_action", "observe_act"}:
            raise ValueError(
                f"unsupported_stagehand_execution_mode: {execution_mode}"
            )
        self.base_backend = base_backend
        self.provider = provider
        self.goal = goal
        self.execution_mode = execution_mode
        self.action_timeout_seconds = action_timeout_seconds
        self.site_input_context = site_input_context
        self.post_action_settle_ms = post_action_settle_ms
        self.app_name = base_backend.app_name
        self.last_execution_error: str | None = None
        self.last_execution_metadata: dict[str, Any] = {}
        self._exploration_context_prompt: str | None = None

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
        if action_kind == "business_intent":
            instruction = (
                action.description
                if isinstance(action, BrowserAction)
                else str(action.get("description") or semantic_id)
            )
            execution_policy = _execution_policy(action)
            execution_instance = (
                action.execution_instance
                if isinstance(action, BrowserAction)
                else action.get("execution_instance")
            )
            instruction = _instruction_with_execution_instance(
                instruction or semantic_id,
                execution_instance,
            )
            if self.execution_mode != "observe_act":
                instruction = _agent_business_instruction(
                    semantic_id,
                    instruction or semantic_id,
                )
            return await self._execute_business_intent(
                instruction or semantic_id,
                {
                    "business_action_id": semantic_id,
                    "execution_policy": execution_policy,
                },
                execution_policy=execution_policy,
            )

        self.last_execution_error = "stagehand_business_intent_required"
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_error": self.last_execution_error,
            "stagehand_semantic_id": semantic_id,
        }
        return False

    async def execute_replay_action(
        self,
        action: BrowserAction | dict[str, Any],
    ) -> bool:
        return await self.execute(action)

    async def _execute_business_intent(
        self,
        instruction: str,
        step_metadata: dict[str, Any],
        *,
        execution_policy: str = "single_instance",
    ) -> bool:
        return await self._execute_instruction(
            instruction,
            execution_mode="business_intent",
            step_metadata=step_metadata,
            execution_policy=execution_policy,
        )

    async def _execute_instruction(
        self,
        instruction: str,
        *,
        execution_mode: str,
        step_metadata: dict[str, Any],
        execution_policy: str = "single_instance",
    ) -> bool:
        if self.site_input_context:
            instruction = "\n\n".join(
                [
                    instruction,
                    f"Site-specific test input:\n{self.site_input_context}",
                ]
            )
        if (
            self.execution_mode != "observe_act"
            and self._exploration_context_prompt
        ):
            instruction = "\n\n".join([instruction, self._exploration_context_prompt])
        observed_action: StagehandObservedAction | None = None
        observed_actions: list[StagehandObservedAction] = []
        trace_execution_mode = execution_mode
        try:
            if self.execution_mode == "observe_act":
                async def observe_then_act():
                    actions = await self.provider.observe_action(instruction)
                    if not actions:
                        raise ValueError("stagehand_observe_returned_no_actions")
                    actions_to_execute = (
                        actions
                        if execution_policy == "composite"
                        else actions[:1]
                    )
                    results: list[StagehandActResult] = []
                    for action in actions_to_execute:
                        result = await self.provider.act_action(action)
                        results.append(result)
                        if not result.success:
                            break
                    aggregate_result = StagehandActResult(
                        success=all(result.success for result in results),
                        message=next(
                            (
                                result.message
                                for result in reversed(results)
                                if result.message
                            ),
                            None,
                        ),
                        action_description=instruction,
                        raw={
                            "atomic_steps": [
                                {
                                    "observed_action": {
                                        "description": action.description,
                                        "selector": action.selector,
                                        "method": action.method,
                                        "arguments": list(action.arguments),
                                        **dict(action.raw),
                                    },
                                    "act_result": {
                                        "success": result.success,
                                        "message": result.message,
                                        "action_description": result.action_description,
                                        **dict(result.raw),
                                    },
                                }
                                for action, result in zip(
                                    actions_to_execute, results
                                )
                            ]
                        },
                    )
                    return actions, aggregate_result

                invocation = observe_then_act()
                trace_execution_mode = "observe_act"
            else:
                execute_instruction = getattr(
                    self.provider, "execute_instruction", None
                )
                if execute_instruction is not None:
                    invocation = execute_instruction(
                        instruction,
                        max_steps=5,
                    )
                else:
                    act_instruction = getattr(self.provider, "act_instruction")
                    invocation = act_instruction(instruction)
            if self.action_timeout_seconds is None:
                invocation_result = await invocation
            else:
                invocation_result = await asyncio.wait_for(
                    invocation,
                    timeout=self.action_timeout_seconds,
                )
            if self.execution_mode == "observe_act":
                observed_actions, result = invocation_result
            else:
                result = invocation_result
        except asyncio.TimeoutError:
            self.last_execution_error = "stagehand_action_timeout"
            trace = StagehandStepTrace(
                instruction=instruction,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            self.last_execution_metadata["stagehand_execution_mode"] = (
                trace_execution_mode
            )
            self.last_execution_metadata.update(step_metadata)
            return False
        except Exception as error:
            self.last_execution_error = str(error)
            trace = StagehandStepTrace(
                instruction=instruction,
                act_result=None,
                error=self.last_execution_error,
            )
            self.last_execution_metadata = stagehand_trace_metadata(trace)
            self.last_execution_metadata["stagehand_execution_mode"] = (
                trace_execution_mode
            )
            self.last_execution_metadata.update(step_metadata)
            return False
        if observed_actions:
            observed_action = observed_actions[0]
        trace = StagehandStepTrace(
            instruction=instruction,
            act_result=result,
            observed_action=observed_action,
        )
        self.last_execution_metadata = stagehand_trace_metadata(trace)
        if observed_actions:
            self.last_execution_metadata["stagehand_observed_actions"] = [
                {
                    "description": action.description,
                    "selector": action.selector,
                    "method": action.method,
                    "arguments": list(action.arguments),
                    **dict(action.raw),
                }
                for action in observed_actions
            ]
        self.last_execution_metadata["stagehand_execution_mode"] = (
            trace_execution_mode
        )
        self.last_execution_metadata["execution_policy"] = execution_policy
        self.last_execution_metadata.update(step_metadata)
        if result.success and self.post_action_settle_ms is not None:
            settle = getattr(self.base_backend, "settle_after_external_action", None)
            if settle is not None:
                await settle(self.post_action_settle_ms)
        self.last_execution_error = None if result.success else result.message
        return result.success

    async def capture_screenshot(self, label: str) -> str | None:
        capture = getattr(self.base_backend, "capture_screenshot", None)
        if capture is None:
            return None
        return await capture(label)
