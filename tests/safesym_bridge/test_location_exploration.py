import json
import asyncio
from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.graph import BusinessAffordance, WebKobeGraph
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.semantic_assistor import DeterministicSemanticAssistor
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.frontier_replay import select_frontier
from ai_web_explorer.grounded_web.location_exploration import (
    CandidatePreflightResult,
    LOCATION_EXPLORATION_META_KEY,
    ExplorationLimits,
    LocationExplorationCoordinator,
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


def test_dependency_records_round_trip_and_schedule_requirements_first():
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "checkout",
        [
            _affordance("fill_billing"),
            _affordance("fill_payment"),
            _affordance("place_order"),
            _affordance("sort_products"),
        ],
        kind="initial",
        requires_by_action_id={
            "fill_billing": [],
            "fill_payment": [],
            "place_order": ["fill_billing", "fill_payment"],
            "sort_products": [],
        },
    )

    pool = memory.pool_for("checkout")
    assert pool.candidates["place_order"].requires == [
        "fill_billing",
        "fill_payment",
    ]
    assert memory.next_candidate("checkout").action_name == "fill_billing"

    memory.record_attempt("checkout", "fill_billing", observable_change=True)
    assert memory.next_candidate("checkout").action_name == "fill_payment"
    memory.record_attempt("checkout", "fill_payment", observable_change=True)
    assert memory.next_candidate("checkout").action_name == "place_order"

    restored = LocationExplorationMemory.from_dict(memory.to_dict())
    restored_record = restored.pool_for("checkout").candidates["place_order"]
    assert restored_record.requires == ["fill_billing", "fill_payment"]
    assert restored.next_candidate("checkout").action_name == "place_order"


def test_failed_requirement_blocks_target_but_leaves_independent_action_eligible():
    memory = LocationExplorationMemory(
        limits=ExplorationLimits(max_action_attempts_per_candidate=1)
    )
    memory.merge_scan(
        "checkout",
        [
            _affordance("fill_billing"),
            _affordance("place_order"),
            _affordance("sort_products"),
        ],
        kind="initial",
        requires_by_action_id={
            "fill_billing": [],
            "place_order": ["fill_billing"],
            "sort_products": [],
        },
    )

    memory.record_attempt(
        "checkout",
        "fill_billing",
        observable_change=False,
        failed=True,
    )

    assert (
        memory.pool_for("checkout").candidates["place_order"].status
        == "blocked_by_failed_requirement"
    )
    assert memory.next_candidate("checkout").action_name == "sort_products"


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


def test_candidate_preflight_accepts_exact_visible_canonical_target():
    coordinator = LocationExplorationCoordinator()
    affordance = BusinessAffordance(
        action_name="add_to_cart",
        target_hint="Add to cart",
    )

    result = coordinator.preflight_candidate(
        affordance,
        [
            {
                "canonical_action_name": "add_to_cart",
                "action_label": "Add to cart",
                "locator": "#add-to-cart",
                "visible": True,
                "enabled": True,
            }
        ],
    )

    assert isinstance(result, CandidatePreflightResult)
    assert result.status == "available"
    assert result.evidence


@pytest.mark.parametrize(
    "interactable",
    [
        {
            "canonical_action_name": "add_to_cart",
            "locator": "#add-to-cart",
            "visible": True,
            "enabled": False,
        },
        {
            "canonical_action_name": "add_to_cart",
            "known": True,
            "present": False,
        },
    ],
)
def test_candidate_preflight_marks_explicitly_disabled_or_absent_target_stale(
    interactable,
):
    coordinator = LocationExplorationCoordinator()
    affordance = BusinessAffordance(action_name="add_to_cart")

    result = coordinator.preflight_candidate(affordance, [interactable])

    assert result.status == "stale"
    assert result.evidence


def test_candidate_preflight_keeps_ambiguous_or_missing_dom_metadata_unknown():
    coordinator = LocationExplorationCoordinator()
    affordance = BusinessAffordance(
        action_name="add_to_cart",
        target_hint="Add to cart",
    )

    ambiguous = coordinator.preflight_candidate(
        affordance,
        [
            {
                "action_label": "Add to cart",
                "locator": "#first",
                "visible": True,
                "enabled": True,
            },
            {
                "action_label": "Add to cart",
                "locator": "#second",
                "visible": True,
                "enabled": True,
            },
        ],
    )
    missing_metadata = coordinator.preflight_candidate(
        affordance,
        [{"canonical_action_name": "add_to_cart", "locator": "#add-to-cart"}],
    )

    assert ambiguous.status == "unknown"
    assert missing_metadata.status == "unknown"


def test_stale_candidate_is_disabled_without_consuming_an_attempt():
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "shopping",
        [BusinessAffordance(action_name="add_to_cart")],
        kind="initial",
    )
    coordinator = LocationExplorationCoordinator(memory=memory)

    selected, result = coordinator.select_candidate(
        "shopping",
        current_interactables=[
            {
                "canonical_action_name": "add_to_cart",
                "known": True,
                "present": False,
            }
        ],
    )

    record = memory.pool_for("shopping").candidates["add_to_cart"]
    assert selected is None
    assert result is not None and result.status == "stale"
    assert record.status == "stale/disabled"
    assert record.attempts == 0


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


class _DisabledCandidateAdapter(_ScopedAdapter):
    async def list_interactables(self, state):
        return [
            {
                "canonical_action_name": "sort_products",
                "known": True,
                "present": False,
            }
        ]


def test_stale_preflight_consumes_zero_formal_action_attempts():
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "shopping",
        [BusinessAffordance(action_name="sort_products")],
        kind="initial",
    )
    explorer = WebKobeExplorer(
        adapter=_DisabledCandidateAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="scoped"),
        location_exploration_coordinator=LocationExplorationCoordinator(memory=memory),
        exploration_limits=ExplorationLimits(),
    )

    graph = asyncio.run(explorer.explore_one_step())

    assert graph.meta["formal_action_attempts"] == 0
    assert graph.meta["last_step_kind"] == "current_state_exhausted"
    assert memory.pool_for("shopping").candidates["sort_products"].status == (
        "stale/disabled"
    )


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
                    "actions": [
                        {
                            "action_id": "sort_products",
                            "description": "Sort visible products",
                            "target": "sort control",
                            "requires": [],
                        },
                        {
                            "action_id": "filter_products",
                            "description": "Filter visible products",
                            "target": "filter control",
                            "requires": [],
                        },
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
