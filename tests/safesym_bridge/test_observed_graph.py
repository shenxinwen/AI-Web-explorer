from ai_web_explorer.safesym_bridge.observed_graph import (
    InteractableElement,
    WebObservedEdge,
    WebObservedGraph,
    WebObservedNode,
)


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
                state_schema={"$.cart_count": "number"},
                observed_values={"$.cart_count": [0, 1]},
                last_state_snapshot={"$.cart_count": 1},
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
                "state_schema": {"$.cart_count": "number"},
                "observed_values": {"$.cart_count": [0, 1]},
                "last_state_snapshot": {"$.cart_count": 1},
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
