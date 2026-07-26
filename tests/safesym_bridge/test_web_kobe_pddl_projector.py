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
    PddlActionHint,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    PddlProjectionOptions,
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)


def _node(
    node_id: str,
    page_type: str,
    values: dict,
    planning_facts: list[str] | None = None,
    node_label: str | None = None,
) -> WebKobeNode:
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
        node_label=node_label,
        planning_state=(
            PlanningState(active_facts=planning_facts)
            if planning_facts is not None
            else None
        ),
    )


def test_compile_web_kobe_graph_to_pddl_uses_page_and_boolean_delta():
    graph = WebKobeGraph(
        app="example",
        start_node_id="listing_empty",
        total_steps_completed=1,
        nodes=[
            _node("listing_empty", "product_listing", {"cart_has_items": False}),
            _node("listing_nonempty", "product_listing", {"cart_has_items": True}),
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
                        "cart_has_items",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"cart_has_items": {"before": False, "after": True}},
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

    assert "(:action edge_001_add_to_cart_product" in artifacts.domain
    assert "(at_listing_empty)" in artifacts.problem
    assert "(cart_has_items)" in artifacts.domain
    assert "(:goal (and (at_listing_nonempty)))" in artifacts.problem
    assert "(not (at_listing_empty))" in artifacts.domain
    assert "(at_listing_nonempty)" in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_uses_custom_start_node():
    graph = WebKobeGraph(
        app="example",
        start_node_id="landing",
        total_steps_completed=0,
        nodes=[
            _node("landing", "landing", {"cart_has_items": False}),
            _node("cart", "cart", {"cart_has_items": True}),
        ],
        edges=[],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        start_node_id="cart",
        goal_node_id="cart",
    )

    assert "(:init (at_cart) (cart_has_items))" in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_uses_node_label_for_location_predicates():
    graph = WebKobeGraph(
        app="example",
        start_node_id="swag_labs__abc123",
        total_steps_completed=1,
        nodes=[
            _node(
                "swag_labs__abc123",
                "inventory",
                {},
                planning_facts=["logged_in"],
                node_label="inventory",
            ),
            _node(
                "swag_labs__def456",
                "checkout",
                {},
                node_label="checkout_step_one",
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="swag_labs__abc123",
                target_node_id="swag_labs__def456",
                instruction="start checkout",
                action=BrowserAction("business_intent", None, "start_checkout"),
                capability=None,
                target_observation="checkout page",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "start_checkout",
                    {},
                    "swag_labs__abc123",
                    "swag_labs__def456",
                    True,
                ),
                status="succeeded_with_navigation",
            ),
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="swag_labs__def456",
    )

    assert "(at_inventory)" in artifacts.problem
    assert "(:goal (and (at_checkout_step_one)))" in artifacts.problem
    assert "(not (at_inventory))" in artifacts.domain
    assert "(at_checkout_step_one)" in artifacts.domain
    assert "at_swag_labs" not in artifacts.domain
    assert "at_swag_labs" not in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_prefers_planning_state_for_init():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=0,
        nodes=[
            _node(
                "inventory",
                "inventory",
                {"cart_has_items": False, "raw_debug_flag": True},
                planning_facts=["logged_in", "product_list_visible"],
            ),
        ],
        edges=[],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="inventory",
    )

    assert "(:init (at_inventory) (logged_in) (product_list_visible))" in (
        artifacts.problem
    )
    assert "raw_debug_flag" not in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_can_use_profile_fact_goal():
    graph = WebKobeGraph(
        app="example",
        start_node_id="review",
        total_steps_completed=1,
        nodes=[
            _node("review", "review", {}, planning_facts=["order_review_ready"]),
            _node("complete", "complete", {}, planning_facts=["order_completed"]),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="review",
                target_node_id="complete",
                instruction="complete order",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="complete_order",
                ),
                capability=None,
                target_observation="complete",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "review",
                    "complete",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["order_completed"],
                    candidate_removed_facts=["order_review_ready"],
                    evidence=["confirmation page displayed"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="complete",
        goal_fact="order_completed",
    )

    assert "(:goal (and (order_completed)))" in artifacts.problem
    assert "(:goal (and (at_complete)))" not in artifacts.problem
    assert "(order_completed)" in artifacts.domain


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

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="filled",
        options=PddlProjectionOptions(include_observed_delta_facts=True),
    )

    assert "(cart_count_positive)" in artifacts.domain
    assert (
        ":effect (and (not (at_empty)) (at_filled) (cart_count_positive))"
        in artifacts.domain
    )
    assert "(cart_count_positive)" not in artifacts.problem


def test_compile_web_kobe_graph_to_pddl_does_not_project_observed_control_facts_by_default():
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
                planning_delta=PlanningDelta(
                    candidate_added_facts=["checkout_started"],
                    evidence=["checkout page became visible"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")

    assert "(checkout_started)" in artifacts.domain
    assert "control_place_order_enabled" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_can_include_observed_facts_for_diagnostics():
    graph = WebKobeGraph(
        app="example",
        start_node_id="cart",
        total_steps_completed=1,
        nodes=[
            _node("cart", "cart", {}),
            _node("checkout", "checkout", {}),
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

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="checkout",
        options=PddlProjectionOptions(include_observed_delta_facts=True),
    )

    assert "(control_place_order_enabled)" in artifacts.domain


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

    assert "(:action edge_001_cart_open" in artifacts.domain
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
                    candidate_added_facts=[
                        "order_place_pending_sensitive",
                        "order_review_ready",
                    ],
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
    assert "(order_review_ready) (order_review_ready)" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_prefers_pddl_action_hint_name():
    graph = WebKobeGraph(
        app="example",
        start_node_id="review",
        total_steps_completed=1,
        nodes=[
            _node("review", "checkout_overview", {"order_created": False}),
            _node("complete", "checkout_complete", {"order_created": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="review",
                target_node_id="complete",
                instruction="finish order",
                action=BrowserAction("click", "button", "click_finish_button"),
                capability=None,
                target_observation="checkout complete",
                observed_delta=[
                    ObservedDelta(
                        "order_created",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"order_created": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button",
                    "Finish",
                    {},
                    "review",
                    "complete",
                    True,
                ),
                pddl_hint=PddlActionHint(action_name="submit_final_order"),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="complete")

    assert "(:action edge_001_submit_final_order" in artifacts.domain
    assert "(:action click_finish_button" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_maps_order_completion_for_safesym():
    graph = WebKobeGraph(
        app="example",
        start_node_id="checkout_overview",
        total_steps_completed=1,
        nodes=[
            _node("checkout_overview", "checkout_overview", {"order_created": False}),
            _node("checkout_complete", "checkout_complete", {"order_created": True}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="checkout_overview",
                target_node_id="checkout_complete",
                instruction="finish checkout",
                action=BrowserAction(
                    "click",
                    "button",
                    "stagehand_000_click_finish_button_on_checkout_overview",
                ),
                capability=None,
                target_observation="checkout complete",
                observed_delta=[
                    ObservedDelta(
                        "order_created",
                        False,
                        True,
                        "state_indicator_change",
                        evidence=[Evidence(source="unit_test")],
                    )
                ],
                schema_delta={"order_created": {"before": False, "after": True}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button",
                    "Finish",
                    {},
                    "checkout_overview",
                    "checkout_complete",
                    True,
                ),
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(
        graph,
        goal_node_id="checkout_complete",
    )

    assert "(:action edge_001_order_place_confirm" in artifacts.domain
    assert "(:action stagehand_000_click_finish_button_on_checkout_overview" not in (
        artifacts.domain
    )
    assert "(order_created)" in artifacts.domain


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

    assert "(:action edge_001_go_success" in artifacts.domain
    assert "(:action go_failed" not in artifacts.domain
    assert "(:action go_no_change" not in artifacts.domain
    assert "(:action go_unexpected" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_prefers_business_canonical_action_name():
    graph = WebKobeGraph(
        app="example",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[
            _node("start", "before", {}),
            _node("done", "after", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="start",
                target_node_id="done",
                instruction="advance one business milestone",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="submit_application",
                ),
                capability=None,
                target_observation="after",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "start",
                    "done",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="done")

    assert "(:action edge_001_submit_application" in artifacts.domain
    assert "(:action stagehand_business_milestone_001" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_ignores_ui_level_canonical_action_name():
    graph = WebKobeGraph(
        app="example",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[
            _node("start", "before", {}),
            _node("done", "after", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="start",
                target_node_id="done",
                instruction="advance one business milestone",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="click_submit_button",
                ),
                capability=None,
                target_observation="after",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "start",
                    "done",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="done")

    assert "(:action edge_001_stagehand_business_milestone_001" in artifacts.domain
    assert "(:action click_submit_button" not in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_makes_duplicate_readable_names_unique():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=2,
        nodes=[
            _node("inventory", "inventory", {}),
            _node("cart", "cart", {}),
            _node("checkout", "checkout", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="advance_business_milestone",
                ),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                status="succeeded_with_observed_change",
            ),
            WebKobeEdge(
                source_node_id="cart",
                target_node_id="checkout",
                instruction="start checkout",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_002",
                    canonical_action_name="advance_business_milestone",
                ),
                capability=None,
                target_observation="checkout",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_002",
                    {},
                    "cart",
                    "checkout",
                    True,
                ),
                status="succeeded_with_observed_change",
            ),
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="checkout")

    assert "(:action edge_001_advance_business_milestone" in artifacts.domain
    assert "(:action edge_002_advance_business_milestone" in artifacts.domain
    assert artifacts.domain.count("(:action advance_business_milestone") == 0


def test_compile_web_kobe_graph_to_pddl_requires_removed_planning_facts():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=2,
        nodes=[
            _node("inventory", "inventory", {}),
            _node("cart", "cart", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="open_cart",
                ),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["cart_page_visible"],
                    candidate_removed_facts=["product_list_visible"],
                    evidence=["cart page replaced product list"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="cart")

    assert (
        ":precondition (and (at_inventory) (product_list_visible))" in artifacts.domain
    )
    assert "(not (product_list_visible))" in artifacts.domain


def test_compile_web_kobe_graph_to_pddl_omits_delete_for_inactive_planning_fact():
    graph = WebKobeGraph(
        app="example",
        start_node_id="inventory",
        total_steps_completed=1,
        nodes=[
            _node("inventory", "inventory", {}, planning_facts=["cart_has_items"]),
            _node("cart", "cart", {}, planning_facts=["cart_has_items"]),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="inventory",
                target_node_id="cart",
                instruction="open cart",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    canonical_action_name="open_cart",
                ),
                capability=None,
                target_observation="cart",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "stagehand_business_milestone_001",
                    {},
                    "inventory",
                    "cart",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["cart_page_visible"],
                    candidate_removed_facts=["product_list_visible"],
                    evidence=["cart page replaced product list"],
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )

    artifacts = compile_web_kobe_graph_to_pddl(graph, goal_node_id="cart")

    assert "product_list_visible" not in artifacts.domain
    assert "(cart_page_visible)" in artifacts.domain


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
            _node("empty", "listing", {"cart_has_items": False}),
            _node("filled", "listing", {"cart_has_items": True}),
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
                    candidate_added_facts=["cart_has_items"],
                    verified_added_facts=["cart_has_items"],
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
    assert loaded.edges[0].planning_delta.verified_added_facts == ["cart_has_items"]


def test_load_web_kobe_graph_json_preserves_node_planning_state(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="filled",
        total_steps_completed=0,
        nodes=[
            _node(
                "filled",
                "listing",
                {},
                planning_facts=["cart_has_items", "product_list_visible"],
            ),
        ],
        edges=[],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.nodes[0].planning_state is not None
    assert loaded.nodes[0].planning_state.active_facts == [
        "cart_has_items",
        "product_list_visible",
    ]


def test_load_web_kobe_graph_json_preserves_pddl_action_hint(tmp_path):
    graph = WebKobeGraph(
        app="example",
        start_node_id="review",
        total_steps_completed=1,
        nodes=[
            _node("review", "checkout_overview", {}),
            _node("complete", "checkout_complete", {}),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="review",
                target_node_id="complete",
                instruction="place order",
                action=BrowserAction("click", "button", "click_finish"),
                capability=None,
                target_observation="complete",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "button",
                    "Finish",
                    {},
                    "review",
                    "complete",
                    True,
                ),
                pddl_hint=PddlActionHint(action_name="order_place_confirm"),
            )
        ],
    )
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    loaded = load_web_kobe_graph_json(path)

    assert loaded.edges[0].pddl_hint is not None
    assert loaded.edges[0].pddl_hint.action_name == "order_place_confirm"
