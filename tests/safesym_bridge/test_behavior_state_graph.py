import pytest

from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.capability_graph import (
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.behavior_state_graph import (
    consolidate_behavior_state_graph,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_phase_a_domain,
)


def _node(node_id: str, affordances=(), *, planning_facts=()) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        node_label=node_id,
        business_affordances=list(affordances),
        planning_state=(
            PlanningState(active_facts=list(planning_facts))
            if planning_facts
            else None
        ),
    )


def _edge(source: str, target: str, action_name: str, *, status="succeeded"):
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_name,
        action=BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id=action_name,
            canonical_action_name=action_name,
            supporting_facts=["visible_control"],
        ),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            concrete_action_kind="business_intent",
            concrete_locator=None,
            concrete_target_sample=action_name,
            input_values_used={},
            before_observation_id=source,
            after_observation_id=target,
            success=status != "failed_execution",
            error="failed" if status == "failed_execution" else None,
        ),
        status=status,
    )


def _graph(nodes, edges, *, start_node_id=None):
    return WebKobeGraph(
        app="example",
        start_node_id=start_node_id or nodes[0].node_id,
        total_steps_completed=len(edges),
        nodes=list(nodes),
        edges=list(edges),
    )


def test_consolidation_normalizes_high_confidence_actions_with_embedding_provider():
    search_products = BusinessAffordance(
        "search_products",
        label="Find products",
        target_hint="search box",
    )
    search_items = BusinessAffordance(
        "search_items",
        label="Find items",
        target_hint="search box",
    )
    graph = _graph(
        [
            _node("list_a", [search_items]),
            _node("list_b", [search_products]),
            _node("results_a"),
            _node("results_b"),
        ],
        [
            _edge("list_a", "results_a", "search_items"),
            _edge("list_b", "results_b", "search_products"),
        ],
    )

    seen_texts = []

    def embed(text):
        seen_texts.append(text)
        if "search" in text or "Find" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    artifacts = consolidate_behavior_state_graph(
        graph,
        embedding_provider=embed,
    )

    assert artifacts.raw_graph is graph
    assert any("search_items" in text and "search box" in text for text in seen_texts)
    assert artifacts.report.to_dict()["action_normalizations"] == [
        {
            "raw_action_names": ["search_items", "search_products"],
            "canonical_action_name": "search_items",
            "confidence": "high",
        }
    ]
    assert artifacts.report.to_dict()["raw_to_canonical_node"] == {
        "list_a": "list_a",
        "list_b": "list_a",
        "results_a": "results_a",
        "results_b": "results_a",
    }


def test_consolidation_without_embedding_provider_keeps_synonyms_separate():
    graph = _graph(
        [
            _node("list_a", [BusinessAffordance("search_items")]),
            _node("list_b", [BusinessAffordance("search_products")]),
            _node("results_a"),
            _node("results_b"),
        ],
        [
            _edge("list_a", "results_a", "search_items"),
            _edge("list_b", "results_b", "search_products"),
        ],
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert artifacts.report.to_dict()["action_normalizations"] == []
    assert artifacts.report.to_dict()["raw_to_canonical_node"]["list_a"] == "list_a"
    assert artifacts.report.to_dict()["raw_to_canonical_node"]["list_b"] == "list_b"


def test_consolidation_does_not_merge_different_actions_with_embedding_provider():
    graph = _graph(
        [
            _node(
                "search_page",
                [BusinessAffordance("search_items", label="Search", target_hint="box")],
            ),
            _node(
                "sort_page",
                [BusinessAffordance("sort_items", label="Sort", target_hint="menu")],
            ),
            _node("search_results"),
            _node("sorted_results"),
        ],
        [
            _edge("search_page", "search_results", "search_items"),
            _edge("sort_page", "sorted_results", "sort_items"),
        ],
    )

    def embed(text):
        return [1.0, 0.0] if "search" in text.lower() else [0.0, 1.0]

    report = consolidate_behavior_state_graph(
        graph,
        embedding_provider=embed,
    ).report.to_dict()

    assert report["raw_to_canonical_node"]["search_page"] == "search_page"
    assert report["raw_to_canonical_node"]["sort_page"] == "sort_page"


def test_consolidation_rejects_incomplete_and_failed_frontiers():
    graph = _graph(
        [
            _node("incomplete", [BusinessAffordance("open_results")]),
            _node("failed", [BusinessAffordance("open_results")]),
        ],
        [_edge("failed", "failed_target", "open_results", status="failed_execution")],
    )
    graph = _graph(
        graph.nodes + [_node("failed_target")],
        graph.edges,
    )

    artifacts = consolidate_behavior_state_graph(graph)
    report = artifacts.report.to_dict()

    assert report["raw_to_canonical_node"]["incomplete"] == "incomplete"
    assert report["raw_to_canonical_node"]["failed"] == "failed"
    assert "frontier_incomplete" in report["rejected_nodes"]["incomplete"]
    assert "failed_execution" in report["rejected_nodes"]["failed"]


def test_consolidation_allows_same_action_to_equivalent_raw_targets():
    graph = _graph(
        [
            _node("source", [BusinessAffordance("open_results")]),
            _node("results_a"),
            _node("results_b"),
        ],
        [
            _edge("source", "results_a", "open_results"),
            _edge("source", "results_b", "open_results"),
        ],
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert "source" not in artifacts.report.rejected_nodes
    source_edges = [
        edge
        for edge in artifacts.canonical_graph.edges
        if edge.source_node_id == "source"
    ]
    assert len(source_edges) == 1


def test_consolidation_rejects_conflicting_target_behavior_groups():
    graph = _graph(
        [
            _node("source", [BusinessAffordance("open_results")]),
            _node("results_a", [BusinessAffordance("back_to_list")]),
            _node("results_b", [BusinessAffordance("start_over")]),
            _node("list_a"),
            _node("list_b"),
        ],
        [
            _edge("source", "results_a", "open_results"),
            _edge("source", "results_b", "open_results"),
            _edge("results_a", "list_a", "back_to_list"),
            _edge("results_b", "list_b", "start_over"),
        ],
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert artifacts.report.rejected_nodes["source"] == [
        "action_target_conflict"
    ]
    assert all(edge.source_node_id != "source" for edge in artifacts.canonical_graph.edges)


@pytest.mark.parametrize(
    ("rejection_reason", "source_affordances", "edges", "extra_nodes"),
    [
        (
            "frontier_incomplete",
            [BusinessAffordance("needed_action")],
            [_edge("source", "target", "different_action")],
            [_node("target")],
        ),
        (
            "failed_execution",
            [BusinessAffordance("open_results")],
            [_edge("source", "target", "open_results", status="failed_execution")],
            [_node("target")],
        ),
        (
            "missing_target_node",
            [BusinessAffordance("open_results")],
            [_edge("source", "missing", "open_results")],
            [],
        ),
    ],
)
def test_consolidation_omits_edges_from_rejected_sources(
    rejection_reason,
    source_affordances,
    edges,
    extra_nodes,
):
    graph = _graph(
        [_node("source", source_affordances), *extra_nodes],
        edges,
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert rejection_reason in artifacts.report.rejected_nodes["source"]
    assert artifacts.raw_graph.edges == graph.edges
    assert artifacts.raw_graph.edges[0].edge_id not in {
        edge.edge_id for edge in artifacts.canonical_graph.edges
    }
    mapping = next(
        item
        for item in artifacts.report.edge_mappings
        if item["raw_edge_id"] == artifacts.raw_graph.edges[0].edge_id
    )
    assert mapping["canonical_edge_id"] is None
    assert mapping["collapsed_into_existing_edge"] is False
    assert mapping["omitted_reason"] == "source_ineligible"


def test_consolidation_keeps_ambiguous_action_chain_identity_mapped():
    graph = _graph(
        [
            _node("a", [BusinessAffordance("action_a")]),
            _node("b", [BusinessAffordance("action_b")]),
            _node("c", [BusinessAffordance("action_c")]),
        ],
        [],
    )

    def embed(text):
        if "action_a" in text:
            return [1.0, 0.0]
        if "action_b" in text:
            return [0.94, 0.342]
        return [0.643, 0.766]

    artifacts = consolidate_behavior_state_graph(
        graph,
        embedding_provider=embed,
    )
    report = artifacts.report.to_dict()

    assert report["ambiguous_actions"] == [
        "action_a",
        "action_b",
        "action_c",
    ]
    assert report["action_normalizations"] == []
    assert {
        action: action
        for node in artifacts.canonical_graph.nodes
        for action in [
            affordance.action_name for affordance in node.business_affordances
        ]
    } == {
        "action_a": "action_a",
        "action_b": "action_b",
        "action_c": "action_c",
    }


def test_consolidation_refines_equivalent_cycles_to_stable_behavior_groups():
    open_results = BusinessAffordance("open_results")
    back_to_list = BusinessAffordance("back_to_list")
    graph = _graph(
        [
            _node("list_one", [open_results]),
            _node("list_two", [open_results]),
            _node("results_one", [back_to_list]),
            _node("results_two", [back_to_list]),
        ],
        [
            _edge("list_one", "results_one", "open_results"),
            _edge("list_two", "results_two", "open_results"),
            _edge("results_one", "list_one", "back_to_list"),
            _edge("results_two", "list_two", "back_to_list"),
        ],
    )

    canonical = consolidate_behavior_state_graph(graph).canonical_graph

    assert [node.node_id for node in canonical.nodes] == ["list_one", "results_one"]
    assert {
        (edge.source_node_id, edge.action.canonical_action_name, edge.target_node_id)
        for edge in canonical.edges
    } == {
        ("list_one", "open_results", "results_one"),
        ("results_one", "back_to_list", "list_one"),
    }


def test_consolidation_merges_two_complete_duplicate_loops():
    graph = _graph(
        [
            _node("list_one", [BusinessAffordance("search")]),
            _node("results_one", [BusinessAffordance("clear")]),
            _node("list_two", [BusinessAffordance("search")]),
            _node("results_two", [BusinessAffordance("clear")]),
        ],
        [
            _edge("list_one", "results_one", "search"),
            _edge("results_one", "list_one", "clear"),
            _edge("list_two", "results_two", "search"),
            _edge("results_two", "list_two", "clear"),
        ],
    )

    artifacts = consolidate_behavior_state_graph(graph)

    assert len(artifacts.raw_graph.nodes) == 4
    assert len(artifacts.canonical_graph.nodes) == 2
    assert artifacts.report.raw_to_canonical_node == {
        "list_one": "list_one",
        "results_one": "results_one",
        "list_two": "list_one",
        "results_two": "results_one",
    }


def test_phase_a_domain_keeps_self_loops_in_graph_but_projects_only_locations():
    graph = _graph(
        [
            _node("listing", [BusinessAffordance("refresh")], planning_facts=("cart_has_items",)),
            _node("details", planning_facts=("product_details_visible",)),
        ],
        [
            _edge("listing", "listing", "refresh", status="no_observed_change"),
            _edge("listing", "details", "view_details"),
        ],
    )
    graph = WebKobeGraph(
        app=graph.app,
        start_node_id=graph.start_node_id,
        total_steps_completed=graph.total_steps_completed,
        nodes=graph.nodes,
        edges=[
            graph.edges[0],
            WebKobeEdge(
                **{
                    **graph.edges[1].__dict__,
                    "observed_delta": [
                        ObservedDelta("cart_has_items", False, True, "fact_change")
                    ],
                }
            ),
        ],
    )

    canonical = consolidate_behavior_state_graph(graph).canonical_graph
    domain = compile_phase_a_domain(canonical)

    assert any(
        edge.source_node_id == edge.target_node_id for edge in canonical.edges
    )
    assert "view_details__from_listing" in domain
    assert "refresh" not in domain
    assert "cart_has_items" not in domain
    assert "product_details_visible" not in domain
    assert "visible_control" not in domain
    assert "(at_listing)" in domain
    assert "(at_details)" in domain
