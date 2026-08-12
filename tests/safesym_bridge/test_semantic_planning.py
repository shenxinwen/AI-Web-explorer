from ai_web_explorer.grounded_web.business_profile import PlanningDelta, PlanningState
from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.grounded_web.semantic_planning import (
    build_semantic_planning_graph,
)


def _node(node_id, *, active_facts=None, profile_fact_ids=None):
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type="surface",
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        planning_state=PlanningState(
            active_facts=list(active_facts or []),
            profile_fact_ids=list(profile_fact_ids or []),
        ),
    )


def _edge(
    *,
    source="start",
    target="after",
    action_name="do_action",
    role="navigation",
    source_location="shopping",
    target_location="shopping",
    completion_facts=None,
    candidate_required_facts=None,
    preserved_facts=None,
    evidence=None,
    confidence=0.9,
    source_active_facts=None,
    source_profile_fact_ids=None,
    supporting_facts=None,
    planning_delta=None,
):
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_name,
        action=BrowserAction(
            "click",
            None,
            action_name,
            canonical_action_name=action_name,
            supporting_facts=list(supporting_facts or []),
        ),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "click",
            None,
            action_name,
            {},
            source,
            target,
            True,
        ),
        planning_delta=planning_delta,
        semantic_observation=SemanticObservation(
            action_role=role,
            source_location=source_location,
            target_location=target_location,
            completion_facts=list(completion_facts or []),
            candidate_required_facts=list(candidate_required_facts or []),
            preserved_facts=list(preserved_facts or []),
            evidence=list(evidence or [f"Observed {action_name}."]),
            confidence=confidence,
        ),
        status="succeeded",
    )


def _graph_with_edge(edge, *, source_active_facts=None, source_profile_fact_ids=None):
    return WebKobeGraph(
        app="test",
        start_node_id=edge.source_node_id,
        total_steps_completed=1,
        nodes=[
            _node(
                edge.source_node_id,
                active_facts=source_active_facts,
                profile_fact_ids=source_profile_fact_ids,
            ),
            _node(edge.target_node_id),
        ],
        edges=[edge],
    )


def test_sort_stays_at_location_and_adds_completion_fact():
    graph = _graph_with_edge(
        _edge(
            action_name="sort_products",
            role="presentation_capability",
            completion_facts=["products_sorted"],
        ),
        source_active_facts=["unrelated_fact"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    action = semantic.actions[0]
    assert action.required_facts == []
    assert action.added_facts == ["products_sorted"]
    assert action.source_location == action.target_location == "shopping"


def test_add_to_cart_changes_fact_without_creating_combination_location():
    graph = _graph_with_edge(
        _edge(
            action_name="add_to_cart_from_shopping",
            role="state_mutation",
            planning_delta=PlanningDelta(verified_added_facts=["cart_has_items"]),
        )
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.locations == ["shopping"]
    assert semantic.actions[0].added_facts == ["cart_has_items"]


def test_guarded_navigation_uses_only_confirmed_candidate_requirement():
    graph = _graph_with_edge(
        _edge(
            action_name="open_checkout",
            role="guarded_navigation",
            source_location="shopping",
            target_location="checkout",
            candidate_required_facts=["cart_has_items"],
            source_active_facts=["products_sorted", "cart_has_items"],
            source_profile_fact_ids=["cart_has_items"],
        ),
        source_active_facts=["products_sorted", "cart_has_items"],
        source_profile_fact_ids=["cart_has_items"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == ["cart_has_items"]
    assert "products_sorted" not in semantic.actions[0].required_facts


def test_supporting_facts_never_become_requirements():
    graph = _graph_with_edge(
        _edge(
            supporting_facts=["checkout_button_visible"],
            role="navigation",
        )
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == []


def test_uncertain_requirement_is_reported_but_omitted():
    graph = _graph_with_edge(
        _edge(
            role="guarded_navigation",
            candidate_required_facts=["cart_has_items"],
            source_active_facts=["cart_has_items"],
            source_profile_fact_ids=["cart_has_items"],
            confidence=0.79,
        ),
        source_active_facts=["cart_has_items"],
        source_profile_fact_ids=["cart_has_items"],
    )
    semantic, report = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == []
    assert report.uncertain_preconditions[0]["fact"] == "cart_has_items"


def test_inactive_or_generated_requirement_is_not_promoted():
    graph = _graph_with_edge(
        _edge(
            role="guarded_navigation",
            candidate_required_facts=["generated_flag", "inactive_flag"],
            source_active_facts=["generated_flag"],
            source_profile_fact_ids=[],
        ),
        source_active_facts=["generated_flag"],
        source_profile_fact_ids=[],
    )
    semantic, report = build_semantic_planning_graph(graph)
    assert semantic.actions[0].required_facts == []
    assert {item["reason"] for item in report.uncertain_preconditions} == {
        "inactive_source_fact",
        "not_verified_profile_fact",
    }


def test_duplicate_actions_and_edge_order_are_deterministic():
    first = _edge(
        action_name="sort products",
        role="presentation_capability",
        completion_facts=["products_sorted"],
    )
    second = _edge(
        source="start",
        target="other",
        action_name="sort-products",
        role="presentation_capability",
        completion_facts=["products_sorted"],
    )
    graph_a = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[_node("start"), _node("after"), _node("other")],
        edges=[first, second],
    )
    graph_b = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[_node("start"), _node("after"), _node("other")],
        edges=[second, first],
    )
    semantic_a, report_a = build_semantic_planning_graph(graph_a)
    semantic_b, report_b = build_semantic_planning_graph(graph_b)
    assert semantic_a.to_dict() == semantic_b.to_dict()
    assert report_a.to_dict() == report_b.to_dict()
    assert len(semantic_a.actions) == 1
    assert semantic_a.actions[0].raw_edge_ids == sorted(semantic_a.actions[0].raw_edge_ids)


def test_conflicting_start_locations_are_reported_without_choosing_one():
    edge_a = _edge(source="start", target="after", source_location="shopping")
    edge_b = _edge(source="start", target="other", source_location="documents")
    graph = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[_node("start"), _node("after"), _node("other")],
        edges=[edge_a, edge_b],
    )
    semantic, report = build_semantic_planning_graph(graph)
    assert semantic.start_location == ""
    assert any(
        item.get("reason") == "conflicting_start_location"
        for item in report.excluded_edges
    )
