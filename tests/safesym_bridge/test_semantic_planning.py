from dataclasses import replace

import pytest

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
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
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
    required_action_ids=None,
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
        required_action_ids=list(required_action_ids or []),
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
    assert action.added_facts == [
        "products_sorted",
        "sort_products_succeeded",
    ]
    assert action.source_location == action.target_location == "shopping"


def test_success_fact_uses_the_readable_action_succeeded_name():
    graph = _graph_with_edge(
        _edge(
            action_name="submit_login",
            role="navigation",
            source_location="login_form",
            target_location="product_catalog",
        )
    )

    semantic, _ = build_semantic_planning_graph(graph)

    assert semantic.actions[0].added_facts == ["submit_login_succeeded"]
    assert "submit_login_succeeded" in semantic.capability_facts


def test_successful_action_dependencies_become_completion_preconditions():
    prerequisite = _edge(
        action_name="fill_billing",
        role="presentation_capability",
        target="after_billing",
        completion_facts=[],
    )
    dependent = _edge(
        source="after_billing",
        target="after_order",
        action_name="place_order",
        role="commit",
        required_action_ids=["fill_billing"],
    )
    graph = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[_node("start"), _node("after_billing"), _node("after_order")],
        edges=[prerequisite, dependent],
    )

    semantic, report = build_semantic_planning_graph(graph)

    assert set(report.included_raw_edge_ids) == {
        prerequisite.edge_id,
        dependent.edge_id,
    }
    prerequisite_action = next(
        action for action in semantic.actions if action.action_name == "fill_billing"
    )
    dependent_action = next(
        action for action in semantic.actions if action.action_name == "place_order"
    )
    assert "fill_billing_succeeded" in prerequisite_action.added_facts
    assert "fill_billing_succeeded" in dependent_action.required_facts
    domain = compile_minimal_semantic_domain(semantic).domain
    assert "(fill_billing_succeeded)" in domain
    place_order = domain.index("(:action place_order")
    completion_fact = domain.index("(fill_billing_succeeded)", place_order)
    assert completion_fact < domain.index(":effect", place_order)


def test_same_action_id_dependency_is_scoped_to_dependent_source_location():
    shopping_fill = _edge(
        source="shopping_start",
        target="shopping_after_fill",
        action_name="fill_form",
        source_location="shopping",
        target_location="shopping",
    )
    checkout_fill = _edge(
        source="checkout_start",
        target="checkout_after_fill",
        action_name="fill_form",
        source_location="checkout",
        target_location="checkout",
    )
    checkout_submit = _edge(
        source="checkout_after_fill",
        target="checkout_after_submit",
        action_name="submit_form",
        source_location="checkout",
        target_location="checkout",
        required_action_ids=["fill_form"],
    )
    graph = WebKobeGraph(
        app="test",
        start_node_id="shopping_start",
        total_steps_completed=3,
        nodes=[
            _node("shopping_start"),
            _node("shopping_after_fill"),
            _node("checkout_start"),
            _node("checkout_after_fill"),
            _node("checkout_after_submit"),
        ],
        edges=[shopping_fill, checkout_fill, checkout_submit],
    )

    semantic, _ = build_semantic_planning_graph(graph)
    submit = next(
        action for action in semantic.actions if action.action_name == "submit_form"
    )

    assert submit.required_facts == ["fill_form_checkout_succeeded"]
    assert "fill_form_shopping_succeeded" not in submit.required_facts


@pytest.mark.parametrize("prerequisite_state", ["absent", "failed", "non_projectable"])
def test_dependent_edge_is_excluded_when_required_success_is_missing(
    prerequisite_state,
):
    dependent = _edge(
        source="checkout_after_fill",
        target="checkout_after_submit",
        action_name="place_order",
        source_location="checkout",
        target_location="checkout",
        required_action_ids=["fill_form"],
    )
    edges = [dependent]
    if prerequisite_state != "absent":
        prerequisite = _edge(
            source="checkout_start",
            target="checkout_after_fill",
            action_name="fill_form",
            source_location="checkout",
            target_location="checkout",
        )
        if prerequisite_state == "failed":
            prerequisite = replace(
                prerequisite,
                status="failed_execution",
                execution_trace=replace(prerequisite.execution_trace, success=False),
            )
        else:
            prerequisite = replace(prerequisite, status="no_observed_change")
        edges.insert(0, prerequisite)
    graph = WebKobeGraph(
        app="test",
        start_node_id="checkout_start",
        total_steps_completed=len(edges),
        nodes=[
            _node("checkout_start"),
            _node("checkout_after_fill"),
            _node("checkout_after_submit"),
        ],
        edges=edges,
    )

    semantic, report = build_semantic_planning_graph(graph)

    assert not any(action.action_name == "place_order" for action in semantic.actions)
    exclusion = next(
        item
        for item in report.excluded_edges
        if item.get("raw_edge_id") == dependent.edge_id
    )
    assert exclusion["reason"] == "missing_successful_required_action"
    assert exclusion["missing_action_ids"] == ["fill_form"]


def test_every_successful_action_gets_a_location_qualified_completion_fact():
    graph = _graph_with_edge(
        _edge(
            action_name="filter_products",
            role="presentation_capability",
        )
    )

    semantic, _ = build_semantic_planning_graph(graph)
    action = semantic.actions[0]
    domain = compile_minimal_semantic_domain(semantic).domain

    assert action.added_facts == ["filter_products_succeeded"]
    assert "filter_products_succeeded" in semantic.capability_facts
    assert "(filter_products_succeeded)" in domain


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
    assert semantic.actions[0].added_facts == [
        "add_to_cart_from_shopping_succeeded",
        "cart_has_items",
    ]


def test_unpromoted_preserved_profile_fact_is_not_created_by_ordinary_action():
    graph = _graph_with_edge(
        _edge(
            action_name="sort_products",
            role="presentation_capability",
            completion_facts=["products_sorted"],
            planning_delta=PlanningDelta(
                preserved_profile_facts=["cart_has_items"],
            ),
        ),
        source_active_facts=[],
        source_profile_fact_ids=["cart_has_items"],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    action = semantic.actions[0]
    assert action.preserved_facts == []
    assert "cart_has_items" not in semantic.business_facts
    domain = compile_minimal_semantic_domain(semantic).domain
    assert "(cart_has_items)" not in domain
    with pytest.raises(ValueError, match="unknown_goal_fact"):
        compile_minimal_semantic_problem(semantic, goal_facts=["cart_has_items"])


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


def test_semantic_observation_conflict_is_explicitly_excluded_from_projection():
    edge = _edge(action_name="sort_products", role="presentation_capability")
    edge = replace(
        edge,
        semantic_observation=None,
        execution_trace=replace(
            edge.execution_trace,
            metadata={
                "semantic_observation_conflict": {
                    "status": "unresolved",
                    "policy": "unresolved_fail_closed",
                    "candidates": [{"source_location": "a"}, {"source_location": "b"}],
                    "selected": None,
                }
            },
        ),
    )
    semantic, report = build_semantic_planning_graph(_graph_with_edge(edge))
    assert semantic.actions == []
    assert report.excluded_edges[0]["reason"] == "semantic_observation_conflict"
    assert "sort_products" not in compile_minimal_semantic_domain(semantic).domain


def test_uncertain_requirement_is_reported_but_omitted():
    graph = _graph_with_edge(
        _edge(
            role="guarded_navigation",
            candidate_required_facts=["cart_has_items"],
            source_active_facts=["cart_has_items"],
            source_profile_fact_ids=["cart_has_items"],
            confidence=0.79,
        ),
        source_active_facts=["cart_has_items", "other_verified_fact"],
        source_profile_fact_ids=["cart_has_items", "other_verified_fact"],
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


def test_preserved_fact_difference_does_not_merge_when_edge_order_is_reversed():
    first = _edge(
        action_name="open_checkout",
        role="guarded_navigation",
        source_location="shopping",
        target_location="checkout",
        candidate_required_facts=["cart_has_items"],
        source_active_facts=["cart_has_items"],
        source_profile_fact_ids=["cart_has_items"],
    )
    second = _edge(
        action_name="open_checkout",
        role="guarded_navigation",
        source_location="shopping",
        target_location="checkout",
        candidate_required_facts=["other_verified_fact"],
    )
    graph_a = WebKobeGraph(
        app="test", start_node_id="start", total_steps_completed=2,
        nodes=[_node("start", active_facts=["cart_has_items", "other_verified_fact"], profile_fact_ids=["cart_has_items", "other_verified_fact"]), _node("after"), _node("other")],
        edges=[first, second],
    )
    graph_b = WebKobeGraph(
        app=graph_a.app, start_node_id=graph_a.start_node_id,
        total_steps_completed=graph_a.total_steps_completed,
        nodes=graph_a.nodes, edges=[second, first],
    )
    semantic_a, _ = build_semantic_planning_graph(graph_a)
    semantic_b, _ = build_semantic_planning_graph(graph_b)
    assert semantic_a.to_dict() == semantic_b.to_dict()
    assert len(semantic_a.actions) == 2


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


def test_practice_shopping_acceptance_path_excludes_optional_capabilities():
    sort_edge = _edge(
        action_name="sort_products",
        role="presentation_capability",
        completion_facts=["products_sorted"],
    )
    filter_edge = _edge(
        action_name="filter_products",
        role="presentation_capability",
        completion_facts=["products_filtered"],
    )
    add_edge = _edge(
        action_name="add_to_cart_from_shopping",
        role="state_mutation",
        planning_delta=PlanningDelta(verified_added_facts=["cart_has_items"]),
    )
    checkout_edge = _edge(
        source="after_add",
        action_name="open_checkout",
        role="guarded_navigation",
        target="checkout",
        target_location="checkout",
        candidate_required_facts=["cart_has_items"],
        source_active_facts=["cart_has_items"],
        source_profile_fact_ids=["cart_has_items"],
    )
    graph = WebKobeGraph(
        app="practice",
        start_node_id="start",
        total_steps_completed=4,
        nodes=[
            _node("start"),
            _node("after_sort"),
            _node("after_filter"),
            _node("after_add", active_facts=["cart_has_items"], profile_fact_ids=["cart_has_items"]),
            _node("checkout"),
        ],
        edges=[
            sort_edge,
            filter_edge,
            add_edge,
            checkout_edge,
        ],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert semantic.locations == ["checkout", "shopping"]
    assert {action.action_name for action in semantic.actions} == {
        "add_to_cart_from_shopping",
        "filter_products",
        "open_checkout",
        "sort_products",
    }
    checkout = next(
        action for action in semantic.actions if action.action_name == "open_checkout"
    )
    assert checkout.required_facts == ["cart_has_items"]
    assert "products_sorted" not in checkout.required_facts
    assert "products_filtered" not in checkout.required_facts


def test_document_fixture_projects_without_commerce_specific_rules():
    search = _edge(
        action_name="search_documents",
        role="presentation_capability",
        source_location="document_list",
        target_location="document_list",
        completion_facts=["documents_found"],
    )
    select = _edge(
        source="after_search",
        action_name="select_document",
        role="navigation",
        source_location="document_list",
        target_location="document_workspace",
        planning_delta=PlanningDelta(verified_added_facts=["document_selected"]),
    )
    graph = WebKobeGraph(
        app="documents",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[_node("start"), _node("after_search"), _node("workspace")],
        edges=[search, select],
    )
    semantic, _ = build_semantic_planning_graph(graph)
    assert "document_list" in semantic.locations
    assert "document_workspace" in semantic.locations
    assert "documents_found" in semantic.capability_facts
    assert "document_selected" in semantic.business_facts
