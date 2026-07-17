from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict(exclude_none=True))
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(exclude_none=True))
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {"value": value}


def _result_items(response: Any) -> list[Any]:
    data = getattr(response, "data", None)
    result = getattr(data, "result", None)
    if result is None and isinstance(data, dict):
        result = data.get("result")
    if result is None:
        return []
    return list(result if isinstance(result, list) else [result])


class StagehandSdkProvider:
    def __init__(self, *, session: Any) -> None:
        self.session = session

    async def observe_next_action(self, *, instruction, state):
        response = await self.session.observe(instruction=instruction)
        actions = []
        for item in _result_items(response):
            data = _to_dict(item)
            actions.append(
                StagehandObservedAction(
                    description=str(data.get("description", "")),
                    method=str(data.get("method") or data.get("action") or "act"),
                    selector=data.get("selector"),
                    arguments=list(data.get("arguments") or []),
                    raw=data,
                )
            )
        return actions

    async def act(self, action: StagehandObservedAction) -> StagehandActResult:
        action_input = {
            "description": action.description,
            "method": action.method,
            "selector": action.selector,
            "arguments": list(action.arguments),
        }
        response = await self.session.act(input=action_input)
        raw_data = _to_dict(getattr(response, "data", response))
        result_data = _to_dict(raw_data.get("result"))
        return StagehandActResult(
            success=bool(result_data.get("success", raw_data.get("success", True))),
            message=result_data.get("message"),
            action_description=(
                result_data.get("actionDescription")
                or result_data.get("action_description")
            ),
            raw=raw_data,
        )


async def create_async_stagehand_provider_from_env(
    *,
    model_name: str | None = None,
) -> StagehandSdkProvider:
    try:
        from stagehand import AsyncStagehand
    except Exception as error:
        raise ValueError(
            "stagehand Python SDK is required for real Stagehand-backed runs."
        ) from error

    client = AsyncStagehand()
    session_options = {}
    if model_name is not None:
        session_options["model_name"] = model_name
    session = await client.sessions.create(**session_options)
    return StagehandSdkProvider(session=session)
