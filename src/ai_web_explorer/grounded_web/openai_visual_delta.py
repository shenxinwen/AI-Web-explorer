from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

DEFAULT_OPENAI_VISUAL_DELTA_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_ACTION_OUTCOME_MODEL = "gpt-4o"


def _image_data_url(path: str | Path) -> str:
    image_path = Path(path)
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@dataclass(frozen=True)
class OpenAIVisualDeltaProvider:
    client: Any
    model: str = DEFAULT_OPENAI_VISUAL_DELTA_MODEL
    temperature: float = 0
    max_tokens: int = 700

    def __call__(
        self,
        prompt: str,
        *,
        before_screenshot_path: str | None = None,
        after_screenshot_path: str | None = None,
        current_screenshot_path: str | None = None,
    ) -> str:
        if current_screenshot_path is not None:
            image_paths = [current_screenshot_path]
        elif before_screenshot_path is not None and after_screenshot_path is not None:
            image_paths = [before_screenshot_path, after_screenshot_path]
        else:
            raise ValueError(
                "Provide either current_screenshot_path or both "
                "before_screenshot_path and after_screenshot_path."
            )

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You compare before/after web screenshots for a "
                        "SafeSym-facing web-state graph. Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                    + [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _image_data_url(image_path),
                                "detail": "high",
                            },
                        }
                        for image_path in image_paths
                    ],
                },
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("OpenAI visual delta provider returned an empty response.")
        if isinstance(content, str):
            return content
        return str(content)


def create_openai_visual_delta_provider_from_env(
    *,
    model: str | None = None,
    request_timeout_seconds: float | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIVisualDeltaProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI visual delta.")

    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI

    selected_model = (
        model
        or env.get("OPENAI_VISUAL_DELTA_MODEL")
        or env.get("OPENAI_VISION_MODEL")
        or DEFAULT_OPENAI_VISUAL_DELTA_MODEL
    )
    base_url = env.get("OPENAI_BASE_URL") or None
    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if request_timeout_seconds is not None:
        client_kwargs["timeout"] = request_timeout_seconds
    return OpenAIVisualDeltaProvider(
        client=openai_factory(**client_kwargs),
        model=selected_model,
    )


def create_openai_action_outcome_provider_from_env(
    *,
    model: str | None = None,
    request_timeout_seconds: float | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIVisualDeltaProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI action outcome.")

    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI

    selected_model = (
        model or env.get("OPENAI_ACTION_OUTCOME_MODEL") or DEFAULT_OPENAI_ACTION_OUTCOME_MODEL
    )
    base_url = env.get("OPENAI_BASE_URL") or None
    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if request_timeout_seconds is not None:
        client_kwargs["timeout"] = request_timeout_seconds
    return OpenAIVisualDeltaProvider(
        client=openai_factory(**client_kwargs),
        model=selected_model,
    )


__all__ = [
    "DEFAULT_OPENAI_ACTION_OUTCOME_MODEL",
    "DEFAULT_OPENAI_VISUAL_DELTA_MODEL",
    "OpenAIVisualDeltaProvider",
    "create_openai_action_outcome_provider_from_env",
    "create_openai_visual_delta_provider_from_env",
]
