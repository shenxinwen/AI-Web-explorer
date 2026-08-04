from dataclasses import replace

from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager


def _node(node_id: str, values: dict, interactables=None) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description="product listing",
        page_frame=PageFrame(
            page_id="example:inventory",
            page_type="product_listing",
            url="https://example.test/inventory",
            url_pattern="https://example.test/inventory",
            title="Inventory",
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        interactable_elements=interactables or [],
        reference_observation=ReferenceObservation(
            url="https://example.test/inventory",
            title="Inventory",
        ),
        evidence=evidence,
    )


def test_identify_or_add_node_merges_schema_and_visit_count():
    manager = WebKobeGraphManager(app="example")

    first = _node("product_listing", {"cart_has_items": False})
    second = _node("product_listing", {"cart_has_items": True, "filter_open": False})

    assert manager.identify_or_add_node(first) == "product_listing"
    assert manager.identify_or_add_node(second) == "product_listing"

    graph = manager.to_graph()
    node = graph.nodes[0]
    assert node.visit_count == 2
    assert node.state_schema["cart_has_items"] == [False, True]
    assert node.state_schema["filter_open"] == [False]
    assert node.last_state_snapshot == {"cart_has_items": True, "filter_open": False}


def test_identify_or_add_node_keeps_existing_business_frontier_on_revisit():
    manager = WebKobeGraphManager(app="example")
    first = replace(
        _node("cart_with_items", {"cart_has_items": True}),
        business_affordances=[
            BusinessAffordance("view_cart"),
            BusinessAffordance("proceed_to_checkout"),
        ],
    )
    revisit = replace(
        _node("cart_with_items", {"cart_has_items": True}),
        business_affordances=[
            BusinessAffordance("add_to_cart"),
            BusinessAffordance("sort_products"),
        ],
    )

    manager.identify_or_add_node(first)
    manager.identify_or_add_node(revisit)

    graph = manager.to_graph()
    assert [
        affordance.action_name for affordance in graph.nodes[0].business_affordances
    ] == ["view_cart", "proceed_to_checkout"]


def test_add_edge_merges_planning_transition_for_repeated_edge():
    manager = WebKobeGraphManager(app="example")
    edge = WebKobeEdge(
        source_node_id="inventory",
        target_node_id="cart",
        instruction="open cart",
        action=BrowserAction("business_intent", None, "open_cart"),
        capability=None,
        target_observation="cart page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "open_cart",
            {},
            "inventory",
            "cart",
            True,
        ),
    )

    manager.add_edge(edge)
    manager.add_edge(
        WebKobeEdge(
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            instruction=edge.instruction,
            action=edge.action,
            capability=edge.capability,
            target_observation=edge.target_observation,
            observed_delta=[],
            schema_delta={},
            execution_trace=edge.execution_trace,
            planning_transition=PlanningTransition(
                pre_facts=["cart_has_items"],
                added_facts=["checkout_started"],
                removed_facts=[],
                post_facts=["cart_has_items", "checkout_started"],
            ),
        )
    )

    graph = manager.to_graph(start_node_id="inventory")

    assert graph.edges[0].visit_count == 2
    assert graph.edges[0].planning_transition is not None
    assert graph.edges[0].planning_transition.pre_facts == ["cart_has_items"]


def test_propagate_planning_state_records_profile_and_generated_facts():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node("inventory", {}, interactables=[]),
    )
    manager.identify_or_add_node(_node("cart", {}, interactables=[]))
    edge = WebKobeEdge(
        source_node_id="inventory",
        target_node_id="cart",
        instruction="open cart",
        action=BrowserAction("business_intent", None, "open_cart"),
        capability=None,
        target_observation="cart page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "open_cart",
            {},
            "inventory",
            "cart",
            True,
        ),
        planning_delta=PlanningDelta(
            candidate_added_facts=["cart_page_visible", "made_up_fact"],
            profile_fact_ids=["cart_page_visible"],
            generated_fact_ids=["made_up_fact"],
        ),
    )

    updated_edge = manager.propagate_planning_state(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    graph = manager.to_graph(start_node_id="inventory")
    cart = next(node for node in graph.nodes if node.node_id == "cart")
    assert cart.planning_state is not None
    assert cart.planning_state.active_facts == ["cart_page_visible", "made_up_fact"]
    assert cart.planning_state.profile_fact_ids == ["cart_page_visible"]
    assert cart.planning_state.generated_fact_ids == ["made_up_fact"]
    assert updated_edge.planning_transition is not None
    assert updated_edge.planning_transition.pre_facts == []
    assert updated_edge.planning_transition.added_facts == [
        "cart_page_visible",
        "made_up_fact",
    ]
    assert updated_edge.planning_transition.removed_facts == []
    assert updated_edge.planning_transition.post_facts == [
        "cart_page_visible",
        "made_up_fact",
    ]


def test_propagate_planning_state_omits_already_active_added_facts():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("products", {}, interactables=[]))
    manager.identify_or_add_node(_node("products_after", {}, interactables=[]))
    manager._nodes["products"] = replace(
        manager._nodes["products"],
        planning_state=PlanningState(active_facts=["cart_has_items"]),
    )
    edge = WebKobeEdge(
        source_node_id="products",
        target_node_id="products_after",
        instruction="add another item",
        action=BrowserAction("business_intent", None, "add_item_to_cart"),
        capability=None,
        target_observation="products page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "add_item_to_cart",
            {},
            "products",
            "products_after",
            True,
        ),
        planning_delta=PlanningDelta(candidate_added_facts=["cart_has_items"]),
    )

    updated_edge = manager.propagate_planning_state(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    assert updated_edge.planning_transition is not None
    assert updated_edge.planning_transition.pre_facts == ["cart_has_items"]
    assert updated_edge.planning_transition.added_facts == []
    assert updated_edge.planning_transition.post_facts == ["cart_has_items"]
