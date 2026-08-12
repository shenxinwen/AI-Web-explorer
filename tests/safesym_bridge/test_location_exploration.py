import json
import asyncio
from dataclasses import replace

from ai_web_explorer.grounded_web.graph import BusinessAffordance, WebKobeGraph
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.semantic_assistor import DeterministicSemanticAssistor
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.frontier_replay import select_frontier
from ai_web_explorer.grounded_web.location_exploration import (
    LOCATION_EXPLORATION_META_KEY,
    ExplorationLimits,
    LocationExplorationMemory,
)
from ai_web_explorer.safesym_bridge.browser_runner import write_web_kobe_graph
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    load_web_kobe_graph_json,
)


def _affordance(action_name: str) -> BusinessAffordance:
    return BusinessAffordance(
        action_name=action_name,
        label=action_name.replace("_", " "),
        relevance_hint="core",
        confidence=0.9,
    )


def _memory() -> LocationExplorationMemory:
    memory = LocationExplorationMemory()
    memory.merge_scan("shopping", [_affordance("sort_products")], kind="initial")
    memory.record_attempt("shopping", "sort_products", observable_change=True)
    return memory


def test_same_action_is_deduped_within_location_but_not_across_locations():
    memory = LocationExplorationMemory()
    memory.merge_scan("shopping", [_affordance("add_to_cart")], kind="initial")
    memory.merge_scan(
        "product_detail", [_affordance("add_to_cart")], kind="initial"
    )

    memory.record_attempt("shopping", "add_to_cart", observable_change=True)

    assert memory.next_candidate("shopping") is None
    assert memory.next_candidate("product_detail").action_name == "add_to_cart"


def test_second_no_change_attempt_closes_candidate():
    memory = LocationExplorationMemory(
        limits=ExplorationLimits(max_action_attempts_per_candidate=2)
    )
    memory.merge_scan("shopping", [_affordance("sort_products")], kind="initial")

    first = memory.record_attempt(
        "shopping", "sort_products", observable_change=False
    )
    assert first.status == "retryable_no_change"
    assert memory.next_candidate("shopping").action_name == "sort_products"

    second = memory.record_attempt(
        "shopping", "sort_products", observable_change=False
    )
    assert second.status == "no_observable_change"
    assert memory.next_candidate("shopping") is None


def test_targeted_scan_key_is_order_independent_and_runs_once():
    memory = LocationExplorationMemory()

    assert memory.should_run_targeted_scan(
        "shopping", added=["cart_has_items"], removed=[]
    )
    memory.mark_targeted_scan_complete(
        "shopping", added=["cart_has_items"], removed=[]
    )
    assert not memory.should_run_targeted_scan(
        "shopping", added=["cart_has_items"], removed=[]
    )
    assert not memory.should_run_targeted_scan(
        "SHOPPING", added=["cart_has_items"], removed=[]
    )


def test_location_memory_survives_compact_graph_round_trip(tmp_path):
    memory = _memory()
    graph = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=0,
        meta={LOCATION_EXPLORATION_META_KEY: memory.to_dict(), "future": {"x": 1}},
    )
    path = tmp_path / "graph.json"
    write_web_kobe_graph(graph, path)

    restored = load_web_kobe_graph_json(path)

    assert restored.meta[LOCATION_EXPLORATION_META_KEY] == memory.to_dict()
    assert restored.meta["future"] == {"x": 1}
    assert json.loads(path.read_text(encoding="utf-8"))["meta"][
        LOCATION_EXPLORATION_META_KEY
    ] == memory.to_dict()


class _ScopedAdapter:
    app_name = "scoped"

    def __init__(self):
        self.executed = []
        self.last_execution_error = None

    async def observe_state(self):
        count = min(len(self.executed), 1)
        return StateSnapshot(
            page_id="shopping",
            url="https://fixture.test/shopping",
            title="Shopping",
            signature={"cart_count": count},
        )

    async def list_interactables(self, state):
        return []

    async def capture_screenshot(self, label):
        return f"{label}.png"

    async def execute(self, action):
        self.executed.append(action)
        return True


def test_scoped_explorer_inherits_pool_and_runs_one_targeted_scan():
    calls = []

    def provider(prompt, **kwargs):
        payload = json.loads(prompt)
        if kwargs.get("current_screenshot_path") is not None:
            calls.append(payload.get("scan_kind", "initial"))
        if kwargs.get("current_screenshot_path") is not None:
            if payload.get("scan_kind") == "targeted":
                return json.dumps(
                    {
                        "location_id": "shopping",
                        "newly_enabled": [
                            {"intent": "open_checkout", "confidence": 0.9}
                        ],
                    }
                )
            return json.dumps(
                {
                    "location_id": "shopping",
                    "regions": [
                        {
                            "actions": [
                                {"intent": "sort_products", "confidence": 0.9},
                                {"intent": "filter_products", "confidence": 0.8},
                            ]
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "observable_change": True,
                "visual_change_kind": "state_indicator",
                "semantic_evidence": ["The cart count changed from zero to one."],
            }
        )

    adapter = _ScopedAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="scoped"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=provider,
        exploration_limits=ExplorationLimits(),
    )

    asyncio.run(explorer.explore_one_step())
    second = asyncio.run(explorer.explore_one_step())

    assert calls.count("initial") == 1
    assert calls.count("targeted") == 1
    assert [action.semantic_id for action in adapter.executed] == [
        "sort_products",
        "open_checkout",
    ]
    memory = LocationExplorationMemory.from_graph(second)
    assert "open_checkout" in memory.pool_for("shopping").candidates


def test_frontier_uses_pending_action_from_shared_location_memory():
    memory = _memory()
    memory.merge_scan("shopping", [_affordance("filter_products")], kind="initial")
    graph = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[],
        meta={LOCATION_EXPLORATION_META_KEY: memory.to_dict()},
    )
    # Keep this fixture small while still representing two Raw Nodes at one location.
    from ai_web_explorer.grounded_web.capability_graph import PageFrame, ExecutionTrace
    from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeEdge, WebKobeNode

    def node(node_id):
        return WebKobeNode(
            node_id=node_id,
            page_description=node_id,
            page_frame=PageFrame(
                page_id=node_id,
                page_type="shopping",
                url="https://fixture.test/shopping",
                url_pattern="https://fixture.test/shopping",
                title="Shopping",
            ),
            state_schema={},
            last_state_snapshot={},
            semantic_location_hint="shopping",
            business_affordances=[_affordance("sort_products"), _affordance("filter_products")],
        )

    edge = WebKobeEdge(
        source_node_id="start",
        target_node_id="after_sort",
        instruction="sort_products",
        action=BrowserAction("click", "#sort", "sort_products"),
        capability=None,
        target_observation="after_sort",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click", "#sort", "sort_products", {}, "start", "after_sort", True
        ),
        status="succeeded_with_observed_change",
    )
    graph = replace(graph, nodes=[node("start"), node("after_sort")], edges=[edge])

    frontier = select_frontier(graph, include_start=True)

    assert frontier is not None
    assert frontier.untried_action_ids == ("filter_products",)
