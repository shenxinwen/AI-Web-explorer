from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

DEFAULT_OPENAI_ACTION_SELECTOR_MODEL = "gpt-4o"


@dataclass(frozen=True)
class OpenAIChatSelectionProvider:
    client: Any
    model: str = DEFAULT_OPENAI_ACTION_SELECTOR_MODEL
    temperature: float = 0
    max_tokens: int = 300

    def __call__(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a web task action selector. Return JSON only. "
                        "Choose exactly one provided action id."
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
            raise ValueError("OpenAI action selector returned an empty response.")
        if isinstance(content, str):
            return content
        return str(content)


def create_openai_chat_selection_provider_from_env(
    *,
    model: str | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIChatSelectionProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI selector smoke.")

    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI

    selected_model = (
        model
        or env.get("OPENAI_ACTION_SELECTOR_MODEL")
        or DEFAULT_OPENAI_ACTION_SELECTOR_MODEL
    )
    base_url = env.get("OPENAI_BASE_URL") or None
    return OpenAIChatSelectionProvider(
        client=openai_factory(api_key=api_key, base_url=base_url),
        model=selected_model,
    )
