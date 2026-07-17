import pytest

from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
)
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeBaseBackend:
    app_name = "saucedemo"

    async def observe_state(self):
        return StateSnapshot(
            page_id="login",
            url="https://www.saucedemo.com/",
            title="Swag Labs",
            signature={"is_logged_in": False},
        )

    async def list_interactables(self, state):
        return []

    async def execute(self, action):
        raise AssertionError("Stagehand wrapper must execute through provider")


class FakeStagehandProvider:
    def __init__(self):
        self.observed = []
        self.acted = []

    async def observe_next_action(self, *, instruction, state):
        self.observed.append((instruction, state.page_id))
        return [
            StagehandObservedAction(
                description="Click the Login button",
                method="click",
                selector="#login-button",
                arguments=[],
                raw={"backendNodeId": 123},
            )
        ]

    async def act(self, action):
        self.acted.append(action)
        return StagehandActResult(
            success=True,
            message="Clicked login",
            action_description="Clicked button with text Login",
            raw={"actionId": "act_login"},
        )


@pytest.mark.anyio
async def test_stagehand_backend_exposes_one_observed_action_as_interactable():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Log in and reach checkout overview.",
    )
    state = await backend.observe_state()

    actions = await backend.list_interactables(state)

    assert provider.observed == [
        ("Log in and reach checkout overview.", "login")
    ]
    assert actions[0]["semantic_id"] == "stagehand_000_click_login_button"
    assert actions[0]["description"] == "Click the Login button"
    assert actions[0]["locator"] == "#login-button"
    assert actions[0]["action_kind"] == "click"
    assert actions[0]["metadata"]["action_source"] == "stagehand"


@pytest.mark.anyio
async def test_stagehand_backend_execute_calls_provider_and_records_metadata():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Log in.",
    )
    state = await backend.observe_state()
    action_dict = (await backend.list_interactables(state))[0]

    success = await backend.execute(action_dict)

    assert success is True
    assert provider.acted[0].description == "Click the Login button"
    assert backend.last_execution_error is None
    assert backend.last_execution_metadata["action_source"] == "stagehand"
    assert backend.last_execution_metadata["stagehand_selector"] == "#login-button"
    assert backend.last_execution_metadata["stagehand_act_result"]["success"] is True
