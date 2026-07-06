from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_web_explorer.safesym_bridge.observed_graph import WebObservedGraph

BOOLEAN_STATE_PREDICATES = {
    "$.is_logged_in": "state_is_logged_in",
    "$.username_filled": "state_username_filled",
    "$.password_filled": "state_password_filled",
    "$.checkout_info_filled": "state_checkout_info_filled",
    "$.checkout_started": "state_checkout_started",
    "$.order_review_ready": "state_order_review_ready",
    "$.order_created": "state_order_created",
}

CART_COUNT_POSITIVE = "state_cart_count_positive"


@dataclass(frozen=True)
class PddlArtifacts:
    domain: str
    problem: str


def _state_predicates_for_graph(graph: WebObservedGraph) -> list[str]:
    predicates: set[str] = set()
    for node in graph.nodes:
        for path in node.state_schema:
            if path == "$.cart_count":
                predicates.add(CART_COUNT_POSITIVE)
            elif path in BOOLEAN_STATE_PREDICATES:
                predicates.add(BOOLEAN_STATE_PREDICATES[path])
    return sorted(predicates)


def compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts:
    state_predicates = _state_predicates_for_graph(graph)
    predicate_lines = ["    (at ?page)"] + [
        f"    ({predicate})" for predicate in state_predicates
    ]
    domain = "\n".join(
        [
            f"(define (domain {graph.app})",
            "  (:requirements :strips)",
            "  (:predicates",
            *predicate_lines,
            "  )",
            ")",
            "",
        ]
    )
    problem = "\n".join(
        [
            f"(define (problem {graph.app}-problem)",
            f"  (:domain {graph.app})",
            "  (:objects",
            "    login inventory cart checkout_info checkout_overview checkout_complete",
            "  )",
            "  (:init",
            f"    (at {graph.start_node})",
            "  )",
            "  (:goal",
            "    (and",
            "      (at checkout_complete)",
            "      (state_order_created)",
            "    )",
            "  )",
            ")",
            "",
        ]
    )
    return PddlArtifacts(domain=domain, problem=problem)


def write_pddl_artifacts(graph: WebObservedGraph, output_dir: Path) -> PddlArtifacts:
    artifacts = compile_graph_to_pddl(graph)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "domain.pddl").write_text(artifacts.domain, encoding="utf-8")
    (output_dir / "problem.pddl").write_text(artifacts.problem, encoding="utf-8")
    return artifacts
