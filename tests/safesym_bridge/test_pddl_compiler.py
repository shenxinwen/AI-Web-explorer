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


def test_compile_graph_to_pddl_emits_expected_actions():
    artifacts = _compile_saucedemo()

    expected_actions = [
        "(:action login_fill_credentials",
        "(:action login_submit",
        "(:action product_add_to_cart",
        "(:action cart_open",
        "(:action cart_checkout_start",
        "(:action checkout_info_fill",
        "(:action checkout_info_submit",
        "(:action order_place_confirm",
    ]
    for action in expected_actions:
        assert action in artifacts.domain


def test_fill_actions_make_submit_preconditions_reachable():
    artifacts = _compile_saucedemo()

    assert "(:action login_fill_credentials" in artifacts.domain
    assert "(state_username_filled)" in artifacts.domain
    assert "(state_password_filled)" in artifacts.domain
    assert "(:action checkout_info_fill" in artifacts.domain
    assert "(state_checkout_info_filled)" in artifacts.domain

    login_submit_start = artifacts.domain.index("(:action login_submit")
    login_submit_chunk = artifacts.domain[login_submit_start : login_submit_start + 500]
    assert "(state_username_filled)" in login_submit_chunk
    assert "(state_password_filled)" in login_submit_chunk

    checkout_submit_start = artifacts.domain.index("(:action checkout_info_submit")
    checkout_submit_chunk = artifacts.domain[
        checkout_submit_start : checkout_submit_start + 500
    ]
    assert "(state_checkout_info_filled)" in checkout_submit_chunk


def test_cart_positive_preconditions_are_preserved_for_checkout_actions():
    artifacts = _compile_saucedemo()

    cart_checkout_start = artifacts.domain.index("(:action cart_checkout_start")
    cart_checkout_chunk = artifacts.domain[
        cart_checkout_start : cart_checkout_start + 500
    ]
    assert "(state_cart_count_positive)" in cart_checkout_chunk

    order_place_confirm_start = artifacts.domain.index("(:action order_place_confirm")
    order_place_confirm_chunk = artifacts.domain[
        order_place_confirm_start : order_place_confirm_start + 500
    ]
    assert "(state_cart_count_positive)" in order_place_confirm_chunk
