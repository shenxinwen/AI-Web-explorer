import os
import sys
from types import SimpleNamespace

import pytest

from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    StagehandSdkProvider,
    create_async_stagehand_provider_from_env,
)
from ai_web_explorer.grounded_web.stagehand_actions import StagehandObservedAction
from ai_web_explorer.grounded_web.stagehand_actions import StagehandActResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_create_stagehand_provider_from_env_reports_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "stagehand", None)

    with pytest.raises(ValueError, match="stagehand Python SDK is required"):
        await create_async_stagehand_provider_from_env(model_name="openai/gpt-5-nano")


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
async def test_create_stagehand_provider_configures_local_no_proxy_and_timeout(
    monkeypatch,
):
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
    monkeypatch.setenv("NO_PROXY", "example.test")

    await create_async_stagehand_provider_from_env(
        load_dotenv=lambda: None,
        environ={
            "STAGEHAND_SERVER": "local",
            "STAGEHAND_MODEL": "deepseek/deepseek-v4-pro",
            "MODEL_API_KEY": "model-test-key",
            "STAGEHAND_LOCAL_READY_TIMEOUT_S": "45",
        },
    )

    assert calls == [
        {
            "model_api_key": "model-test-key",
            "server": "local",
            "local_ready_timeout_s": 45.0,
        }
    ]
    no_proxy = {item.strip() for item in os.environ["NO_PROXY"].split(",")}
    assert {"example.test", "localhost", "127.0.0.1", "::1"}.issubset(no_proxy)


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


class FakeSession:
    def __init__(self):
        self.acted_input = None
        self.acted_page = None
        self.observed_instruction = None
        self.observed_page = None
        self.executed_agent_config = None
        self.executed_options = None
        self.executed_page = None

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

    async def observe(self, instruction, page=None):
        self.observed_instruction = instruction
        self.observed_page = page
        return SimpleNamespace(
            data=SimpleNamespace(
                result=[
                    SimpleNamespace(
                        description="Login button to submit the form.",
                        selector="xpath=/html/body/form/input[@type='submit']",
                        method="click",
                        arguments=[],
                        backendNodeId=42,
                    )
                ],
                actionId="observe_1",
            )
        )

    async def execute(self, agent_config, execute_options, page=None):
        self.executed_agent_config = agent_config
        self.executed_options = execute_options
        self.executed_page = page
        return SimpleNamespace(
            data=SimpleNamespace(
                result=SimpleNamespace(
                    success=True,
                    completed=True,
                    message="Logged in and reached a product listing",
                    actions=[
                        SimpleNamespace(type="act", action="fill username"),
                        SimpleNamespace(type="act", action="click login"),
                    ],
                )
            )
        )


def _install_fake_stagehand(monkeypatch, calls):
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


@pytest.mark.anyio
async def test_stagehand_sdk_provider_acts_on_instruction_text():
    session = FakeSession()
    provider = StagehandSdkProvider(session=session)

    result = await provider.act_instruction(
        "Advance the website by exactly one meaningful business milestone."
    )

    assert (
        session.acted_input
        == "Advance the website by exactly one meaningful business milestone."
    )
    assert result.success is True
    assert result.action_description == "Clicked Login"


@pytest.mark.anyio
async def test_stagehand_sdk_provider_observes_then_acts_on_concrete_action():
    session = FakeSession()
    page = object()
    provider = StagehandSdkProvider(session=session, page=page)

    actions = await provider.observe_action("Click the Login button")
    result = await provider.act_action(actions[0])

    assert actions == [
        StagehandObservedAction(
            description="Login button to submit the form.",
            selector="xpath=/html/body/form/input[@type='submit']",
            method="click",
            arguments=(),
            raw={
                "description": "Login button to submit the form.",
                "selector": "xpath=/html/body/form/input[@type='submit']",
                "method": "click",
                "arguments": [],
                "backendNodeId": 42,
            },
        )
    ]
    assert session.observed_instruction == "Click the Login button"
    assert session.observed_page is page
    assert session.acted_input == {
        "description": "Login button to submit the form.",
        "selector": "xpath=/html/body/form/input[@type='submit']",
        "method": "click",
        "arguments": [],
    }
    assert session.acted_page is page
    assert result.success is True


@pytest.mark.anyio
async def test_stagehand_sdk_provider_executes_instruction_with_step_limit():
    session = FakeSession()
    provider = StagehandSdkProvider(session=session)

    result = await provider.execute_instruction("Advance one milestone.", max_steps=5)

    assert session.executed_agent_config == {"mode": "dom"}
    assert session.executed_options == {
        "instruction": "Advance one milestone.",
        "max_steps": 5,
        "use_search": False,
    }
    assert result.success is True
    assert result.message == "Logged in and reached a product listing"
    assert result.raw["result"]["actions"][0]["action"] == "fill username"


@pytest.mark.anyio
async def test_stagehand_model_relay_isolated_from_visual_openai_base_url(monkeypatch):
    calls = []
    _install_fake_stagehand(monkeypatch, calls)

    provider = await create_async_stagehand_provider_from_env(
        load_dotenv=lambda: None,
        environ={
            "STAGEHAND_SERVER": "local",
            "STAGEHAND_MODEL": "openai/gemini-3-flash-preview",
            "MODEL_API_KEY": "cun-test-key",
            "STAGEHAND_MODEL_BASE_URL": "https://www.cun.ai/v1",
            "STAGEHAND_MODEL_USER_AGENT": "CUN.AI-Python/1.0",
            "OPENAI_BASE_URL": "https://visual.example.test/v1",
        },
    )

    result = await provider.execute_instruction("Advance one step.")

    assert provider.session.executed_agent_config == {
        "mode": "dom",
        "model": {
            "model_name": "openai/gemini-3-flash-preview",
            "provider": "openai",
            "api_key": "cun-test-key",
            "base_url": "https://www.cun.ai/v1",
            "headers": {"User-Agent": "CUN.AI-Python/1.0"},
        },
    }
    assert provider.session.executed_agent_config["model"]["base_url"] != (
        "https://visual.example.test/v1"
    )
    raw_text = str(result.raw)
    assert "cun-test-key" not in raw_text
    assert "www.cun.ai" not in raw_text
    assert "CUN.AI-Python" not in raw_text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            {"STAGEHAND_MODEL_BASE_URL": "ftp://relay.test"},
            "STAGEHAND_MODEL_BASE_URL",
        ),
        (
            {
                "STAGEHAND_MODEL": "google/gemini-3-flash-preview",
                "STAGEHAND_MODEL_BASE_URL": "https://relay.test/v1",
            },
            "STAGEHAND_MODEL",
        ),
        (
            {"STAGEHAND_MODEL_BASE_URL": "https://relay.test/v1"},
            "MODEL_API_KEY",
        ),
        (
            {"STAGEHAND_MODEL_USER_AGENT": "CUN.AI-Python/1.0"},
            "STAGEHAND_MODEL_USER_AGENT",
        ),
    ],
)
async def test_stagehand_model_relay_rejects_invalid_configuration(
    monkeypatch,
    environment,
    message,
):
    _install_fake_stagehand(monkeypatch, [])
    environ = {
        "STAGEHAND_SERVER": "local",
        "STAGEHAND_MODEL": "openai/gemini-3-flash-preview",
        "MODEL_API_KEY": "cun-test-key",
    }
    environ.update(environment)
    if "MODEL_API_KEY" not in environment:
        environ["MODEL_API_KEY"] = "cun-test-key"
    if message == "MODEL_API_KEY":
        environ.pop("MODEL_API_KEY")

    with pytest.raises(ValueError, match=message):
        await create_async_stagehand_provider_from_env(
            load_dotenv=lambda: None,
            environ=environ,
        )


@pytest.mark.anyio
async def test_stagehand_provider_preserves_legacy_factory_and_method_contracts(
    monkeypatch,
):
    calls = []
    _install_fake_stagehand(monkeypatch, calls)
    page = object()

    provider = await create_async_stagehand_provider_from_env(
        page=page,
        load_dotenv=lambda: None,
        environ={
            "STAGEHAND_SERVER": "local",
            "STAGEHAND_MODEL": "deepseek/deepseek-v4-pro",
            "MODEL_API_KEY": "model-test-key",
        },
    )

    act_result = await provider.act_instruction("Click the selected action.")
    execute_result = await provider.execute_instruction(
        "Advance one milestone.",
        max_steps=5,
    )

    assert isinstance(act_result, StagehandActResult)
    assert isinstance(execute_result, StagehandActResult)
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
    assert provider.session.executed_agent_config == {"mode": "dom"}
