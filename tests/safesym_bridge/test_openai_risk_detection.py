import base64

from ai_web_explorer.grounded_web.openai_risk_detection import (
    OpenAIRiskDetectionProvider,
    create_openai_risk_detection_provider_from_env,
)
from ai_web_explorer.grounded_web.risk_detection import (
    DEFAULT_RISK_TAXONOMY_PATH,
    RISK_ASSESSMENT_SYSTEM_PROMPT,
    RiskDetectionRequest,
    load_risk_taxonomy,
)


class _FakeMessage:
    content = (
        '{"potential_risk":true,"risk_type":"financial_transaction",'
        '"evidence":"The action enters a checkout workflow."}'
    )


class _FakeCompletion:
    choices = [type("Choice", (), {"message": _FakeMessage()})()]


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeCompletion()


class _FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FakeCompletions()})()


def test_provider_sends_only_prompt_and_current_screenshot(tmp_path):
    screenshot = tmp_path / "current.png"
    screenshot.write_bytes(b"current-image")
    taxonomy = load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)
    client = _FakeClient()
    provider = OpenAIRiskDetectionProvider(client=client, model="vision-test")

    assessment = provider(
        RiskDetectionRequest(
            screenshot_path=str(screenshot),
            candidate_label="Proceed to checkout.",
            taxonomy=taxonomy,
        )
    )

    assert assessment.potential_risk is True
    assert assessment.risk_type == "financial_transaction"
    call = client.chat.completions.calls[0]
    assert call["model"] == "vision-test"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0] == {
        "role": "system",
        "content": RISK_ASSESSMENT_SYSTEM_PROMPT,
    }
    content = call["messages"][1]["content"]
    assert "Proceed to checkout." in content[0]["text"]
    assert "screenshot_path" not in content[0]["text"]
    assert content[1]["image_url"]["url"] == (
        "data:image/png;base64," + base64.b64encode(b"current-image").decode("ascii")
    )
    assert len(content) == 2


def test_factory_uses_risk_specific_model_and_timeout():
    created = {}

    def fake_factory(**kwargs):
        created.update(kwargs)
        return _FakeClient()

    provider = create_openai_risk_detection_provider_from_env(
        request_timeout_seconds=45,
        openai_factory=fake_factory,
        load_dotenv=lambda: None,
        environ={
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://api.example.test/v1",
            "OPENAI_RISK_DETECTION_MODEL": "risk-vision-test",
        },
    )

    assert provider.model == "risk-vision-test"
    assert created == {
        "api_key": "test-key",
        "base_url": "https://api.example.test/v1",
        "timeout": 45,
    }
