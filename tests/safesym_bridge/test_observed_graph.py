from ai_web_explorer.safesym_bridge.observed_graph import (
    InteractableElement,
    WebObservedEdge,
    WebObservedGraph,
    WebObservedNode,
    build_observed_graph,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_web_observed_graph_to_dict_uses_expected_shape():
    graph = WebObservedGraph(
        app="saucedemo",
        start_node="login",
        total_steps_completed=1,
        nodes=[
            WebObservedNode(
                id="inventory",
                page_description="product listing page",
                url_patterns=["/inventory.html"],
                state_schema={"cart_count": "number"},
                observed_values={"cart_count": [0, 1]},
                last_state_snapshot={"cart_count": 1},
                interactable_elements=[
                    InteractableElement(
                        description="shopping cart link",
                        position="top right",
                        explored=True,
                        execution_hints={"selector": ".shopping_cart_link"},
                    )
                ],
                visit_count=2,
            )
        ],
        edges=[
            WebObservedEdge(
                source="inventory",
                target="cart",
                semantic_action="cart_open",
                instructions=["Click the shopping cart link"],
                target_observations=["cart page"],
                schema_deltas=[],
                preconditions=[],
                effects=[],
                visit_count=1,
            )
        ],
    )

    assert graph.to_dict() == {
        "meta": {
            "schema_version": "web-observed-graph-v1",
            "app": "saucedemo",
            "start_node": "login",
            "total_steps_completed": 1,
        },
        "nodes": [
            {
                "id": "inventory",
                "page_description": "product listing page",
                "url_patterns": ["/inventory.html"],
                "state_schema": {"cart_count": "number"},
                "observed_values": {"cart_count": [0, 1]},
                "last_state_snapshot": {"cart_count": 1},
                "interactable_elements": [
                    {
                        "description": "shopping cart link",
                        "position": "top right",
                        "explored": True,
                        "execution_hints": {"selector": ".shopping_cart_link"},
                    }
                ],
                "visit_count": 2,
            }
        ],
        "edges": [
            {
                "source": "inventory",
                "target": "cart",
                "semantic_action": "cart_open",
                "instructions": ["Click the shopping cart link"],
                "target_observations": ["cart page"],
                "schema_deltas": [],
                "preconditions": [],
                "effects": [],
                "visit_count": 1,
            }
        ],
    }


def test_build_observed_graph_accumulates_nodes_values_and_edges():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()

    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert data["meta"]["start_node"] == "login"
    assert data["meta"]["total_steps_completed"] == 6

    nodes = {node["id"]: node for node in data["nodes"]}
    assert set(nodes) == {
        "login",
        "inventory",
        "cart",
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }
    assert nodes["inventory"]["page_description"] == "inventory page"
    assert nodes["inventory"]["state_schema"]["cart_count"] == "number"
    assert nodes["inventory"]["observed_values"]["cart_count"] == [0, 1]
    assert nodes["inventory"]["last_state_snapshot"]["cart_count"] == 1
    assert nodes["inventory"]["visit_count"] == 4

    edges = {
        (edge["source"], edge["target"], edge["semantic_action"]): edge
        for edge in data["edges"]
    }
    add_to_cart = edges[("inventory", "inventory", "product_add_to_cart")]
    assert add_to_cart["instructions"] == ["Click Add to cart"]
    assert add_to_cart["schema_deltas"] == [
        {"cart_count": {"before": 0, "after": 1}}
    ]
    assert add_to_cart["effects"] == [
        {"path": "cart_count", "op": "set", "value": 1}
    ]


def test_build_observed_graph_can_attach_interactable_elements():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
        interactable_elements_by_node={
            "inventory": [
                InteractableElement(
                    description="Click Add to cart",
                    position="product list",
                    explored=True,
                    execution_hints={
                        "selector": '[data-test="add-to-cart-sauce-labs-backpack"]'
                    },
                )
            ]
        },
    )

    inventory = next(node for node in graph.nodes if node.id == "inventory")
    assert inventory.interactable_elements[0].description == "Click Add to cart"
    assert inventory.interactable_elements[0].explored is True
