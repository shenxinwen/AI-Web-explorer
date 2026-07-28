import pytest

from ai_web_explorer.grounded_web.openai_state_embedding import (
    DEFAULT_OPENAI_STATE_EMBEDDING_MODEL,
    OpenAIStateEmbeddingProvider,
    create_openai_state_embedding_provider_from_env,
)


class FakeEmbeddingResponse:
    class Item:
        embedding = [0.1, 0.2, 0.3]

    data = [Item()]


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, *, model, input):
        self.calls.append((model, input))
        return FakeEmbeddingResponse()


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.embeddings = FakeEmbeddings()


def test_openai_state_embedding_provider_returns_embedding():
    client = FakeClient()
    provider = OpenAIStateEmbeddingProvider(client=client, model="text-embedding-test")

    assert provider("hello state") == [0.1, 0.2, 0.3]
    assert client.embeddings.calls == [("text-embedding-test", "hello state")]


def test_create_openai_state_embedding_provider_requires_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_openai_state_embedding_provider_from_env(
            environ={},
            load_dotenv=lambda: None,
            openai_factory=lambda **kwargs: FakeClient(**kwargs),
        )


def test_create_openai_state_embedding_provider_uses_default_model():
    provider = create_openai_state_embedding_provider_from_env(
        environ={"OPENAI_API_KEY": "test"},
        load_dotenv=lambda: None,
        openai_factory=lambda **kwargs: FakeClient(**kwargs),
    )

    assert provider.model == DEFAULT_OPENAI_STATE_EMBEDDING_MODEL
