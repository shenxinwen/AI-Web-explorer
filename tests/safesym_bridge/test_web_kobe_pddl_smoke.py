import json
from pathlib import Path

from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    analyze_web_kobe_pddl_smoke,
    goal_reachable_through_projectable_edges,
)


def _node(node_id: str, values: dict) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description=f"{node_id} page",
        page_frame=PageFrame(
            page_id=f"example:{node_id}",
            page_type=node_id,
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        reference_observation=ReferenceObservation(
            url=f"https://example.test/{node_id}",
            title=node_id,
        ),
        evidence=evidence,
    )


def _edge(
    source: str,
    target: str,
    semantic_id: str,
    *,
    success: bool = True,
    status: str = "succeeded_with_observed_change",
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=semantic_id,
        action=BrowserAction("click", f"#{semantic_id}", semantic_id),
        capability=None,
        target_observation=target,
        observed_delta=[
            ObservedDelta(
                "cart_count",
                0,
                1,
                "state_indicator_change",
                evidence=[Evidence(source="unit_test")],
            )
        ],
        schema_delta={"cart_count": {"before": 0, "after": 1}},
        execution_trace=ExecutionTrace(
            "click",
            f"#{semantic_id}",
            semantic_id,
            {},
            source,
            target,
            success,
        ),
        status=status,
    )


def _graph(edges: list[WebKobeEdge]) -> WebKobeGraph:
    return WebKobeGraph(
        app="local_shop",
        start_node_id="empty",
        total_steps_completed=len(edges),
        nodes=[
            _node("empty", {"cart_count": 0}),
            _node("filled", {"cart_count": 1}),
            _node("checkout", {"cart_count": 1, "checkout_visible": True}),
        ],
        edges=edges,
    )


def test_goal_reachable_through_projectable_edges_uses_successful_edges_only():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    assert goal_reachable_through_projectable_edges(
        graph,
        start_node_id="empty",
        goal_node_id="filled",
    )


def test_goal_reachable_through_projectable_edges_ignores_no_change_edges():
    graph = _graph(
        [
            _edge(
                "empty",
                "filled",
                "add_to_cart",
                success=True,
                status="no_observed_change",
            )
        ]
    )

    assert not goal_reachable_through_projectable_edges(
        graph,
        start_node_id="empty",
        goal_node_id="filled",
    )


def test_analyze_web_kobe_pddl_smoke_reports_planning_ready_graph():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(
        graph,
        goal_node_id="filled",
        domain_path=Path("out/domain.pddl"),
        problem_path=Path("out/problem.pddl"),
    )

    data = report.to_dict()
    assert data["graph_loaded"] is True
    assert data["app"] == "local_shop"
    assert data["start_node"] == "empty"
    assert data["goal_node"] == "filled"
    assert data["goal_reachable_in_graph"] is True
    assert data["projectable_edge_count"] == 1
    assert data["projected_action_count"] == 1
    assert data["projected_predicate_count"] >= 3
    assert data["pddl_static_consistency_ready"] is True
    assert data["undeclared_predicates"] == []
    assert data["planning_ready"] is True
    assert data["failure_reasons"] == []
    assert data["safety_trigger_expected"] is False
    assert "planning-readiness smoke" in data["safety_trigger_reason"]


def test_analyze_web_kobe_pddl_smoke_reports_undeclared_effect_predicates(
    monkeypatch,
):
    from ai_web_explorer.safesym_bridge import web_kobe_pddl_smoke
    from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
        WebKobePddlArtifacts,
    )

    def fake_compile(*args, **kwargs):
        return WebKobePddlArtifacts(
            domain="\n".join(
                [
                    "(define (domain web-kobe)",
                    "  (:requirements :strips)",
                    "  (:predicates",
                    "    (at_empty)",
                    "    (at_filled)",
                    "  )",
                    "  (:action add_to_cart",
                    "    :precondition (and (at_empty))",
                    "    :effect (and (not (at_empty)) (at_filled) "
                    "(cart_count_positive))",
                    "  )",
                    ")",
                ]
            ),
            problem="\n".join(
                [
                    "(define (problem web-kobe-problem)",
                    "  (:domain web-kobe)",
                    "  (:init (at_empty))",
                    "  (:goal (and (at_filled)))",
                    ")",
                ]
            ),
        )

    monkeypatch.setattr(
        web_kobe_pddl_smoke,
        "compile_web_kobe_graph_to_pddl",
        fake_compile,
    )

    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(graph, goal_node_id="filled")

    data = report.to_dict()
    assert data["pddl_static_consistency_ready"] is False
    assert data["undeclared_predicates"] == ["cart_count_positive"]
    assert data["planning_ready"] is False
    assert "domain uses undeclared predicates: cart_count_positive" in data[
        "failure_reasons"
    ]


def test_analyze_web_kobe_pddl_smoke_reports_unreachable_goal():
    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    report = analyze_web_kobe_pddl_smoke(graph, goal_node_id="checkout")

    data = report.to_dict()
    assert data["goal_reachable_in_graph"] is False
    assert data["planning_ready"] is False
    assert "goal is not reachable from start through projectable edges" in data[
        "failure_reasons"
    ]


def test_write_web_kobe_pddl_smoke_writes_pddl_and_report(tmp_path):
    from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
        write_web_kobe_pddl_smoke,
    )

    graph = _graph([_edge("empty", "filled", "add_to_cart")])

    result = write_web_kobe_pddl_smoke(
        graph,
        tmp_path,
        goal_node_id="filled",
    )

    domain_path = tmp_path / "domain.pddl"
    problem_path = tmp_path / "problem.pddl"
    report_path = tmp_path / "smoke_report.json"

    assert domain_path.exists()
    assert problem_path.exists()
    assert report_path.exists()
    assert "(:action add_to_cart" in domain_path.read_text(encoding="utf-8")
    assert "(:goal (and (at_filled)))" in problem_path.read_text(encoding="utf-8")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["planning_ready"] is True
    assert data["domain_path"] == str(domain_path)
    assert data["problem_path"] == str(problem_path)
    assert result.report.planning_ready is True
    assert result.artifacts.domain == domain_path.read_text(encoding="utf-8")
