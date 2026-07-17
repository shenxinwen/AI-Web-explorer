from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "action"


def _target_slug(description: str, method: str) -> str:
    pattern = rf"^\s*{re.escape(method)}\s+"
    target = re.sub(pattern, "", description, flags=re.IGNORECASE)
    target = re.sub(r"^\s*(the|a|an)\s+", "", target, flags=re.IGNORECASE)
    return _slug(target)


@dataclass(frozen=True)
class StagehandObservedAction:
    description: str
    method: str
    selector: str | None = None
    arguments: list[Any] = field(default_factory=list)
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
    observed_action: StagehandObservedAction | None
    act_result: StagehandActResult | None
    error: str | None = None


class StagehandProvider(Protocol):
    async def observe_next_action(
        self,
        *,
        instruction: str,
        state: StateSnapshot,
    ) -> list[StagehandObservedAction]: ...

    async def act(
        self,
        action: StagehandObservedAction,
    ) -> StagehandActResult: ...


def stagehand_action_to_browser_action(
    action: StagehandObservedAction,
    *,
    index: int,
) -> BrowserAction:
    method = action.method.strip().lower() or "act"
    selector = action.selector
    input_values: dict[str, str] = {}
    if method in {"fill", "type"} and selector and action.arguments:
        input_values[selector] = str(action.arguments[0])
    semantic_id = f"stagehand_{index:03d}_{method}_{_target_slug(action.description, method)}"
    return BrowserAction(
        action_kind=method,
        locator=selector,
        semantic_id=semantic_id,
        input_values=input_values,
        description=action.description,
    )


def stagehand_trace_metadata(trace: StagehandStepTrace) -> dict[str, Any]:
    observed_action = trace.observed_action
    act_result = trace.act_result
    metadata: dict[str, Any] = {
        "action_source": "stagehand",
        "stagehand_instruction": trace.instruction,
        "stagehand_error": trace.error,
    }
    if observed_action is not None:
        metadata.update(
            {
                "stagehand_description": observed_action.description,
                "stagehand_method": observed_action.method,
                "stagehand_selector": observed_action.selector,
                "stagehand_arguments": list(observed_action.arguments),
                "stagehand_observed_action": dict(observed_action.raw),
            }
        )
    if act_result is not None:
        metadata["stagehand_act_result"] = {
            "success": act_result.success,
            "message": act_result.message,
            "action_description": act_result.action_description,
            **dict(act_result.raw),
        }
    return metadata
