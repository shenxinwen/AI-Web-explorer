from __future__ import annotations

import os
from typing import Any, Callable, Mapping

from vera.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return dict(value.to_dict(exclude_none=True))
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(exclude_none=True))
    if hasattr(value, "__dict__"):
        return {
            key: _to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {"value": value}


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if (
        hasattr(value, "to_dict")
        or hasattr(value, "model_dump")
        or hasattr(value, "__dict__")
    ):
        return _to_dict(value)
    return value


class StagehandSdkProvider:
    def __init__(
        self,
        *,
        session: Any,
        page: Any | None = None,
        agent_model_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.page = page
        self._agent_model_config = (
            dict(agent_model_config) if agent_model_config is not None else None
        )

    async def observe_action(
        self,
        instruction: str,
    ) -> list[StagehandObservedAction]:
        observe_args = {"instruction": instruction}
        if self.page is not None:
            observe_args["page"] = self.page
        response = await self.session.observe(**observe_args)
        raw_data = _to_dict(getattr(response, "data", response))
        raw_items = raw_data.get("result") or []
        if not isinstance(raw_items, list):
            raw_items = [raw_items]
        return [
            StagehandObservedAction(
                description=str(item.get("description", "")),
                selector=str(item.get("selector", "")),
                method=str(item.get("method", "")),
                arguments=tuple(str(value) for value in item.get("arguments") or []),
                raw=dict(item),
            )
            for item in raw_items
            if isinstance(item, dict)
        ]

    async def act_action(
        self,
        action: StagehandObservedAction,
    ) -> StagehandActResult:
        act_args: dict[str, Any] = {
            "input": {
                "description": action.description,
                "selector": action.selector,
                "method": action.method,
                "arguments": list(action.arguments),
            }
        }
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

    async def act_instruction(self, instruction: str) -> StagehandActResult:
        act_args = {"input": instruction}
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

    async def execute_instruction(
        self,
        instruction: str,
        *,
        max_steps: int = 5,
    ) -> StagehandActResult:
        agent_config: dict[str, Any] = {"mode": "dom"}
        if self._agent_model_config is not None:
            agent_config["model"] = dict(self._agent_model_config)
        execute_args = {
            "agent_config": agent_config,
            "execute_options": {
                "instruction": instruction,
                "max_steps": max_steps,
                "use_search": False,
            },
        }
        if self.page is not None:
            execute_args["page"] = self.page
        response = await self.session.execute(**execute_args)
        raw_data = _to_dict(getattr(response, "data", response))
        result_data = _to_dict(raw_data.get("result"))
        message = result_data.get("message")
        return StagehandActResult(
            success=bool(result_data.get("success", raw_data.get("success", True))),
            message=message,
            action_description=str(message) if message is not None else None,
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
_LOCAL_NO_PROXY_HOSTS = ("localhost", "127.0.0.1", "::1")
DEFAULT_STAGEHAND_MODEL = "openai/gpt-4o"


def _resolve_model_name(
    model_name: str | None,
    *,
    env: Mapping[str, str],
) -> str:
    return model_name or env.get("STAGEHAND_MODEL") or DEFAULT_STAGEHAND_MODEL


def _resolve_model_api_key(*, model_name: str, env: Mapping[str, str]) -> str | None:
    explicit_key = env.get("MODEL_API_KEY")
    if explicit_key:
        return explicit_key
    provider = model_name.split("/", 1)[0].lower()
    provider_key_env = _PROVIDER_KEY_ENV_BY_MODEL_PREFIX.get(provider)
    if provider_key_env:
        return env.get(provider_key_env)
    return None


def _resolve_agent_model_config(
    *,
    model_name: str,
    model_api_key: str | None,
    env: Mapping[str, str],
) -> dict[str, Any] | None:
    base_url = (env.get("STAGEHAND_MODEL_BASE_URL") or "").strip()
    user_agent = (env.get("STAGEHAND_MODEL_USER_AGENT") or "").strip()
    if not base_url and not user_agent:
        return None
    if user_agent and not base_url:
        raise ValueError(
            "STAGEHAND_MODEL_USER_AGENT requires STAGEHAND_MODEL_BASE_URL."
        )
    if not base_url.lower().startswith(("http://", "https://")):
        raise ValueError(
            "STAGEHAND_MODEL_BASE_URL must start with http:// or https://."
        )
    if not model_name.startswith("openai/"):
        raise ValueError(
            "STAGEHAND_MODEL must start with openai/ when using "
            "STAGEHAND_MODEL_BASE_URL."
        )
    if not model_api_key:
        raise ValueError(
            "MODEL_API_KEY or a provider-specific model key is required when "
            "using STAGEHAND_MODEL_BASE_URL."
        )
    config: dict[str, Any] = {
        "model_name": model_name,
        "provider": "openai",
        "api_key": model_api_key,
        "base_url": base_url,
    }
    if user_agent:
        config["headers"] = {"User-Agent": user_agent}
    return config


def _merge_no_proxy(value: str | None) -> str:
    existing = [item.strip() for item in (value or "").split(",") if item.strip()]
    merged = list(existing)
    existing_lower = {item.lower() for item in existing}
    for host in _LOCAL_NO_PROXY_HOSTS:
        if host.lower() not in existing_lower:
            merged.append(host)
    return ",".join(merged)


def _ensure_local_no_proxy() -> None:
    os.environ["NO_PROXY"] = _merge_no_proxy(os.environ.get("NO_PROXY"))
    os.environ["no_proxy"] = _merge_no_proxy(os.environ.get("no_proxy"))


def _resolve_local_ready_timeout(env: Mapping[str, str]) -> float | None:
    raw_timeout = env.get("STAGEHAND_LOCAL_READY_TIMEOUT_S")
    if raw_timeout is None:
        return None
    try:
        return float(raw_timeout)
    except ValueError as error:
        raise ValueError("STAGEHAND_LOCAL_READY_TIMEOUT_S must be a number.") from error


async def create_async_stagehand_provider_from_env(
    *,
    model_name: str | None = None,
    page: Any | None = None,
    local_cdp_url: str | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> StagehandSdkProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()
    env = os.environ if environ is None else environ

    try:
        from stagehand import AsyncStagehand
    except Exception as error:
        raise ValueError(
            "stagehand Python SDK is required for real Stagehand-backed runs."
        ) from error

    resolved_model_name = _resolve_model_name(model_name, env=env)
    server = env.get("STAGEHAND_SERVER", "local").lower()
    if server not in {"local", "remote"}:
        raise ValueError("STAGEHAND_SERVER must be either 'local' or 'remote'.")
    if server == "local":
        _ensure_local_no_proxy()

    model_api_key = _resolve_model_api_key(
        model_name=resolved_model_name,
        env=env,
    )
    agent_model_config = _resolve_agent_model_config(
        model_name=resolved_model_name,
        model_api_key=model_api_key,
        env=env,
    )
    client_options: dict[str, Any] = {
        "model_api_key": model_api_key,
        "server": server,
    }
    stagehand_api_url = env.get("STAGEHAND_API_URL")
    if stagehand_api_url:
        client_options["base_url"] = stagehand_api_url
    local_ready_timeout = _resolve_local_ready_timeout(env)
    if local_ready_timeout is not None:
        client_options["local_ready_timeout_s"] = local_ready_timeout
    client = AsyncStagehand(**client_options)
    session_options: dict[str, Any] = {"model_name": resolved_model_name}
    if server == "local":
        browser_options: dict[str, Any] = {"type": "local"}
        if local_cdp_url:
            browser_options["cdp_url"] = local_cdp_url
        session_options["browser"] = browser_options
    session = await client.sessions.start(**session_options)
    return StagehandSdkProvider(
        session=session,
        page=page if server == "local" else None,
        agent_model_config=agent_model_config,
    )
