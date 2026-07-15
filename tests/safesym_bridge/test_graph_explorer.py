from __future__ import annotations

from pathlib import Path

import pytest

from ai_web_explorer.safesym_bridge.graph_explorer import (
    ExplorationAction,
    GraphExplorer,
    choose_next_unexplored_action,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(page_id: str, *, order_created: bool = False) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://example.test/{page_id}",
        title=page_id,
        signature={
            "is_logged_in": page_id != "login",
            "cart_count": 0,
            "order_created": order_created,
        },
    )


def action(page_id: str, semantic_id: str) -> ExplorationAction:
    return ExplorationAction(
        raw_description=f"Run {semantic_id}",
        semantic_id=semantic_id,
        page_id=page_id,
        execution_kind="click",
        selector=f"#{semantic_id}",
    )


def test_choose_next_unexplored_action_returns_first_new_action():
    chosen = choose_next_unexplored_action(
        snapshot("login"),
        [action("login", "login_submit")],
        None,
    )

    assert chosen is not None
    assert chosen.semantic_id == "login_submit"


def test_choose_next_unexplored_action_skips_existing_source_action():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )

    chosen = choose_next_unexplored_action(
        snapshot("login"),
        [
            action("login", "login_submit"),
            action("login", "login_help"),
        ],
        graph,
    )

    assert chosen is not None
    assert chosen.semantic_id == "login_help"


class FakeAdapter:
    app_name = "fake"
    start_node = "login"
    start_url = "https://example.test/"

    def __init__(self):
        self.states = [
            snapshot("login"),
            snapshot("inventory"),
            snapshot("checkout_complete", order_created=True),
        ]
        self.executed: list[str] = []

    async def observe_state(self, page):
        return self.states[len(self.executed)]

    async def list_actions(self, page, state):
        if state.page_id == "login":
            return [action("login", "login_submit")]
        if state.page_id == "inventory":
            return [action("inventory", "order_place_confirm")]
        return []

    async def execute_action(self, page, selected_action):
        self.executed.append(selected_action.semantic_id)

    def is_goal_state(self, state):
        return state.page_id == "checkout_complete" and bool(
            state.signature.get("order_created")
        )


@pytest.mark.anyio
async def test_graph_explorer_records_transitions_until_goal(tmp_path: Path):
    output_path = tmp_path / "graph.json"
    adapter = FakeAdapter()
    explorer = GraphExplorer(adapter, max_steps=5)

    result = await explorer.run(object(), output_path=output_path)

    assert result.stop_reason == "goal_reached"
    assert result.final_state.page_id == "checkout_complete"
    assert [edge.semantic_action for edge in result.graph.edges] == [
        "login_submit",
        "order_place_confirm",
    ]
    assert output_path.exists()


@pytest.mark.anyio
async def test_graph_explorer_marks_successful_action_interactable_explored():
    adapter = FakeAdapter()
    explorer = GraphExplorer(adapter, max_steps=1)

    result = await explorer.run(object())

    login = next(node for node in result.graph.nodes if node.id == "login")
    assert login.interactable_elements[0].description == "Run login_submit"
    assert login.interactable_elements[0].explored is True
