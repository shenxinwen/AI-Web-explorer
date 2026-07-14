from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph


@dataclass(frozen=True)
class WebKobePddlArtifacts:
    domain: str
    problem: str


def _predicate(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _at(node_id: str) -> str:
    return f"at_{_predicate(node_id)}"


def _boolean_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
        for key, value in node.last_state_snapshot.items():
            if isinstance(value, bool):
                names.add(_predicate(key))
    return sorted(names)


def _initial_predicates(graph: WebKobeGraph) -> list[str]:
    start = next(node for node in graph.nodes if node.node_id == graph.start_node_id)
    predicates = [_at(start.node_id)]
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
    return sorted(predicates)


def _action_name(raw: str) -> str:
    return _predicate(raw)


def _effects_for_edge(edge) -> list[str]:
    effects = [
        f"(not ({_at(edge.source_node_id)}))",
        f"({_at(edge.target_node_id)})",
    ]
    for delta in edge.observed_delta:
        if isinstance(delta.after, bool):
            pred = _predicate(delta.field)
            if delta.after:
                effects.append(f"({pred})")
            else:
                effects.append(f"(not ({pred}))")
    return effects


def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
) -> WebKobePddlArtifacts:
    predicates = sorted(
        set([_at(node.node_id) for node in graph.nodes] + _boolean_predicates(graph))
    )
    predicate_text = "\n".join(f"    ({name})" for name in predicates)

    action_blocks = []
    for edge in graph.edges:
        action_name = _action_name(edge.action.semantic_id)
        preconditions = [f"({_at(edge.source_node_id)})"]
        effects = _effects_for_edge(edge)
        action_blocks.append(
            "\n".join(
                [
                    f"  (:action {action_name}",
                    f"    :precondition (and {' '.join(preconditions)})",
                    f"    :effect (and {' '.join(effects)})",
                    "  )",
                ]
            )
        )

    domain = "\n".join(
        [
            "(define (domain web-kobe)",
            "  (:requirements :strips)",
            "  (:predicates",
            predicate_text,
            "  )",
            *action_blocks,
            ")",
        ]
    )
    init_text = " ".join(f"({name})" for name in _initial_predicates(graph))
    problem = "\n".join(
        [
            "(define (problem web-kobe-problem)",
            "  (:domain web-kobe)",
            f"  (:init {init_text})",
            f"  (:goal (and ({_at(goal_node_id)})))",
            ")",
        ]
    )
    return WebKobePddlArtifacts(domain=domain, problem=problem)
