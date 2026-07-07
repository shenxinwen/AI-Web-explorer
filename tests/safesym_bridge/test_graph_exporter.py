from ai_web_explorer.safesym_bridge.graph_exporter import graph_to_fsm
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_graph_to_fsm_exports_safesym_shape_without_exploration_fields():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )

    fsm = graph_to_fsm(graph, terminal_pages=["checkout_complete"])
    data = fsm.to_dict()

    assert data["meta"] == {
        "app": "saucedemo",
        "initial_page_id": "login",
        "terminal_pages": ["checkout_complete"],
    }
    pages = {page["id"]: page for page in data["pages"]}
    assert "interactable_elements" not in pages["inventory"]
    assert pages["inventory"]["signature_schema"]["$.cart_count"] == "number"

    actions = [action for page in data["pages"] for action in page["actions"]]
    order_action = next(
        action for action in actions if action["id"] == "order_place_confirm"
    )
    assert order_action["from"] == "checkout_overview"
    assert order_action["to"] == "checkout_complete"
    assert order_action["effects"] == [
        {"path": "$.order_created", "op": "set", "value": True}
    ]
