from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.simple_grounded_web_agent import (
    SimpleGroundedWebAgent,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeBackend:
    app_name = "fake_shop"

    def __init__(self) -> None:
        self.executed: list[BrowserAction] = []
        self.state_index = 0

    async def observe_state(self) -> StateSnapshot:
        signatures = [
            {"cart_count": 0},
            {"cart_count": 1},
        ]
        signature = signatures[min(self.state_index, len(signatures) - 1)]
        return StateSnapshot(
            page_id="shop",
            url="http://example.test/shop",
            title="Shop",
            signature=signature,
        )

    async def list_interactables(self, state: StateSnapshot) -> list[dict]:
        if self.executed:
            return [
                {
                    "semantic_id": "add_to_cart",
                    "description": "Add to cart",
                    "locator": "#add",
                    "action_kind": "click",
                    "input_values": {},
                    "explored": True,
                }
            ]
        return [
            {
                "semantic_id": "add_to_cart",
                "description": "Add to cart",
                "locator": "#add",
                "action_kind": "click",
                "input_values": {},
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction) -> bool:
        self.executed.append(action)
        self.state_index = 1
        return True


class NoActionBackend(FakeBackend):
    async def list_interactables(self, state: StateSnapshot) -> list[dict]:
        return []


@pytest.mark.anyio
async def test_simple_grounded_agent_executes_one_grounded_action_and_records_delta():
    backend = FakeBackend()
    agent = SimpleGroundedWebAgent(backend)

    result = await agent.run(max_steps=1)

    assert len(backend.executed) == 1
    assert backend.executed[0].locator == "#add"
    assert result.summary.steps_completed == 1
    assert result.summary.stop_reason == "max_steps"
    assert result.graph.edges[0].status == "verified"
    assert result.graph.edges[0].schema_delta == {
        "cart_count": {"before": 0, "after": 1}
    }


@pytest.mark.anyio
async def test_simple_grounded_agent_stops_when_no_action_is_available():
    agent = SimpleGroundedWebAgent(NoActionBackend())

    result = await agent.run(max_steps=3)

    assert result.summary.steps_completed == 0
    assert result.summary.stop_reason == "no_available_action"
    assert result.graph.edges == []
