import asyncio

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


class ResetBaseBackend(FakeBaseBackend):
    def __init__(self, *, reset_result=True, reset_error=None):
        super().__init__()
        self.reset_calls = []
        self.reset_result = reset_result
        self.last_execution_error = reset_error

    async def reset_to(self, url):
        self.reset_calls.append(url)
        return self.reset_result


class DeterministicInteractablesBaseBackend(FakeBaseBackend):
    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "dom_login_button",
                "description": "Login button evidence",
                "locator": "#login-button",
                "action_kind": "click",
            }
        ]


class ScreenshotBaseBackend(FakeBaseBackend):
    def __init__(self):
        self.captured = []

    async def capture_screenshot(self, label):
        self.captured.append(label)
        return f"outputs/{label}.png"


class FakeStagehandProvider:
    def __init__(self):
        self.acted_instructions = []
        self.executed_instructions = []
        self.observed_instructions = []
        self.acted_actions = []

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

    async def observe_action(self, instruction):
        self.observed_instructions.append(instruction)
        return [
            StagehandObservedAction(
                description="Login button",
                selector="#login-button",
                method="click",
                arguments=(),
                raw={"backendNodeId": 42},
            )
        ]

    async def act_action(self, action):
        self.acted_actions.append(action)
        return StagehandActResult(
            success=True,
            message="Clicked",
            action_description=action.description,
            raw={"actionId": "act_observed"},
        )


@pytest.mark.anyio
async def test_stagehand_backend_observed_action_mode_delegates_base_evidence():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=DeterministicInteractablesBaseBackend(),
        provider=provider,
        goal="Explore shopping capabilities.",
        execution_mode="observed_action",
    )
    state = await backend.observe_state()

    actions = await backend.list_interactables(state)

    assert actions == [
        {
            "semantic_id": "dom_login_button",
            "description": "Login button evidence",
            "locator": "#login-button",
            "action_kind": "click",
        }
    ]


@pytest.mark.anyio
async def test_stagehand_backend_observe_act_mode_delegates_base_evidence():
    backend = StagehandAutomationBackend(
        base_backend=DeterministicInteractablesBaseBackend(),
        provider=FakeStagehandProvider(),
        goal="Explore visible functionality.",
        execution_mode="observe_act",
    )
    state = await backend.observe_state()

    actions = await backend.list_interactables(state)

    assert actions == [
        {
            "semantic_id": "dom_login_button",
            "description": "Login button evidence",
            "locator": "#login-button",
            "action_kind": "click",
        }
    ]


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
async def test_stagehand_backend_delegates_entry_reset():
    base = ResetBaseBackend()
    backend = StagehandAutomationBackend(
        base_backend=base,
        provider=FakeStagehandProvider(),
        goal="Explore shopping capabilities.",
    )

    assert await backend.reset_to("https://example.test/start") is True
    assert base.reset_calls == ["https://example.test/start"]
    assert backend.last_execution_error is None
    assert backend.last_execution_metadata == {
        "action_source": "stagehand",
        "stagehand_execution_mode": "entry_reset",
        "backend_reported_success": True,
    }


@pytest.mark.anyio
async def test_stagehand_backend_reports_entry_reset_failure():
    base = ResetBaseBackend(reset_result=False, reset_error="reset_error:TimeoutError")
    backend = StagehandAutomationBackend(
        base_backend=base,
        provider=FakeStagehandProvider(),
        goal="Explore shopping capabilities.",
    )

    assert await backend.reset_to("https://example.test/start") is False
    assert backend.last_execution_error == "reset_error:TimeoutError"
    assert backend.last_execution_metadata["stagehand_execution_mode"] == "entry_reset"


def test_stagehand_backend_rejects_removed_business_milestone_mode():
    with pytest.raises(ValueError, match="business_milestone"):
        StagehandAutomationBackend(
            base_backend=FakeBaseBackend(),
            provider=FakeStagehandProvider(),
            goal="Explore shopping capabilities.",
            execution_mode="business_milestone",
        )


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
    assert provider.executed_instructions == [
        (
            "Execute only this selected business action: add_item_to_cart. "
            "Business action: add_item_to_cart. Target hint: button labeled "
            "Add to cart. Evidence: A product card contains an Add to cart button. "
            "Stop after the first visible completion or clear failure. "
            "Do not continue to the next business goal.",
            5,
        )
    ]
    assert backend.last_execution_metadata["stagehand_execution_mode"] == (
        "business_intent"
    )


@pytest.mark.anyio
async def test_stagehand_backend_observe_act_mode_avoids_agent_execute():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore visible functionality.",
        execution_mode="observe_act",
    )

    success = await backend.execute(
        BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="submit_login",
            canonical_action_name="submit_login",
            description="Click the Login button",
        )
    )

    assert success is True
    assert provider.observed_instructions == ["Click the Login button"]
    assert len(provider.acted_actions) == 1
    assert provider.executed_instructions == []
    assert provider.acted_instructions == []
    assert backend.last_execution_metadata["stagehand_execution_mode"] == (
        "observe_act"
    )
    assert backend.last_execution_metadata["stagehand_observed_action"] == {
        "description": "Login button",
        "selector": "#login-button",
        "method": "click",
        "arguments": [],
        "backendNodeId": 42,
    }


@pytest.mark.anyio
async def test_stagehand_backend_observe_act_executes_all_observed_actions_in_order():
    class MultiActionProvider(FakeStagehandProvider):
        async def observe_action(self, instruction):
            self.observed_instructions.append(instruction)
            return [
                StagehandObservedAction(
                    description="Username input",
                    selector="#username",
                    method="fill",
                    arguments=("standard_user",),
                ),
                StagehandObservedAction(
                    description="Password input",
                    selector="#password",
                    method="fill",
                    arguments=("secret_sauce",),
                ),
            ]

        async def act_action(self, action):
            self.acted_actions.append(action)
            return StagehandActResult(
                success=True,
                message="Filled one credential field",
                action_description=action.description,
            )

    provider = MultiActionProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore visible functionality.",
        execution_mode="observe_act",
    )

    success = await backend.execute(
        BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="enter_credentials",
            canonical_action_name="enter_credentials",
            description="Fill in the username and password fields.",
            execution_policy="composite",
        )
    )

    assert success is True
    assert [action.description for action in provider.acted_actions] == [
        "Username input",
        "Password input",
    ]


@pytest.mark.anyio
async def test_stagehand_backend_observe_act_executes_only_first_single_instance_action():
    class MultiActionProvider(FakeStagehandProvider):
        async def observe_action(self, instruction):
            self.observed_instructions.append(instruction)
            return [
                StagehandObservedAction(
                    description="First matching control",
                    selector="#first",
                    method="click",
                ),
                StagehandObservedAction(
                    description="Second matching control",
                    selector="#second",
                    method="click",
                ),
            ]

    provider = MultiActionProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore visible functionality.",
        execution_mode="observe_act",
    )

    success = await backend.execute(
        BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="add_to_cart",
            canonical_action_name="add_to_cart",
            description="Add one visible item to the cart.",
            execution_policy="single_instance",
        )
    )

    assert success is True
    assert [action.description for action in provider.acted_actions] == [
        "First matching control"
    ]


@pytest.mark.anyio
async def test_stagehand_backend_observe_act_does_not_append_exploration_memory():
    provider = FakeStagehandProvider()
    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=provider,
        goal="Explore visible functionality.",
        execution_mode="observe_act",
    )
    backend.set_exploration_context(
        "Exploration memory:\nAvoid repeating actions: sort_products"
    )

    success = await backend.execute(
        BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id="open_cart",
            canonical_action_name="open_cart",
            description=(
                "Open the shopping cart to view selected items. "
                "Target: Cart icon in the header."
            ),
        )
    )

    assert success is True
    assert provider.observed_instructions == [
        "Open the shopping cart to view selected items. "
        "Target: Cart icon in the header."
    ]


@pytest.mark.anyio
async def test_stagehand_backend_bounds_provider_execution_time():
    class SlowProvider(FakeStagehandProvider):
        async def execute_instruction(self, instruction, *, max_steps):
            await asyncio.sleep(0.02)
            return await super().execute_instruction(instruction, max_steps=max_steps)

    backend = StagehandAutomationBackend(
        base_backend=FakeBaseBackend(),
        provider=SlowProvider(),
        goal="Advance one useful milestone.",
        execution_mode="observed_action",
        action_timeout_seconds=0.001,
    )
    state = await backend.observe_state()
    action = BrowserAction(
        action_kind="business_intent",
        locator=None,
        semantic_id="advance_one_useful_milestone",
        description="Advance one useful milestone.",
    )

    assert await backend.execute(action) is False
    assert backend.last_execution_error == "stagehand_action_timeout"
    assert backend.last_execution_metadata["stagehand_error"] == (
        "stagehand_action_timeout"
    )
