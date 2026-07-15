import pytest

from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeAdapter:
    app_name = "fake"

    def __init__(self):
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": False},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": True},
            ),
        ]
        self.executed = []

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "add_to_cart_product",
                "description": "Add to cart",
                "locator": "button.add",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


class RepeatedStateAdapter:
    app_name = "fake"

    def __init__(self):
        self.executed = []

    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_count": len(self.executed)},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "first_action",
                "description": "First action",
                "locator": "#first",
                "action_kind": "click",
                "explored": False,
            },
            {
                "semantic_id": "second_action",
                "description": "Second action",
                "locator": "#second",
                "action_kind": "click",
                "input_values": {"#name": "Alice"},
                "explored": False,
            },
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_records_self_loop_delta():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.total_steps_completed == 1
    assert len(graph.nodes) == 1
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.source_node_id == "listing"
    assert edge.target_node_id == "listing"
    assert edge.action.semantic_id == "add_to_cart_product"
    assert edge.schema_delta == {
        "cart_nonempty": {"before": False, "after": True}
    }
    assert edge.observed_delta[0].field == "cart_nonempty"


@pytest.mark.anyio
async def test_explore_one_step_skips_previously_explored_self_loop_action():
    adapter = RepeatedStateAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    assert [action.semantic_id for action in adapter.executed] == [
        "first_action",
        "second_action",
    ]
    assert adapter.executed[1].input_values == {"#name": "Alice"}
    assert [edge.action.semantic_id for edge in graph.edges] == [
        "first_action",
        "second_action",
    ]
