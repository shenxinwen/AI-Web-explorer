from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
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


def test_mark_interactable_explored_updates_matching_candidate():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node(
            "product_listing",
            {"cart_has_items": False},
            interactables=[
                {
                    "semantic_id": "add_to_cart_product",
                    "description": "Add to cart",
                    "locator": "button.add",
                    "explored": False,
                }
            ],
        )
    )

    manager.mark_interactable_explored("product_listing", "add_to_cart_product")

    graph = manager.to_graph()
    assert graph.nodes[0].interactable_elements[0]["explored"] is True


def test_interactable_merge_preserves_explored_by_locator_when_label_changes():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node(
            "product_listing",
            {"cart_count": 0},
            interactables=[
                {
                    "semantic_id": "button_cart_0",
                    "description": "Cart (0)",
                    "locator": '[data-web-kobe-id="dom_001"]',
                    "explored": False,
                }
            ],
        )
    )

    manager.mark_interactable_explored(
        "product_listing",
        "button_cart_0",
        locator='[data-web-kobe-id="dom_001"]',
    )
    manager.identify_or_add_node(
        _node(
            "product_listing",
            {"cart_count": 1},
            interactables=[
                {
                    "semantic_id": "button_cart_1",
                    "description": "Cart (1)",
                    "locator": '[data-web-kobe-id="dom_001"]',
                    "explored": False,
                }
            ],
        )
    )

    graph = manager.to_graph()

    assert len(graph.nodes[0].interactable_elements) == 1
    assert graph.nodes[0].interactable_elements[0]["explored"] is True


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


def test_propagate_planning_state_filters_to_profile_facts():
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
        ),
    )

    updated_edge = manager.propagate_planning_state(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    graph = manager.to_graph(start_node_id="inventory")
    cart = next(node for node in graph.nodes if node.node_id == "cart")
    assert cart.planning_state is not None
    assert cart.planning_state.active_facts == ["cart_page_visible"]
    assert updated_edge.planning_transition is not None
    assert updated_edge.planning_transition.pre_facts == []
    assert updated_edge.planning_transition.added_facts == ["cart_page_visible"]
    assert updated_edge.planning_transition.removed_facts == []
    assert updated_edge.planning_transition.post_facts == ["cart_page_visible"]
