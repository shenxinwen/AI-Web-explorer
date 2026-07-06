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


def _predicate_for_condition(path: str, value: object) -> tuple[str, bool] | None:
    if path == "$.cart_count":
        if isinstance(value, (int, float)):
            return CART_COUNT_POSITIVE, value > 0
        return None
    if path in BOOLEAN_STATE_PREDICATES and isinstance(value, bool):
        return BOOLEAN_STATE_PREDICATES[path], value
    return None


def _format_positive_atoms(atoms: list[str], indent: str) -> list[str]:
    return [f"{indent}({atom})" for atom in atoms]


def _format_effect_atoms(
    add_atoms: list[str], delete_atoms: list[str], indent: str
) -> list[str]:
    lines = [f"{indent}({atom})" for atom in add_atoms]
    lines.extend(f"{indent}(not ({atom}))" for atom in delete_atoms)
    return lines


def _format_action(
    *,
    name: str,
    preconditions: list[str],
    add_effects: list[str],
    delete_effects: list[str],
) -> str:
    precondition_lines = _format_positive_atoms(preconditions, "      ")
    effect_lines = _format_effect_atoms(add_effects, delete_effects, "      ")
    return "\n".join(
        [
            f"  (:action {name}",
            "    :precondition",
            "      (and",
            *precondition_lines,
            "      )",
            "    :effect",
            "      (and",
            *effect_lines,
            "      )",
            "  )",
        ]
    )


def _saucedemo_fill_actions() -> list[str]:
    return [
        _format_action(
            name="login_fill_credentials",
            preconditions=["at login"],
            add_effects=["state_username_filled", "state_password_filled"],
            delete_effects=[],
        ),
        _format_action(
            name="checkout_info_fill",
            preconditions=["at checkout_info"],
            add_effects=["state_checkout_info_filled"],
            delete_effects=[],
        ),
    ]


def _edge_action_preconditions(edge) -> list[str]:
    atoms = [f"at {edge.source}"]
    for condition in edge.preconditions:
        mapped = _predicate_for_condition(condition["path"], condition["value"])
        if mapped is None:
            continue
        predicate, is_positive = mapped
        if is_positive:
            atoms.append(predicate)
    return atoms


def _edge_action_effects(edge) -> tuple[list[str], list[str]]:
    add_effects: list[str] = []
    delete_effects: list[str] = []
    if edge.source != edge.target:
        delete_effects.append(f"at {edge.source}")
        add_effects.append(f"at {edge.target}")
    else:
        add_effects.append(f"at {edge.target}")

    for effect in edge.effects:
        if effect.get("op") != "set":
            continue
        mapped = _predicate_for_condition(effect["path"], effect["value"])
        if mapped is None:
            continue
        predicate, is_positive = mapped
        if is_positive:
            add_effects.append(predicate)
        else:
            delete_effects.append(predicate)
    return add_effects, delete_effects


def _graph_edge_actions(graph: WebObservedGraph) -> list[str]:
    actions: list[str] = []
    for edge in graph.edges:
        add_effects, delete_effects = _edge_action_effects(edge)
        actions.append(
            _format_action(
                name=edge.semantic_action,
                preconditions=_edge_action_preconditions(edge),
                add_effects=add_effects,
                delete_effects=delete_effects,
            )
        )
    return actions


def compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts:
    state_predicates = _state_predicates_for_graph(graph)
    predicate_lines = ["    (at ?page)"] + [
        f"    ({predicate})" for predicate in state_predicates
    ]
    actions = _saucedemo_fill_actions() + _graph_edge_actions(graph)
    domain = "\n".join(
        [
            f"(define (domain {graph.app})",
            "  (:requirements :strips)",
            "  (:predicates",
            *predicate_lines,
            "  )",
            *actions,
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
