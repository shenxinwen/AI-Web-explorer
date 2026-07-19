import base64

import pytest

from ai_web_explorer.grounded_web.openai_visual_delta import (
    OpenAIVisualDeltaProvider,
    create_openai_visual_delta_provider_from_env,
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
            '{"candidate_added_facts":["cart_nonempty"],'
            '"candidate_removed_facts":["cart_empty"],'
            '"evidence":["cart badge changed"],'
            '"confidence":0.8}'
        )


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_openai_visual_delta_provider_sends_prompt_and_two_images(tmp_path):
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"before-image")
    after.write_bytes(b"after-image")
    client = _FakeClient()
    provider = OpenAIVisualDeltaProvider(client=client, model="gpt-vision-test")

    raw = provider(
        "compare screenshots",
        before_screenshot_path=str(before),
        after_screenshot_path=str(after),
    )

    assert '"candidate_added_facts":["cart_nonempty"]' in raw
    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-vision-test"
    assert call["response_format"] == {"type": "json_object"}
    content = call["messages"][1]["content"]
    assert content[0] == {"type": "text", "text": "compare screenshots"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == (
        "data:image/png;base64," + base64.b64encode(b"before-image").decode("ascii")
    )
    assert content[2]["type"] == "image_url"


def test_create_openai_visual_delta_provider_uses_separate_env_model(monkeypatch):
    created = []

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url=None):
            created.append((api_key, base_url))
            self.chat = _FakeChat()

    provider = create_openai_visual_delta_provider_from_env(
        openai_factory=FakeOpenAI,
        load_dotenv=lambda: None,
        environ={
            "OPENAI_API_KEY": "openai-test-key",
            "OPENAI_BASE_URL": "https://api.example.test/v1",
            "OPENAI_VISUAL_DELTA_MODEL": "gpt-vision-env",
            "STAGEHAND_MODEL": "deepseek/deepseek-v4-pro",
        },
    )

    assert provider.model == "gpt-vision-env"
    assert created == [("openai-test-key", "https://api.example.test/v1")]


def test_create_openai_visual_delta_provider_requires_openai_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_openai_visual_delta_provider_from_env(
            openai_factory=lambda **kwargs: None,
            load_dotenv=lambda: None,
            environ={},
        )
