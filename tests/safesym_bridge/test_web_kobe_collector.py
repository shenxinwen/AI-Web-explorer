import uuid

from ai_web_explorer import webstate
from ai_web_explorer.safesym_bridge.web_kobe_collector import WebKobeCollector
from ai_web_explorer.safesym_bridge.web_kobe_observer import WebKobeObservation


def _state(title: str) -> webstate.WebState:
    return webstate.WebState(
        title=title,
        title_embedding=[],
        urls=[f"https://example.test/{title.lower().replace(' ', '-')}"],
        description=[],
        actions=[],
        transitions=[],
        ws_id=uuid.uuid5(uuid.NAMESPACE_DNS, title),
    )


def _observation(url: str, title: str, **state_indicators):
    return WebKobeObservation(
        url=url,
        url_pattern=url,
        browser_title=title,
        heading=title,
        web_state_id=title,
        llm_title=title,
        state_indicators=state_indicators,
    )


def test_collector_records_state_and_transition_delta():
    collector = WebKobeCollector(app="example")
    source = _state("Products")
    target = _state("Products")
    action = webstate.Action(
        description="Add a product to the cart",
        part=0,
        priority=10,
        status="success",
        function_calls=[],
    )
    before = _observation(
        "https://example.test/products",
        "Products",
        cart_count=0,
        cart_nonempty=False,
    )
    after = _observation(
        "https://example.test/products",
        "Products",
        cart_count=1,
        cart_nonempty=True,
    )

    collector.on_state_observed(page=None, web_state=source, observation=before)
    collector.on_action_selected(source_state=source, action=action)
    collector.on_action_executed(action=action, success=True, tool_calls=[])
    collector.on_transition(
        source_state=source,
        action=action,
        target_state=target,
        before_observation=before,
        after_observation=after,
    )

    graph = collector.to_web_kobe_graph()

    assert graph.app == "example"
    assert len(graph.nodes) == 1
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.action.semantic_id == "add_a_product_to_the_cart"
    assert edge.schema_delta == {
        "cart_count": {"before": 0, "after": 1},
        "cart_nonempty": {"before": False, "after": True},
    }
    assert edge.execution_trace.success is True
