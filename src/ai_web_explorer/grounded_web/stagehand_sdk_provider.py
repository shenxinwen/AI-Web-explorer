from __future__ import annotations

import os
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
    def __init__(self, *, session: Any, page: Any | None = None) -> None:
        self.session = session
        self.page = page

    async def observe_next_action(self, *, instruction, state):
        observe_args = {"instruction": instruction}
        if self.page is not None:
            observe_args["page"] = self.page
        response = await self.session.observe(**observe_args)
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
        act_args = {"input": action_input}
        if self.page is not None:
            act_args["page"] = self.page
        response = await self.session.act(**act_args)
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


_PROVIDER_KEY_ENV_BY_MODEL_PREFIX = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "openai": "OPENAI_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "together": "TOGETHER_API_KEY",
    "xai": "XAI_API_KEY",
}


def _resolve_model_name(model_name: str | None) -> str:
    resolved_model_name = model_name or os.environ.get("STAGEHAND_MODEL")
    if not resolved_model_name:
        raise ValueError(
            "Stagehand model is required. Pass --model or set STAGEHAND_MODEL."
        )
    return resolved_model_name


def _resolve_model_api_key(*, model_name: str) -> str | None:
    explicit_key = os.environ.get("MODEL_API_KEY")
    if explicit_key:
        return explicit_key
    provider = model_name.split("/", 1)[0].lower()
    provider_key_env = _PROVIDER_KEY_ENV_BY_MODEL_PREFIX.get(provider)
    if provider_key_env:
        return os.environ.get(provider_key_env)
    return None


async def create_async_stagehand_provider_from_env(
    *,
    model_name: str | None = None,
    page: Any | None = None,
) -> StagehandSdkProvider:
    try:
        from stagehand import AsyncStagehand
    except Exception as error:
        raise ValueError(
            "stagehand Python SDK is required for real Stagehand-backed runs."
        ) from error

    resolved_model_name = _resolve_model_name(model_name)
    server = os.environ.get("STAGEHAND_SERVER", "local").lower()
    if server not in {"local", "remote"}:
        raise ValueError("STAGEHAND_SERVER must be either 'local' or 'remote'.")

    client = AsyncStagehand(
        model_api_key=_resolve_model_api_key(model_name=resolved_model_name),
        server=server,
    )
    session_options: dict[str, Any] = {"model_name": resolved_model_name}
    if server == "local":
        session_options["browser"] = {"type": "local"}
    session = await client.sessions.start(**session_options)
    return StagehandSdkProvider(
        session=session,
        page=page if server == "local" else None,
    )
