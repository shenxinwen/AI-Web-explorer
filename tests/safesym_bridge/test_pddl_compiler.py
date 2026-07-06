from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import compile_graph_to_pddl
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def _compile_saucedemo():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    return compile_graph_to_pddl(graph)


def test_compile_graph_to_pddl_returns_domain_and_problem_text():
    artifacts = _compile_saucedemo()

    assert artifacts.domain.startswith("(define (domain saucedemo)")
    assert artifacts.problem.startswith("(define (problem saucedemo-problem)")
    assert "(:domain saucedemo)" in artifacts.problem
    assert "(:objects" in artifacts.problem
    assert "login inventory cart checkout_info checkout_overview checkout_complete" in artifacts.problem
    assert "(:init" in artifacts.problem
    assert "(at login)" in artifacts.problem
    assert "(and" in artifacts.problem
    assert "(at checkout_complete)" in artifacts.problem
    assert "(state_order_created)" in artifacts.problem


def test_compile_graph_to_pddl_declares_stable_state_predicates():
    artifacts = _compile_saucedemo()

    expected_predicates = [
        "(state_is_logged_in)",
        "(state_username_filled)",
        "(state_password_filled)",
        "(state_checkout_info_filled)",
        "(state_checkout_started)",
        "(state_order_review_ready)",
        "(state_order_created)",
        "(state_cart_count_positive)",
    ]
    for predicate in expected_predicates:
        assert predicate in artifacts.domain

    assert "state_cart_count_is_value" not in artifacts.domain
    assert "state_cart_count_is_value" not in artifacts.problem
