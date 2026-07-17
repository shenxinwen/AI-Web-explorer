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


class FakeAction:
    def __init__(self, data):
        self.data = data

    def to_dict(self, exclude_none=True):
        return dict(self.data)


class FakeSession:
    def __init__(self):
        self.observed_instruction = None
        self.acted_input = None

    async def observe(self, instruction):
        self.observed_instruction = instruction
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

    async def act(self, input):
        self.acted_input = input
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
