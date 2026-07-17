import sys
from types import SimpleNamespace

import pytest

from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    StagehandSdkProvider,
    create_async_stagehand_provider_from_env,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_stagehand_provider_from_env_reports_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "stagehand", None)

    with pytest.raises(ValueError, match="stagehand Python SDK is required"):
        await create_async_stagehand_provider_from_env(
            model_name="openai/gpt-5-nano"
        )


@pytest.mark.anyio
async def test_create_stagehand_provider_from_env_requires_model(monkeypatch):
    class FakeAsyncStagehand:
        pass

    monkeypatch.setitem(
        sys.modules,
        "stagehand",
        SimpleNamespace(AsyncStagehand=FakeAsyncStagehand),
    )
    monkeypatch.delenv("STAGEHAND_MODEL", raising=False)

    with pytest.raises(ValueError, match="Stagehand model is required"):
        await create_async_stagehand_provider_from_env(
            load_dotenv=lambda: None,
            environ={},
        )


@pytest.mark.anyio
async def test_create_stagehand_provider_uses_deepseek_key_and_local_page(
    monkeypatch,
):
    calls = []
    fake_page = object()

    class FakeSessions:
        async def start(self, **kwargs):
            calls.append(("start", kwargs))
            return FakeSession()

    class FakeAsyncStagehand:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))
            self.sessions = FakeSessions()

    monkeypatch.setitem(
        sys.modules,
        "stagehand",
        SimpleNamespace(AsyncStagehand=FakeAsyncStagehand),
    )
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("STAGEHAND_SERVER", "local")

    provider = await create_async_stagehand_provider_from_env(
        model_name="deepseek/deepseek-v4-pro",
        page=fake_page,
        load_dotenv=lambda: None,
        environ={
            "DEEPSEEK_API_KEY": "deepseek-test-key",
            "STAGEHAND_SERVER": "local",
        },
    )

    assert provider.page is fake_page
    assert calls == [
        (
            "client",
            {
                "model_api_key": "deepseek-test-key",
                "server": "local",
            },
        ),
        (
            "start",
            {
                "model_name": "deepseek/deepseek-v4-pro",
                "browser": {"type": "local"},
            },
        ),
    ]


@pytest.mark.anyio
async def test_create_stagehand_provider_passes_local_cdp_url(monkeypatch):
    calls = []

    class FakeSessions:
        async def start(self, **kwargs):
            calls.append(("start", kwargs))
            return FakeSession()

    class FakeAsyncStagehand:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))
            self.sessions = FakeSessions()

    monkeypatch.setitem(
        sys.modules,
        "stagehand",
        SimpleNamespace(AsyncStagehand=FakeAsyncStagehand),
    )

    await create_async_stagehand_provider_from_env(
        load_dotenv=lambda: None,
        environ={
            "STAGEHAND_SERVER": "local",
            "STAGEHAND_MODEL": "deepseek/deepseek-v4-pro",
            "MODEL_API_KEY": "model-test-key",
        },
        local_cdp_url="http://127.0.0.1:9222",
    )

    assert calls[-1] == (
        "start",
        {
            "model_name": "deepseek/deepseek-v4-pro",
            "browser": {
                "type": "local",
                "cdp_url": "http://127.0.0.1:9222",
            },
        },
    )


@pytest.mark.anyio
async def test_create_stagehand_provider_loads_dotenv_and_model_api_key(
    monkeypatch,
):
    calls = []

    class FakeSessions:
        async def start(self, **kwargs):
            calls.append(("start", kwargs))
            return FakeSession()

    class FakeAsyncStagehand:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))
            self.sessions = FakeSessions()

    monkeypatch.setitem(
        sys.modules,
        "stagehand",
        SimpleNamespace(AsyncStagehand=FakeAsyncStagehand),
    )

    loaded = []
    provider = await create_async_stagehand_provider_from_env(
        load_dotenv=lambda: loaded.append("dotenv"),
        environ={
            "STAGEHAND_SERVER": "local",
            "STAGEHAND_MODEL": "deepseek/deepseek-v4-pro",
            "MODEL_API_KEY": "model-test-key",
        },
    )

    assert provider.session is not None
    assert loaded == ["dotenv"]
    assert calls == [
        (
            "client",
            {
                "model_api_key": "model-test-key",
                "server": "local",
            },
        ),
        (
            "start",
            {
                "model_name": "deepseek/deepseek-v4-pro",
                "browser": {"type": "local"},
            },
        ),
    ]


@pytest.mark.anyio
async def test_create_stagehand_provider_passes_stagehand_api_url(monkeypatch):
    calls = []

    class FakeSessions:
        async def start(self, **kwargs):
            return FakeSession()

    class FakeAsyncStagehand:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.sessions = FakeSessions()

    monkeypatch.setitem(
        sys.modules,
        "stagehand",
        SimpleNamespace(AsyncStagehand=FakeAsyncStagehand),
    )

    await create_async_stagehand_provider_from_env(
        load_dotenv=lambda: None,
        environ={
            "STAGEHAND_SERVER": "remote",
            "STAGEHAND_MODEL": "openai/gpt-5-nano",
            "MODEL_API_KEY": "model-test-key",
            "STAGEHAND_API_URL": "https://stagehand.example.test",
        },
    )

    assert calls == [
        {
            "model_api_key": "model-test-key",
            "server": "remote",
            "base_url": "https://stagehand.example.test",
        }
    ]


class FakeAction:
    def __init__(self, data):
        self.data = data

    def to_dict(self, exclude_none=True):
        return dict(self.data)


class FakeSession:
    def __init__(self):
        self.observed_instruction = None
        self.observed_page = None
        self.acted_input = None
        self.acted_page = None

    async def observe(self, instruction, page=None):
        self.observed_instruction = instruction
        self.observed_page = page
        return SimpleNamespace(
            data=SimpleNamespace(
                result=[
                    FakeAction(
                        {
                            "description": "Click Login",
                            "method": "click",
                            "selector": "#login-button",
                            "arguments": [],
                            "backendNodeId": 123,
                        }
                    )
                ]
            )
        )

    async def act(self, input, page=None):
        self.acted_input = input
        self.acted_page = page
        return SimpleNamespace(
            data=SimpleNamespace(
                result=SimpleNamespace(
                    success=True,
                    message="Clicked",
                    actionDescription="Clicked Login",
                ),
                actionId="act_1",
            )
        )


@pytest.mark.anyio
async def test_stagehand_sdk_provider_converts_observe_and_act_results():
    session = FakeSession()
    provider = StagehandSdkProvider(session=session)

    actions = await provider.observe_next_action(
        instruction="log in",
        state=SimpleNamespace(page_id="login"),
    )
    result = await provider.act(actions[0])

    assert session.observed_instruction == "log in"
    assert actions[0].description == "Click Login"
    assert actions[0].method == "click"
    assert actions[0].selector == "#login-button"
    assert actions[0].raw["backendNodeId"] == 123
    assert session.acted_input["selector"] == "#login-button"
    assert result.success is True
    assert result.raw["actionId"] == "act_1"


@pytest.mark.anyio
async def test_stagehand_sdk_provider_passes_page_when_available():
    page = object()
    session = FakeSession()
    provider = StagehandSdkProvider(session=session, page=page)

    await provider.observe_next_action(
        instruction="log in",
        state=SimpleNamespace(page_id="login"),
    )

    assert session.observed_page is page
