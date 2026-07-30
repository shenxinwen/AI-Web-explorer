import pytest

from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.graph import BrowserAction
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

    def __init__(self):
        self.back_calls = 0

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

    async def go_back(self):
        self.back_calls += 1
        return True


class ScreenshotBaseBackend(FakeBaseBackend):
    def __init__(self):
        self.captured = []

    async def capture_screenshot(self, label):
        self.captured.append(label)
        return f"outputs/{label}.png"


class FakeStagehandProvider:
    def __init__(self):
        self.observed = []
        self.acted = []
        self.acted_instructions = []
        self.executed_instructions = []

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

    async def act_instruction(self, instruction):
        self.acted_instructions.append(instruction)
        return StagehandActResult(
            success=True,
            message="Advanced one milestone",
            action_description="Logged in and reached a product listing",
            raw={"actionId": "act_milestone"},
        )

    async def execute_instruction(self, instruction, *, max_steps):
        self.executed_instructions.append((instruction, max_steps))
        return StagehandActResult(
            success=True,
            message="Completed milestone",
            action_description="Logged in and reached a product listing",
            raw={"actions": [{"type": "act", "action": "fill username"}]},
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

    assert provider.observed == [("Log in and reach checkout overview.", "login")]
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


@pytest.mark.anyio
async def test_stagehand_backend_retains_previous_observed_actions_for_cached_nodes():
    class SwitchingProvider:
        def __init__(self):
            self.actions = [
                StagehandObservedAction(
                    description="Click Login",
                    method="click",
                    selector="#login-button",
                    arguments=[],
                )
            ]
            self.acted = []

        async def observe_next_action(self, *, instruction, state):
            return list(self.actions)

        async def act(self, action):
            self.acted.append(action)
            return StagehandActResult(success=True)

    provider = SwitchingProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="log in",
    )
    state = StateSnapshot(
        page_id="login",
        url="https://example.test",
        title="Login",
        signature={},
    )

    first_actions = await backend.list_interactables(state)
    provider.actions = [
        StagehandObservedAction(
            description="Fill password",
            method="fill",
            selector="#password",
            arguments=["secret_sauce"],
        )
    ]
    await backend.list_interactables(state)

    assert await backend.execute(first_actions[0]) is True
    assert provider.acted[0].description == "Click Login"


@pytest.mark.anyio
async def test_stagehand_backend_delegates_screenshot_capture_to_base_backend():
    base = ScreenshotBaseBackend()
    backend = StagehandAutomationBackend(
        base_backend=base,
        provider=FakeStagehandProvider(),
        goal="Log in.",
    )

    path = await backend.capture_screenshot("before_0001")

    assert path == "outputs/before_0001.png"
    assert base.captured == ["before_0001"]


@pytest.mark.anyio
async def test_stagehand_backend_delegates_go_back_to_base_backend():
    base = FakeBaseBackend()
    backend = StagehandAutomationBackend(
        base_backend=base,
        provider=FakeStagehandProvider(),
        goal="Explore shopping capabilities.",
    )

    assert await backend.go_back() is True
    assert base.back_calls == 1


@pytest.mark.anyio
async def test_stagehand_backend_business_milestone_mode_acts_without_observe():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Advance one meaningful checkout milestone.",
        execution_mode="business_milestone",
    )
    state = await backend.observe_state()

    actions = await backend.list_interactables(state)
    success = await backend.execute(actions[0])

    assert success is True
    assert provider.observed == []
    assert provider.acted == []
    assert provider.acted_instructions == []
    assert provider.executed_instructions == [
        ("Advance one meaningful checkout milestone.", 5)
    ]
    assert actions[0]["semantic_id"] == "stagehand_business_milestone_001"
    assert actions[0]["description"] == "Advance one meaningful checkout milestone."
    assert actions[0]["locator"] is None
    assert actions[0]["action_kind"] == "business_intent"
    assert actions[0]["input_values"] == {}
    assert actions[0]["action_label"] == "Advance one business milestone"
    assert actions[0]["canonical_action_name"] == "advance_business_milestone"
    assert actions[0]["naming_provenance"] == {"source": "stagehand_business_milestone"}
    assert actions[0]["explored"] is False
    assert actions[0]["metadata"] == {
        "action_source": "stagehand",
        "stagehand_execution_mode": "business_milestone",
    }
    assert backend.last_execution_metadata["stagehand_observed_action"] is None
    assert (
        backend.last_execution_metadata["stagehand_act_result"]["action_description"]
        == "Logged in and reached a product listing"
    )


@pytest.mark.anyio
async def test_stagehand_backend_business_milestone_falls_back_to_act_instruction():
    class ActOnlyProvider:
        def __init__(self):
            self.acted_instructions = []

        async def act_instruction(self, instruction):
            self.acted_instructions.append(instruction)
            return StagehandActResult(success=True, message="Acted")

    provider = ActOnlyProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Advance one meaningful checkout milestone.",
        execution_mode="business_milestone",
    )
    state = await backend.observe_state()
    actions = await backend.list_interactables(state)

    assert await backend.execute(actions[0]) is True
    assert provider.acted_instructions == ["Advance one meaningful checkout milestone."]


@pytest.mark.anyio
async def test_stagehand_backend_executes_business_intent_action_instruction():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore shopping capabilities.",
    )

    success = await backend.execute(
        BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="add_item_to_cart",
            canonical_action_name="add_item_to_cart",
            description=(
                "Business action: add_item_to_cart. Target hint: button labeled "
                "Add to cart. Evidence: A product card contains an Add to cart button."
            ),
        )
    )

    assert success is True
    assert provider.observed == []
    assert provider.acted == []
    assert provider.executed_instructions == [
        (
            "Business action: add_item_to_cart. Target hint: button labeled "
            "Add to cart. Evidence: A product card contains an Add to cart button.",
            5,
        )
    ]
    assert backend.last_execution_metadata["stagehand_execution_mode"] == (
        "business_intent"
    )


@pytest.mark.anyio
async def test_stagehand_backend_business_milestone_ids_are_runtime_unique():
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=FakeStagehandProvider(),
        goal="Advance one meaningful checkout milestone.",
        execution_mode="business_milestone",
    )
    state = await backend.observe_state()

    first = await backend.list_interactables(state)
    second = await backend.list_interactables(state)

    assert first[0]["semantic_id"] == "stagehand_business_milestone_001"
    assert second[0]["semantic_id"] == "stagehand_business_milestone_002"


@pytest.mark.anyio
async def test_stagehand_backend_business_milestone_uses_step_specific_goal():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Fallback milestone.",
        execution_mode="business_milestone",
        goal_provider=lambda step_number: f"Configured step {step_number}.",
        business_step_metadata_provider=lambda step_number: {
            "experiment_step_id": f"step_{step_number}",
            "expected_added_facts": [f"fact_{step_number}"],
        },
    )
    state = await backend.observe_state()

    first = (await backend.list_interactables(state))[0]
    second = (await backend.list_interactables(state))[0]
    success = await backend.execute(second)

    assert success is True
    assert first["description"] == "Configured step 1."
    assert first["metadata"]["experiment_step_id"] == "step_1"
    assert first["canonical_action_name"] == "step_1"
    assert provider.executed_instructions == [("Configured step 2.", 5)]
    assert backend.last_execution_metadata["experiment_step_id"] == "step_2"
    assert backend.last_execution_metadata["expected_added_facts"] == ["fact_2"]


@pytest.mark.anyio
async def test_stagehand_business_milestone_appends_exploration_context():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore one useful action.",
        execution_mode="business_milestone",
    )
    state = await backend.observe_state()
    actions = await backend.list_interactables(state)

    backend.set_exploration_context("Avoid repeating actions: theme_toggle")
    success = await backend.execute(actions[0])

    assert success is True
    assert "Explore one useful action." in provider.executed_instructions[0][0]
    assert (
        "Avoid repeating actions: theme_toggle" in provider.executed_instructions[0][0]
    )
