from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class StagehandObservedAction:
    description: str
    selector: str
    method: str
    arguments: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StagehandActResult:
    success: bool
    message: str | None = None
    action_description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StagehandStepTrace:
    instruction: str
    act_result: StagehandActResult | None
    observed_action: StagehandObservedAction | None = None
    error: str | None = None


class StagehandProvider(Protocol):
    async def observe_action(
        self,
        instruction: str,
    ) -> list[StagehandObservedAction]: ...

    async def act_action(
        self,
        action: StagehandObservedAction,
    ) -> StagehandActResult: ...

    async def act_instruction(self, instruction: str) -> StagehandActResult: ...

    async def execute_instruction(
        self,
        instruction: str,
        *,
        max_steps: int = 5,
    ) -> StagehandActResult: ...


def stagehand_trace_metadata(trace: StagehandStepTrace) -> dict[str, Any]:
    act_result = trace.act_result
    observed_action = trace.observed_action
    metadata: dict[str, Any] = {
        "action_source": "stagehand",
        "stagehand_instruction": trace.instruction,
        "stagehand_error": trace.error,
        "stagehand_observed_action": (
            {
                "description": observed_action.description,
                "selector": observed_action.selector,
                "method": observed_action.method,
                "arguments": list(observed_action.arguments),
                **dict(observed_action.raw),
            }
            if observed_action is not None
            else None
        ),
    }
    if act_result is not None:
        metadata["stagehand_act_result"] = {
            "success": act_result.success,
            "message": act_result.message,
            "action_description": act_result.action_description,
            **dict(act_result.raw),
        }
    return metadata
