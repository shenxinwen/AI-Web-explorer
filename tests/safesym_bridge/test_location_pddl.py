from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_domain
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_problem
from ai_web_explorer.safesym_bridge import location_pddl


def _node(node_id: str, label: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        node_label=label,
        page_description=label,
        page_frame=PageFrame(
            page_id=node_id,
            page_type="generic",
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=label,
        ),
        state_schema={},
        last_state_snapshot={},
    )


def _edge(
    source: str,
    action: str,
    target: str,
    *,
    status: str = "verified",
    success: bool = True,
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action,
        action=BrowserAction(
            "business_intent",
            None,
            action,
            canonical_action_name=action,
        ),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            action,
            {},
            source,
            target,
            success,
        ),
        status=status,
    )


def _graph_with_cross_self_failed_and_missing_edges() -> WebKobeGraph:
    nodes = [_node("raw-home", "Home"), _node("raw-details", "Details")]
    return WebKobeGraph(
        app="generic_site",
        start_node_id="raw-home",
        total_steps_completed=4,
        nodes=nodes,
        edges=[
            _edge("raw-home", "open_details", "raw-details"),
            _edge("raw-home", "refresh", "raw-home"),
            _edge(
                "raw-details",
                "failed_action",
                "raw-home",
                status="failed_execution",
                success=False,
            ),
            _edge("raw-details", "open_missing", "raw-missing"),
        ],
    )


def _three_location_graph() -> WebKobeGraph:
    return WebKobeGraph(
        app="generic_site",
        start_node_id="home-id",
        total_steps_completed=2,
        nodes=[
            _node("home-id", "Home"),
            _node("details-id", "Details"),
            _node("done-id", "Done"),
        ],
        edges=[
            _edge("home-id", "open_details", "details-id"),
            _edge("details-id", "finish", "done-id"),
        ],
    )


def _graph_with_disconnected_goal() -> WebKobeGraph:
    return WebKobeGraph(
        app="generic_site",
        start_node_id="home-id",
        total_steps_completed=0,
        nodes=[_node("home-id", "Home"), _node("isolated-id", "Isolated")],
        edges=[],
    )


def test_compile_location_domain_uses_one_typed_location_predicate():
    graph = WebKobeGraph(
        app="generic_site",
        start_node_id="raw-home",
        total_steps_completed=1,
        nodes=[_node("raw-home", "Home"), _node("raw-details", "Details")],
        edges=[_edge("raw-home", "open_details", "raw-details")],
    )

    result = compile_location_domain(graph)

    assert "(:types location)" in result.domain
    assert "(at ?location - location)" in result.domain
    assert "home - location" in result.domain
    assert "details - location" in result.domain
    assert "(at_home)" not in result.domain
    assert "(:action open_details" in result.domain
    assert "(at home)" in result.domain
    assert "(not (at home))" in result.domain
    assert "(at details)" in result.domain
    assert result.report["schema_version"] == "location-pddl-projection-v1"
    assert result.report["actions"][0]["planning_edge_id"] == graph.edges[0].edge_id


def test_location_domain_is_deterministic_and_reports_excluded_edges():
    base = _graph_with_cross_self_failed_and_missing_edges()
    mappings = [
        {"planning_edge_id": base.edges[0].edge_id, "raw_edge_id": "raw-edge-b"},
        {"planning_edge_id": base.edges[0].edge_id, "raw_edge_id": "raw-edge-a"},
    ]

    first = compile_location_domain(base, edge_mappings=mappings)
    shuffled = replace(
        base,
        nodes=list(reversed(base.nodes)),
        edges=list(reversed(base.edges)),
    )
    second = compile_location_domain(
        shuffled,
        edge_mappings=list(reversed(mappings)),
    )

    assert first.domain == second.domain
    assert first.report == second.report
    assert first.report["actions"][0]["raw_edge_ids"] == [
        "raw-edge-a",
        "raw-edge-b",
    ]
    assert {item["reason"] for item in first.report["excluded_edges"]} == {
        "planning_self_loop",
        "unverified_transition",
        "missing_location_reference",
    }


def test_location_domain_does_not_project_fact_or_visual_fields():
    base = _graph_with_cross_self_failed_and_missing_edges()
    edge = base.edges[0]
    enriched_action = replace(
        edge.action,
        supporting_facts=["cart_has_items"],
    )
    enriched_edge = replace(
        edge,
        action=enriched_action,
        visual_change_kind="content",
    )
    graph = replace(base, edges=[enriched_edge, *base.edges[1:]])

    result = compile_location_domain(graph)

    assert "cart_has_items" not in result.domain
    assert "content" not in result.domain
    assert "supporting" not in result.domain


def test_compile_location_problem_uses_explicit_reachable_nodes():
    result = compile_location_problem(
        _three_location_graph(),
        start_node_id="home-id",
        goal_node_id="details-id",
    )

    assert "(:domain web_kobe_location)" in result.problem
    assert "(:init (at home))" in result.problem
    assert "(:goal (at details))" in result.problem


def test_compile_location_problem_rejects_unreachable_goal():
    with pytest.raises(ValueError, match="goal_unreachable"):
        compile_location_problem(
            _graph_with_disconnected_goal(),
            start_node_id="home-id",
            goal_node_id="isolated-id",
        )


@pytest.mark.parametrize(
    ("labels", "action"),
    [
        (("catalog", "details"), "open_item"),
        (("documents", "editor"), "open_document"),
        (("meeting_list", "meeting_room"), "join_meeting"),
    ],
)
def test_location_compiler_is_domain_agnostic(labels, action):
    graph = WebKobeGraph(
        app="generic_site",
        start_node_id="source",
        total_steps_completed=1,
        nodes=[_node("source", labels[0]), _node("target", labels[1])],
        edges=[_edge("source", action, "target")],
    )

    result = compile_location_domain(graph)

    assert "(at ?location - location)" in result.domain
    assert f"(:action {action}" in result.domain
    assert "cart_has_items" not in result.domain


def test_location_compiler_has_no_domain_action_rules():
    source = Path(location_pddl.__file__).read_text(encoding="utf-8").lower()
    for token in ("checkout", "cart", "login", "search", "filter", "payment"):
        assert token not in source
from dataclasses import replace
