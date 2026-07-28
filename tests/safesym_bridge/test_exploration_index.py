from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.exploration_index import build_exploration_context
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.state_embedding import StateMatch


def node(node_id: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://shop.test/{node_id}",
            url_pattern=f"https://shop.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
    )


def edge(source: str, target: str, action_id: str, status: str) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_id.replace("_", " "),
        action=BrowserAction("click", f"#{action_id}", action_id),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click",
            f"#{action_id}",
            action_id,
            {},
            source,
            target,
            status != "failed_execution",
        ),
        status=status,
    )


def test_build_exploration_context_summarizes_tried_and_avoid_actions():
    graph = WebKobeGraph(
        app="shop",
        start_node_id="products",
        total_steps_completed=3,
        nodes=[node("products"), node("cart")],
        edges=[
            edge("products", "cart", "open_cart", "succeeded_with_navigation"),
            edge("products", "products", "theme_toggle", "no_observed_change"),
            edge("products", "products", "bad_button", "failed_execution"),
        ],
    )

    context = build_exploration_context(graph, current_node_id="products")

    assert context.tried_action_ids == ("open_cart", "theme_toggle", "bad_button")
    assert context.avoid_action_ids == ("theme_toggle", "bad_button")
    assert (
        "Avoid repeating actions: theme_toggle, bad_button"
        in context.to_prompt_block()
    )


def test_build_exploration_context_uses_matched_node_for_revisit_memory():
    graph = WebKobeGraph(
        app="shop",
        start_node_id="products",
        total_steps_completed=1,
        nodes=[node("products")],
        edges=[edge("products", "products", "open_filter", "no_observed_change")],
    )
    match = StateMatch(status="same", node_id="products", score=0.94)

    context = build_exploration_context(
        graph,
        current_node_id="new_products_node",
        state_match=match,
    )

    assert context.reference_node_id == "products"
    assert context.is_revisit is True
    assert context.avoid_action_ids == ("open_filter",)
    assert (
        "This state appears to revisit node products" in context.to_prompt_block()
    )
