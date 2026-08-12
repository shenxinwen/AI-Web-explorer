import json

from ai_web_explorer.grounded_web.graph import BusinessAffordance, WebKobeGraph
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
