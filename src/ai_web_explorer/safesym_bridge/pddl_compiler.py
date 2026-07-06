from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_web_explorer.safesym_bridge.observed_graph import WebObservedGraph


@dataclass(frozen=True)
class PddlArtifacts:
    domain: str
    problem: str


def compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts:
    domain = "\n".join(
        [
            f"(define (domain {graph.app})",
            "  (:requirements :strips)",
            "  (:predicates",
            "    (at ?page)",
            "    (state_order_created)",
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
