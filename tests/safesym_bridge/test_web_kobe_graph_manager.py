from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import (
    ReferenceObservation,
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

    first = _node("product_listing", {"cart_nonempty": False})
    second = _node("product_listing", {"cart_nonempty": True, "filter_open": False})

    assert manager.identify_or_add_node(first) == "product_listing"
    assert manager.identify_or_add_node(second) == "product_listing"

    graph = manager.to_graph()
    node = graph.nodes[0]
    assert node.visit_count == 2
    assert node.state_schema["cart_nonempty"] == [False, True]
    assert node.state_schema["filter_open"] == [False]
    assert node.last_state_snapshot == {"cart_nonempty": True, "filter_open": False}


def test_mark_interactable_explored_updates_matching_candidate():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node(
            "product_listing",
            {"cart_nonempty": False},
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
