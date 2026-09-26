from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

DEFAULT_EMBEDDING_MODEL = "text-embedding-v4"


@dataclass(frozen=True)
class CompatibleEmbeddingProvider:
    client: Any
    model: str = DEFAULT_EMBEDDING_MODEL
    dimension: int | None = None

    def __call__(self, text: str) -> list[float]:
        request = {
            "model": self.model,
            "input": text,
        }
        if self.dimension is not None:
            request["dimensions"] = self.dimension
        response = self.client.embeddings.create(**request)
        return [float(value) for value in response.data[0].embedding]


def create_embedding_provider_from_env(
    *,
    model: str | None = None,
    dimension: int | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> CompatibleEmbeddingProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv
    load_dotenv()

    env = os.environ if environ is None else environ
    api_key = env.get("EMBEDDING_API_KEY")
    if not api_key:
        raise ValueError("EMBEDDING_API_KEY is required for state embeddings.")
    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI
    base_url = env.get("EMBEDDING_BASE_URL") or None
    selected_model = model or env.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    selected_dimension = dimension
    if selected_dimension is None and env.get("EMBEDDING_DIMENSION"):
        selected_dimension = int(str(env["EMBEDDING_DIMENSION"]))
    return CompatibleEmbeddingProvider(
        client=openai_factory(api_key=api_key, base_url=base_url),
        model=selected_model,
        dimension=selected_dimension,
    )
