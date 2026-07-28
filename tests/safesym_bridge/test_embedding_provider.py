import pytest

from ai_web_explorer.grounded_web.embedding_provider import (
    DEFAULT_EMBEDDING_MODEL,
    CompatibleEmbeddingProvider,
    create_embedding_provider_from_env,
)


class FakeEmbeddingResponse:
    class Item:
        embedding = [0.1, 0.2, 0.3]

    data = [Item()]


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeEmbeddingResponse()


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.embeddings = FakeEmbeddings()


def test_compatible_embedding_provider_returns_embedding_with_dimension():
    client = FakeClient()
    provider = CompatibleEmbeddingProvider(
        client=client,
        model="text-embedding-test",
        dimension=512,
    )

    assert provider("hello state") == [0.1, 0.2, 0.3]
    assert client.embeddings.calls == [
        {
            "model": "text-embedding-test",
            "input": "hello state",
            "dimensions": 512,
        }
    ]


def test_create_embedding_provider_requires_embedding_api_key():
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY"):
        create_embedding_provider_from_env(
            environ={},
            load_dotenv=lambda: None,
            openai_factory=lambda **kwargs: FakeClient(**kwargs),
        )


def test_create_embedding_provider_uses_embedding_env_names():
    provider = create_embedding_provider_from_env(
        environ={
            "EMBEDDING_API_KEY": "test",
            "EMBEDDING_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
        },
        load_dotenv=lambda: None,
        openai_factory=lambda **kwargs: FakeClient(**kwargs),
    )

    assert provider.model == "text-embedding-v4"
    assert provider.dimension == 1024
    assert provider.client.kwargs == {
        "api_key": "test",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }


def test_create_embedding_provider_uses_default_model_without_fallback_aliases():
    provider = create_embedding_provider_from_env(
        environ={"EMBEDDING_API_KEY": "test"},
        load_dotenv=lambda: None,
        openai_factory=lambda **kwargs: FakeClient(**kwargs),
    )

    assert provider.model == DEFAULT_EMBEDDING_MODEL
    assert provider.dimension is None
