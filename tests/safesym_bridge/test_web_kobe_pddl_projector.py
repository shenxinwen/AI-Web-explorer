import json

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
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
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


def test_compile_web_kobe_graph_to_pddl_declares_predicates_from_effect_deltas():
    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {"cart_visible": True}),
            _node("checkout", "checkout", {"cart_visible": False}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="begin checkout",
                action=BrowserAction("click", "#checkout", "begin_checkout"),
                capability=None,
                target_observation="checkout page",
                observed_delta=[
                    ObservedDelta(
                        "control_place_order_enabled",
                        None,
                        True,
                        "control_availability_changed",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "#checkout",
                    "checkout",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")
    predicate_block = artifacts.domain.split("  (:predicates", 1)[1].split(
        "  (:action",
        1,
    )[0]

    assert "\n    (control_place_order_enabled)\n" in predicate_block
    assert (
        ":effect (and (not (at_cart)) (at_checkout) "
        "(control_place_order_enabled))" in artifacts.domain
    )


def test_compile_web_kobe_graph_to_pddl_projects_successful_navigation_edges():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=1,
        nodes=[
            _node("inventory", "inventory", {"cart_count": 1}),
            _node("cart", "cart", {"cart_count": 1}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction("click", ".cart", "cart_open"),
                capability=None,
                target_observation="cart page",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    ".cart",
                    "cart",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                status="succeeded_with_navigation",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="cart")

    assert "(:action cart_open" in artifacts.domain
    assert ":precondition (and (at_inventory))" in artifacts.domain
    assert ":effect (and (not (at_inventory)) (at_cart))" in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_trusts_candidate_planning_delta():
    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {"raw_cart_count": 1}),
            _node("review", "review", {"raw_cart_count": 1}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="review",
                instruction="continue to review",
                action=BrowserAction("click", "button.continue", "continue_to_review"),
                capability=None,
                target_observation="order review",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.continue",
                    "continue",
                    {},
                    "cart",
                    "review",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["order_place_pending_sensitive"],
                    candidate_removed_facts=["checkout_started"],
                    verified_added_facts=["order_review_ready"],
                    verified_removed_facts=["checkout_info_complete"],
                    evidence=["structured review evidence confirmed order review"],
                    confidence=0.88,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="review")

    assert "(order_review_ready)" in artifacts.domain
    assert "(checkout_info_complete)" in artifacts.domain
    assert "(order_place_pending_sensitive)" in artifacts.domain
    assert "(checkout_started)" in artifacts.domain
    assert "(order_review_ready)" in artifacts.domain
    assert "(not (checkout_info_complete))" in artifacts.domain
    assert "(order_place_pending_sensitive)" in artifacts.domain
    assert "(not (checkout_started))" in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_deduplicates_repeated_effects():
    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {"checkout_started": False}),
            _node("checkout", "checkout", {"checkout_started": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="start checkout",
                action=BrowserAction("click", "button.checkout", "start_checkout"),
                capability=None,
                target_observation="checkout info",
                observed_delta=[
                    ObservedDelta(
                        "checkout_started",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={
                    "checkout_started": {"before": False, "after": True}
                },
                execution_trace=ExecutionTrace(
                    "click",
                    "button.checkout",
                    "checkout",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["checkout_started"],
                    verified_added_facts=["checkout_started"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")

    assert artifacts.domain.count("(checkout_started)") == 2


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


def test_load_web_kobe_graph_json_reads_to_dict_output(tmp_path):
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
    path = tmp_path / "web_kobe_graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.app == "example"
    assert loaded.start_node_id == "empty"
    assert loaded.nodes[1].last_state_snapshot == {"cart_count": 1}
    assert loaded.edges[0].action.semantic_id == "add_to_cart"
    assert loaded.edges[0].execution_trace.success is True


def test_load_web_kobe_graph_json_preserves_execution_trace_metadata(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="login",
        total_steps_completed=1,
        nodes=[
            _node("login", "login", {"is_logged_in": False}),
            _node("inventory", "inventory", {"is_logged_in": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="login",
                target_node_id="inventory",
                instruction="log in",
                action=BrowserAction("click", "#login-button", "stagehand_login"),
                capability=None,
                target_observation="inventory page",
                observed_delta=[
                    ObservedDelta(
                        "is_logged_in",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"is_logged_in": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "#login-button",
                    "stagehand_login",
                    {},
                    "login",
                    "inventory",
                    True,
                    metadata={"action_source": "stagehand"},
                ),
            )
        ],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.edges[0].execution_trace.metadata == {"action_source": "stagehand"}


def test_load_web_kobe_graph_json_preserves_planning_delta(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            _node("empty", "listing", {"cart_nonempty": False}),
            _node("filled", "listing", {"cart_nonempty": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["cart_nonempty"],
                    verified_added_facts=["cart_nonempty"],
                    evidence=["cart count indicates one or more items"],
                    confidence=0.9,
                ),
            )
        ],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.edges[0].planning_delta is not None
    assert loaded.edges[0].planning_delta.verified_added_facts == ["cart_nonempty"]
