import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
import ai_web_explorer.safesym_bridge.trace_pddl as trace_pddl
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_domain
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_problem


def _node(node_id: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type="generic",
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
    )


def _edge(
    source: str,
    action: str,
    target: str,
    *,
    status: str = "no_observed_change",
    success: bool = True,
    after_observation_id: str | None = None,
    semantic_id: str | None = None,
    canonical_action_name: str | None = None,
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action,
        action=BrowserAction(
            "business_intent",
            None,
            action if semantic_id is None else semantic_id,
            canonical_action_name=(
                action
                if canonical_action_name is None
                else canonical_action_name
            ),
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
            target if after_observation_id is None else after_observation_id,
            success,
        ),
        status=status,
    )


def _graph(edges: list[WebKobeEdge]) -> WebKobeGraph:
    node_ids = {"page"}
    for edge in edges:
        node_ids.update((edge.source_node_id, edge.target_node_id))
    return WebKobeGraph(
        app="generic_site",
        start_node_id="page",
        total_steps_completed=len(edges),
        nodes=[_node(node_id) for node_id in sorted(node_ids)],
        edges=edges,
    )


def test_trace_domain_projects_successful_self_loops_as_ordered_checkpoints():
    graph = _graph(
        edges=[
            _edge("page", "search_items", "page"),
            _edge("page", "apply_category_filter", "page"),
        ]
    )

    result = compile_trace_domain(graph)

    assert "(:requirements :strips)" in result.domain
    assert ":typing" not in result.domain
    assert ":types" not in result.domain
    assert ":constants" not in result.domain
    assert "(at " not in result.domain
    assert len(result.report["checkpoints"]) == 3
    assert [item["pddl_action"] for item in result.report["actions"]] == [
        "search_items",
        "apply_category_filter",
    ]
    assert "(not (state_initial))" in result.domain
    assert "(state_after_search_items)" in result.domain


def _three_step_trace() -> WebKobeGraph:
    return _graph(
        edges=[
            _edge("page", "open_item", "page"),
            _edge("page", "apply_filter", "page"),
            _edge("page", "open_checkout", "page"),
        ]
    )


def test_trace_problem_uses_explicit_reachable_checkpoints():
    graph = _three_step_trace()
    checkpoints = compile_trace_domain(graph).report["checkpoints"]

    result = compile_trace_problem(
        graph,
        start_checkpoint_id=checkpoints[0]["checkpoint_id"],
        goal_checkpoint_id=checkpoints[-1]["checkpoint_id"],
    )

    assert "(:domain web_kobe_trace)" in result.problem
    assert "(:init (state_initial))" in result.problem
    assert "(:goal (state_after_open_checkout))" in result.problem
    assert result.start_checkpoint == checkpoints[0]["checkpoint_id"]
    assert result.goal_checkpoint == checkpoints[-1]["checkpoint_id"]


def test_trace_problem_rejects_unknown_start_checkpoint():
    with pytest.raises(ValueError, match="unknown_start_checkpoint"):
        compile_trace_problem(
            _three_step_trace(),
            start_checkpoint_id="missing",
            goal_checkpoint_id="checkpoint_000",
        )


def test_trace_problem_rejects_unknown_goal_checkpoint():
    with pytest.raises(ValueError, match="unknown_goal_checkpoint"):
        compile_trace_problem(
            _three_step_trace(),
            start_checkpoint_id="checkpoint_000",
            goal_checkpoint_id="missing",
        )


def test_trace_problem_rejects_goal_earlier_than_selected_start():
    graph = _three_step_trace()
    checkpoints = compile_trace_domain(graph).report["checkpoints"]

    with pytest.raises(ValueError, match="goal_unreachable_in_explored_trace"):
        compile_trace_problem(
            graph,
            start_checkpoint_id=checkpoints[-1]["checkpoint_id"],
            goal_checkpoint_id=checkpoints[0]["checkpoint_id"],
        )


def test_trace_problem_allows_zero_step_query():
    graph = _three_step_trace()
    checkpoint_id = compile_trace_domain(graph).report["checkpoints"][1][
        "checkpoint_id"
    ]

    result = compile_trace_problem(
        graph,
        start_checkpoint_id=checkpoint_id,
        goal_checkpoint_id=checkpoint_id,
    )

    assert f"(:init (state_after_open_item))" in result.problem
    assert f"(:goal (state_after_open_item))" in result.problem


def test_trace_domain_excludes_failed_missing_observation_and_invalid_identity():
    graph = _graph(
        edges=[
            _edge("page", "failed_action", "page", status="failed_execution", success=False),
            _edge("page", "missing_observation", "page", after_observation_id=""),
            _edge(
                "page",
                "",
                "page",
                semantic_id="",
                canonical_action_name=None,
            ),
        ]
    )

    result = compile_trace_domain(graph)

    assert len(result.report["checkpoints"]) == 1
    assert result.report["actions"] == []
    assert [item["reason"] for item in result.report["excluded_edges"]] == [
        "failed_execution",
        "missing_after_observation",
        "invalid_action_identity",
    ]
    assert [item["raw_edge_id"] for item in result.report["excluded_edges"]] == [
        edge.edge_id for edge in graph.edges
    ]


def test_trace_domain_with_no_successful_edges_is_a_legal_initial_only_domain():
    graph = _graph(
        edges=[_edge("page", "failed_action", "page", status="failed_execution", success=False)]
    )

    result = compile_trace_domain(graph)

    assert result.domain.startswith("(define (domain web_kobe_trace)")
    assert result.domain.endswith("\n")
    assert result.domain.count("(state_") == 1
    assert result.report["checkpoints"] == [
        {
            "checkpoint_id": "checkpoint_000",
            "trace_index": 0,
            "pddl_predicate": "state_initial",
            "incoming_raw_edge_id": None,
            "after_observation_id": "page",
        }
    ]


def test_trace_domain_disambiguates_repeated_action_names_with_stable_digest():
    graph = _graph(
        edges=[
            _edge("page", "open_item", "page"),
            _edge("page", "open_item", "page"),
        ]
    )

    first = compile_trace_domain(graph)
    second = compile_trace_domain(graph)
    digest = hashlib.sha256(
        f"{graph.edges[1].edge_id}:2".encode("utf-8")
    ).hexdigest()[:8]

    assert first.domain == second.domain
    assert first.report == second.report
    assert [item["pddl_action"] for item in first.report["actions"]] == [
        "open_item",
        f"open_item__{digest}",
    ]
    assert first.report["checkpoints"][2]["pddl_predicate"] == (
        f"state_after_open_item__{digest}"
    )


def test_trace_domain_ignores_nodes_dom_visual_and_planning_fields():
    graph = _graph([_edge("page", "open_item", "page")])
    enriched_edge = replace(
        graph.edges[0],
        observed_delta=[object()],
        schema_delta={"changed": True},
        planning_delta=object(),
        planning_transition=object(),
        visual_change_kind="content",
    )
    enriched_node = replace(
        graph.nodes[0],
        page_description="different description",
        state_schema={"fields": ["ignored"]},
        last_state_snapshot={"ignored": True},
        node_label="different label",
    )
    enriched = replace(graph, nodes=[enriched_node], edges=[enriched_edge])

    assert compile_trace_domain(graph) == compile_trace_domain(enriched)


def test_trace_domain_is_stable_when_node_and_mapping_key_order_changes():
    graph = _graph(
        edges=[
            _edge("page", "open_item", "page"),
            _edge("page", "close_item", "page"),
        ]
    )
    reordered = replace(graph, nodes=list(reversed(graph.nodes)))

    first = compile_trace_domain(graph)
    second = compile_trace_domain(reordered)

    assert first.domain == second.domain
    assert first.report == second.report


def test_trace_pddl_source_has_no_domain_action_vocabulary():
    source = Path(trace_pddl.__file__).read_text(encoding="utf-8").lower()
    for token in ("checkout", "cart", "login", "search", "filter", "payment"):
        assert token not in source
