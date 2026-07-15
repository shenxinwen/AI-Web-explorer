import pytest

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
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
)


def _node(node_id: str, page_type: str, values: dict) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description=f"{page_type} page",
        page_frame=PageFrame(
            page_id=f"example:{page_type}",
            page_type=page_type,
            url=f"https://example.test/{page_type}",
            url_pattern=f"https://example.test/{page_type}",
            title=page_type,
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        reference_observation=ReferenceObservation(
            url=f"https://example.test/{page_type}",
            title=page_type,
        ),
        evidence=evidence,
    )


def test_compile_web_kobe_graph_to_pddl_uses_page_and_boolean_delta():
    graph = WebKobeGraph(
        app="example",
        start_node_id="listing_empty",
        total_steps_completed=1,
        nodes=[
            _node("listing_empty", "product_listing", {"cart_nonempty": False}),
            _node("listing_nonempty", "product_listing", {"cart_nonempty": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="listing_empty",
                target_node_id="listing_nonempty",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart_product"),
                capability=None,
                target_observation="product listing page",
                observed_delta=[
                    ObservedDelta(
                        "cart_nonempty",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"cart_nonempty": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "product",
                    {},
                    "listing_empty",
                    "listing_nonempty",
                    True,
                ),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="listing_nonempty",
    )

    assert "(:action add_to_cart_product" in artifacts.domain
    assert "(at_listing_empty)" in artifacts.problem
    assert "(cart_nonempty)" in artifacts.domain
    assert "(:goal (and (at_listing_nonempty)))" in artifacts.problem
    assert "(not (at_listing_empty))" in artifacts.domain
    assert "(at_listing_nonempty)" in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_uses_custom_start_node():
    graph = WebKobeGraph(
        app="example",
        start_node_id="landing",
        total_steps_completed=0,
        nodes=[
            _node("landing", "landing", {"cart_nonempty": False}),
            _node("cart", "cart", {"cart_nonempty": True}),
        ],
        edges=[],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id="cart",
        goal_node_id="cart",
    )

    assert "(:init (at_cart) (cart_nonempty))" in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_rejects_missing_goal_node():
    graph = WebKobeGraph(
        app="example",
        start_node_id="landing",
        total_steps_completed=0,
        nodes=[_node("landing", "landing", {})],
        edges=[],
    )

    with pytest.raises(ValueError, match="Unknown goal node"):
        compile_web_kobe_graph_to_pddl(graph, goal_node_id="missing")


def test_compile_web_kobe_graph_to_pddl_projects_positive_numeric_facts():
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            _node("empty", "listing", {"cart_count": 0}),
            _node("filled", "listing", {"cart_count": 1}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
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
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="filled")

    assert "(cart_count_positive)" in artifacts.domain
    assert (
        ":effect (and (not (at_empty)) (at_filled) (cart_count_positive))"
        in artifacts.domain
    )
    assert "(cart_count_positive)" not in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_excludes_non_projectable_edges():
    nodes = [
        _node("start", "start", {}),
        _node("success", "success", {}),
        _node("failed", "failed", {}),
        _node("no_change", "no_change", {}),
        _node("unexpected", "unexpected", {}),
    ]

    def edge(target: str, semantic_id: str, success: bool, status: str) -> WebKobeEdge:
        return WebKobeEdge(
            source_node_id="start",
            target_node_id=target,
            instruction=semantic_id,
            action=BrowserAction("click", f"#{semantic_id}", semantic_id),
            capability=None,
            target_observation=target,
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click",
                f"#{semantic_id}",
                semantic_id,
                {},
                "start",
                target,
                success,
            ),
            status=status,
        )

    graph = WebKobeGraph(
        app="example",
        start_node_id="start",
        total_steps_completed=4,
        nodes=nodes,
        edges=[
            edge("success", "go_success", True, "succeeded_with_observed_change"),
            edge("failed", "go_failed", False, "failed_execution"),
            edge("no_change", "go_no_change", True, "no_observed_change"),
            edge("unexpected", "go_unexpected", True, "unexpected_change"),
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="success")

    assert "(:action go_success" in artifacts.domain
    assert "(:action go_failed" not in artifacts.domain
    assert "(:action go_no_change" not in artifacts.domain
    assert "(:action go_unexpected" not in artifacts.domain
