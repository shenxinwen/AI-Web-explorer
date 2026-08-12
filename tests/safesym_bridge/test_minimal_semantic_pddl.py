import pytest

from ai_web_explorer.grounded_web.semantic_model import (
    SemanticAction,
    SemanticPlanningGraph,
)
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
)


def _action(graph_text, name):
    marker = f"(:action {name}"
    start = graph_text.index(marker)
    next_action = graph_text.find("  (:action ", start + len(marker))
    return graph_text[start : next_action if next_action >= 0 else graph_text.index("\n)", start)]


def _practice_shopping_semantic_graph():
    return SemanticPlanningGraph(
        start_location="shopping",
        locations=["checkout", "shopping"],
        capability_facts=["products_filtered", "products_sorted"],
        business_facts=["cart_has_items"],
        initial_business_facts=[],
        actions=[
            SemanticAction(
                action_id="sort_products",
                action_name="sort_products",
                action_role="presentation_capability",
                source_location="shopping",
                target_location="shopping",
                added_facts=["products_sorted"],
                raw_edge_ids=["edge-sort"],
                evidence=["Products visibly changed order."],
            ),
            SemanticAction(
                action_id="add_to_cart_from_shopping",
                action_name="add_to_cart_from_shopping",
                action_role="state_mutation",
                source_location="shopping",
                target_location="shopping",
                added_facts=["cart_has_items"],
                raw_edge_ids=["edge-cart"],
                evidence=["Cart count changed."],
            ),
            SemanticAction(
                action_id="open_checkout",
                action_name="open_checkout",
                action_role="guarded_navigation",
                source_location="shopping",
                target_location="checkout",
                required_facts=["cart_has_items"],
                added_facts=["cart_has_items"],
                preserved_facts=["cart_has_items"],
                raw_edge_ids=["edge-checkout"],
                evidence=["Checkout surface opened."],
            ),
        ],
    )


def test_compiler_separates_location_capability_and_business_facts():
    graph = _practice_shopping_semantic_graph()
    domain = compile_minimal_semantic_domain(graph).domain
    assert ":precondition (and (at_shopping))" in _action(domain, "sort_products")
    assert ":effect (and (at_shopping) (products_sorted))" in _action(domain, "sort_products")
    assert "products_sorted" not in _action(domain, "add_to_cart_from_shopping").split(":effect")[0]
    assert ":precondition (and (at_shopping) (cart_has_items))" in _action(domain, "open_checkout")
    assert "(not (at_shopping))" in _action(domain, "open_checkout")
    assert "(at_checkout)" in _action(domain, "open_checkout")
    assert "(cart_has_items)" in _action(domain, "open_checkout").split(":effect")[1]


def test_problem_can_ask_for_checkout_location():
    graph = _practice_shopping_semantic_graph()
    problem = compile_minimal_semantic_problem(graph, goal_location="checkout").problem
    assert "(:init (at_shopping))" in problem
    assert "(:goal (and (at_checkout)))" in problem


def test_supporting_facts_cannot_enter_compiler_without_graph_fields():
    graph = _practice_shopping_semantic_graph()
    domain = compile_minimal_semantic_domain(graph).domain
    assert "supporting_facts" not in domain


def test_order_reversal_produces_byte_identical_pddl():
    graph = _practice_shopping_semantic_graph()
    reversed_graph = SemanticPlanningGraph(
        start_location=graph.start_location,
        locations=list(reversed(graph.locations)),
        capability_facts=list(reversed(graph.capability_facts)),
        business_facts=list(reversed(graph.business_facts)),
        initial_business_facts=list(reversed(graph.initial_business_facts)),
        actions=list(reversed(graph.actions)),
    )
    assert compile_minimal_semantic_domain(graph).domain == compile_minimal_semantic_domain(reversed_graph).domain


def test_document_fixture_uses_the_same_compiler():
    graph = SemanticPlanningGraph(
        start_location="document_list",
        locations=["document_list", "document_workspace"],
        capability_facts=["documents_found", "document_selected"],
        business_facts=[],
        initial_business_facts=[],
        actions=[
            SemanticAction(
                action_id="search_documents",
                action_name="search_documents",
                action_role="presentation_capability",
                source_location="document_list",
                target_location="document_list",
                added_facts=["documents_found"],
            ),
            SemanticAction(
                action_id="select_document",
                action_name="select_document",
                action_role="navigation",
                source_location="document_list",
                target_location="document_workspace",
                added_facts=["document_selected"],
            ),
        ],
    )
    domain = compile_minimal_semantic_domain(graph).domain
    assert "at_document_list" in domain
    assert "documents_found" in domain
    assert "document_selected" in domain


def test_empty_semantic_action_set_still_produces_valid_domain():
    graph = SemanticPlanningGraph(
        start_location="document_list",
        locations=["document_list"],
        capability_facts=[],
        business_facts=[],
        initial_business_facts=[],
        actions=[],
    )
    assert "(define (domain web_kobe_semantic)" in compile_minimal_semantic_domain(graph).domain


def test_unreachable_checkout_goal_is_rejected():
    graph = _practice_shopping_semantic_graph()
    graph = SemanticPlanningGraph(
        start_location=graph.start_location,
        locations=graph.locations,
        capability_facts=graph.capability_facts,
        business_facts=graph.business_facts,
        initial_business_facts=graph.initial_business_facts,
        actions=[graph.actions[0]],
    )
    with pytest.raises(ValueError, match="goal_unreachable"):
        compile_minimal_semantic_problem(graph, goal_location="checkout")


def test_problem_requires_a_goal_and_rejects_unknown_goals():
    graph = _practice_shopping_semantic_graph()
    with pytest.raises(ValueError, match="goal_required"):
        compile_minimal_semantic_problem(graph)
    with pytest.raises(ValueError, match="unknown_goal_location"):
        compile_minimal_semantic_problem(graph, goal_location="missing")
    with pytest.raises(ValueError, match="unknown_goal_fact"):
        compile_minimal_semantic_problem(graph, goal_facts=["missing_fact"])


def test_shortest_checkout_plan_uses_add_then_open_checkout():
    graph = _practice_shopping_semantic_graph()
    initial = {"at_shopping"}
    queue = [(initial, [])]
    seen = {frozenset(initial)}
    plan = None
    while queue:
        state, actions = queue.pop(0)
        if "at_checkout" in state:
            plan = actions
            break
        for action in graph.actions:
            if f"at_{action.source_location}" not in state:
                continue
            if not set(action.required_facts).issubset(state):
                continue
            next_state = set(state)
            if action.source_location != action.target_location:
                next_state.discard(f"at_{action.source_location}")
            next_state.add(f"at_{action.target_location}")
            next_state.update(action.added_facts)
            next_state.difference_update(action.removed_facts)
            key = frozenset(next_state)
            if key not in seen:
                seen.add(key)
                queue.append((next_state, actions + [action.action_name]))
    assert plan == ["add_to_cart_from_shopping", "open_checkout"]
