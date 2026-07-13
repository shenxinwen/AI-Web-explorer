import json

from ai_web_explorer.safesym_bridge.capability_builder import build_capability_graph
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_build_capability_graph_projects_saucedemo_checkout_path():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()

    assert data["meta"] == {
        "schema_version": "web-capability-graph-v1",
        "app": "saucedemo",
        "start_state": "login_ready",
        "total_steps_completed": 6,
    }

    states = {state["state_id"]: state for state in data["states"]}
    assert {
        "login_ready",
        "product_listing_cart_empty",
        "product_listing_cart_nonempty",
        "cart_nonempty",
        "checkout_form_incomplete",
        "checkout_form_complete",
        "checkout_review_ready",
        "confirmation_order_created",
    }.issubset(states)

    product_listing = states["product_listing_cart_empty"]
    assert product_listing["page_frame"]["page_type"] == "product_listing"
    assert product_listing["page_frame"]["page_id"] == "saucedemo:inventory"
    capability_ids = {
        capability["capability_id"]
        for capability in product_listing["capabilities"]
    }
    assert "add_to_cart_product" in capability_ids
    assert "open_cart" in capability_ids


def test_build_capability_graph_abstracts_product_instances():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data_text = json.dumps(graph.to_dict(), ensure_ascii=False)

    assert "add_to_cart_product" in data_text
    assert "target_type" in data_text
    assert "product" in data_text
    assert "sauce_labs_backpack" not in data_text
    assert "29.99" not in data_text
    assert "Sauce Labs Backpack" not in data_text


def test_build_capability_graph_records_self_loop_state_delta():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    data = graph.to_dict()
    transitions = {
        transition["capability_id"]: transition
        for transition in data["transitions"]
    }

    add_to_cart = transitions["add_to_cart_product"]
    assert add_to_cart["source_state_id"] == "product_listing_cart_empty"
    assert add_to_cart["target_state_id"] == "product_listing_cart_nonempty"
    assert add_to_cart["transition_kind"] == "state_delta"
    assert add_to_cart["observed_delta"] == [
        {
            "field": "cart_nonempty",
            "before": False,
            "after": True,
            "delta_type": "state_indicator_change",
            "confidence": 1.0,
            "evidence": [
                {
                    "source": "transition_diff",
                    "selector": None,
                    "text_sample": None,
                    "url": "https://www.saucedemo.com/inventory.html",
                    "confidence": 1.0,
                }
            ],
        }
    ]


def test_build_capability_graph_records_navigation_transition():
    graph = build_capability_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    transitions = {
        transition.capability_id: transition
        for transition in graph.transitions
    }

    checkout = transitions["checkout_start"]
    assert checkout.transition_kind == "navigation"
    assert checkout.source_state_id == "cart_nonempty"
    assert checkout.target_state_id == "checkout_form_incomplete"
    assert checkout.observed_delta[0].field == "page_type"
    assert checkout.observed_delta[0].before == "cart"
    assert checkout.observed_delta[0].after == "checkout_form"
