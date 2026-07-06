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
