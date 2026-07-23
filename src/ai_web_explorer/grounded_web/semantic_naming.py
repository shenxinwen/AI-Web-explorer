from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot

DEFAULT_DEEPSEEK_SEMANTIC_NAMING_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

SemanticNamingProvider = Callable[["SemanticNamingRequest"], dict[str, Any] | str]
TextCompletionProvider = Callable[[str], str]


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unnamed"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_provider_prefix(model: str) -> str:
    if "/" not in model:
        return model
    provider, name = model.split("/", 1)
    if provider.lower() == "deepseek":
        return name
    return model


def _resolve_deepseek_model(
    *,
    model: str | None,
    env: Mapping[str, str],
) -> str:
    resolved = (
        model
        or env.get("SEMANTIC_NAMING_MODEL")
        or env.get("DEEPSEEK_SEMANTIC_NAMING_MODEL")
        or env.get("STAGEHAND_MODEL")
        or DEFAULT_DEEPSEEK_SEMANTIC_NAMING_MODEL
    )
    return _strip_provider_prefix(resolved)


@dataclass(frozen=True)
class SemanticNamingRequest:
    state: StateSnapshot
    action: BrowserAction | None = None
    goal: str | None = None
    visual_change_summary: str | None = None
    naming_task: str = "state_action"


@dataclass(frozen=True)
class SemanticNamingResult:
    node_label: str | None = None
    state_summary: str | None = None
    action_label: str | None = None
    canonical_action_name: str | None = None
    naming_provenance: dict[str, Any] | None = None


@dataclass(frozen=True)
class OpenAICompatibleSemanticNamingProvider:
    client: Any
    model: str = DEFAULT_DEEPSEEK_SEMANTIC_NAMING_MODEL
    temperature: float = 0
    max_tokens: int = 400

    def __call__(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You produce concise semantic names for web state graph "
                        "nodes and actions. Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("semantic naming provider returned an empty response.")
        if isinstance(content, str):
            return content
        return str(content)


def create_deepseek_semantic_naming_provider_from_env(
    *,
    model: str | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAICompatibleSemanticNamingProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv

    load_dotenv()
    env = os.environ if environ is None else environ
    api_key = env.get("MODEL_API_KEY") or env.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError(
            "MODEL_API_KEY or DEEPSEEK_API_KEY is required for DeepSeek semantic naming."
        )

    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI

    selected_model = _resolve_deepseek_model(model=model, env=env)
    base_url = env.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    return OpenAICompatibleSemanticNamingProvider(
        client=openai_factory(api_key=api_key, base_url=base_url),
        model=selected_model,
    )


def normalize_semantic_naming_response(
    response: dict[str, Any] | str,
    *,
    source: str = "llm_semantic_naming",
) -> SemanticNamingResult:
    data = json.loads(response) if isinstance(response, str) else dict(response)
    confidence = data.get("confidence")
    provenance: dict[str, Any] = {"source": source}
    if confidence is not None:
        provenance["confidence"] = float(confidence)

    node_label = _clean_text(data.get("node_label"))
    canonical_action_name = _clean_text(data.get("canonical_action_name"))
    return SemanticNamingResult(
        node_label=_slug(node_label) if node_label else None,
        state_summary=_clean_text(data.get("state_summary")),
        action_label=_clean_text(data.get("action_label")),
        canonical_action_name=(
            _slug(canonical_action_name) if canonical_action_name else None
        ),
        naming_provenance=provenance,
    )


def prompt_for_semantic_naming(request: SemanticNamingRequest) -> str:
    if request.naming_task == "transition":
        payload: dict[str, Any] = {
            "task": "Name one website business-level transition.",
            "goal": request.goal,
            "visual_change_summary": request.visual_change_summary,
            "runtime_action_id": (
                request.action.semantic_id if request.action is not None else None
            ),
            "constraints": [
                "Return JSON only.",
                "canonical_action_name must be lower_snake_case.",
                "Use a concise verb_object or verb_result style name.",
                "Name the business-level transition, not the UI operation.",
                "Avoid click, fill, type, button, selector, xpath, and website-specific branding.",
                "Do not change runtime identifiers.",
            ],
            "output_schema": {
                "action_label": "short human-readable phrase",
                "canonical_action_name": "lower_snake_case business transition name",
                "confidence": "number from 0 to 1",
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    payload: dict[str, Any] = {
        "goal": request.goal,
        "state": {
            "page_id": request.state.page_id,
            "url": request.state.url,
            "title": request.state.title,
            "signature": dict(request.state.signature),
        },
        "action": None,
        "constraints": [
            "Do not invent selectors or change runtime identifiers.",
            "node_label and canonical_action_name must be short snake_case names.",
            "state_summary and action_label should be concise human-readable text.",
        ],
        "output_schema": {
            "node_label": "snake_case node label",
            "state_summary": "short sentence",
            "action_label": "short phrase, optional when no action is provided",
            "canonical_action_name": "snake_case action name, optional",
            "confidence": "number from 0 to 1",
        },
    }
    if request.action is not None:
        payload["action"] = {
            "semantic_id": request.action.semantic_id,
            "action_kind": request.action.action_kind,
            "locator": request.action.locator,
            "description": request.action.description,
            "input_values": dict(request.action.input_values),
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def call_semantic_naming_provider(
    request: SemanticNamingRequest,
    *,
    provider: TextCompletionProvider,
) -> dict[str, Any] | str:
    return provider(prompt_for_semantic_naming(request))


def semantic_naming_provider_from_text_provider(
    provider: TextCompletionProvider,
) -> SemanticNamingProvider:
    return lambda request: call_semantic_naming_provider(request, provider=provider)


def apply_semantic_naming(
    request: SemanticNamingRequest,
    *,
    provider: SemanticNamingProvider,
) -> tuple[dict[str, Any], BrowserAction | None]:
    try:
        result = normalize_semantic_naming_response(provider(request))
    except Exception as error:
        provenance = {
            "source": "semantic_naming_failed",
            "error": str(error),
        }
        return {"naming_provenance": provenance}, request.action

    node_fields = {
        "node_label": result.node_label,
        "state_summary": result.state_summary,
        "naming_provenance": result.naming_provenance,
    }
    if request.action is None:
        return node_fields, None

    renamed_action = replace(
        request.action,
        action_label=result.action_label,
        canonical_action_name=result.canonical_action_name,
        naming_provenance=result.naming_provenance,
    )
    return node_fields, renamed_action


def apply_transition_naming(
    *,
    action: BrowserAction,
    goal: str | None,
    visual_change_summary: str,
    provider: SemanticNamingProvider,
) -> BrowserAction:
    request = SemanticNamingRequest(
        goal=goal,
        state=StateSnapshot(
            page_id="transition",
            url="",
            title="",
            signature={},
        ),
        action=action,
        visual_change_summary=visual_change_summary,
        naming_task="transition",
    )
    try:
        result = normalize_semantic_naming_response(
            provider(request),
            source="llm_transition_naming",
        )
    except Exception as error:
        return replace(
            action,
            naming_provenance={
                "source": "transition_naming_failed",
                "error": str(error),
            },
        )
    return replace(
        action,
        action_label=result.action_label or action.action_label,
        canonical_action_name=result.canonical_action_name
        or action.canonical_action_name,
        naming_provenance=result.naming_provenance,
    )


__all__ = [
    "DEFAULT_DEEPSEEK_SEMANTIC_NAMING_MODEL",
    "OpenAICompatibleSemanticNamingProvider",
    "SemanticNamingProvider",
    "SemanticNamingRequest",
    "SemanticNamingResult",
    "apply_semantic_naming",
    "apply_transition_naming",
    "call_semantic_naming_provider",
    "create_deepseek_semantic_naming_provider_from_env",
    "normalize_semantic_naming_response",
    "prompt_for_semantic_naming",
    "semantic_naming_provider_from_text_provider",
]
