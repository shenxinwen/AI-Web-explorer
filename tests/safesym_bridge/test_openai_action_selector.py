import pytest

from ai_web_explorer.grounded_web.openai_action_selector import (
    OpenAIChatSelectionProvider,
    create_openai_chat_selection_provider_from_env,
)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeCompletion(
            '{"selected_action_id":"product_add_to_cart",'
            '"confidence":0.9,'
            '"reason":"The cart is empty."}'
        )


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_openai_chat_selection_provider_requests_json_response():
    client = _FakeClient()
    provider = OpenAIChatSelectionProvider(
        client=client,
        model="gpt-test",
    )

    raw = provider("prompt payload")

    assert '"selected_action_id":"product_add_to_cart"' in raw
    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-test"
    assert call["temperature"] == 0
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1] == {
        "role": "user",
        "content": "prompt payload",
    }


def test_openai_chat_selection_provider_rejects_empty_content():
    class EmptyCompletions(_FakeCompletions):
        def create(self, **kwargs):
            return _FakeCompletion("")

    client = _FakeClient()
    client.chat.completions = EmptyCompletions()
    provider = OpenAIChatSelectionProvider(client=client, model="gpt-test")

    with pytest.raises(ValueError, match="empty response"):
        provider("prompt")


def test_create_openai_provider_from_env_uses_dotenv_and_base_url(monkeypatch):
    created = []

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url=None):
            created.append((api_key, base_url))
            self.chat = _FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("OPENAI_ACTION_SELECTOR_MODEL", "gpt-env")

    provider = create_openai_chat_selection_provider_from_env(
        openai_factory=FakeOpenAI,
        load_dotenv=lambda: None,
    )

    assert provider.model == "gpt-env"
    assert created == [("test-key", "https://api.example.test/v1")]


def test_create_openai_provider_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_ACTION_SELECTOR_MODEL", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_openai_chat_selection_provider_from_env(
            openai_factory=lambda **kwargs: None,
            load_dotenv=lambda: None,
            environ={},
        )
