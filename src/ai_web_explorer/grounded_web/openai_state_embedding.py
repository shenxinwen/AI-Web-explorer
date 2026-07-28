from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

DEFAULT_OPENAI_STATE_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(frozen=True)
class OpenAIStateEmbeddingProvider:
    client: Any
    model: str = DEFAULT_OPENAI_STATE_EMBEDDING_MODEL

    def __call__(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return [float(value) for value in response.data[0].embedding]


def create_openai_state_embedding_provider_from_env(
    *,
    model: str | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIStateEmbeddingProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI state embeddings.")
    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI
    base_url = env.get("OPENAI_BASE_URL") or None
    selected_model = (
        model
        or env.get("OPENAI_STATE_EMBEDDING_MODEL")
        or DEFAULT_OPENAI_STATE_EMBEDDING_MODEL
    )
    return OpenAIStateEmbeddingProvider(
        client=openai_factory(api_key=api_key, base_url=base_url),
        model=selected_model,
    )
