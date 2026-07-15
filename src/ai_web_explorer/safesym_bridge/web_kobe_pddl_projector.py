from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.grounded_web.graph import WebKobeGraph


@dataclass(frozen=True)
class WebKobePddlArtifacts:
    domain: str
    problem: str


def _predicate(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _at(node_id: str) -> str:
    return f"at_{_predicate(node_id)}"


def _is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _is_zero_or_negative_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value <= 0


def _positive_predicate(name: str) -> str:
    return f"{_predicate(name)}_positive"


def _state_predicate_for_value(key: str, value: object) -> str | None:
    if isinstance(value, bool):
        return _predicate(key)
    if _is_positive_number(value):
        return _positive_predicate(key)
    return None


def _state_predicates(graph: WebKobeGraph) -> list[str]:
    names: set[str] = set()
    for node in graph.nodes:
        for key, value in node.last_state_snapshot.items():
            predicate = _state_predicate_for_value(key, value)
            if predicate is not None:
                names.add(predicate)
    return sorted(names)


def _nodes_by_id(graph: WebKobeGraph) -> dict[str, object]:
    return {node.node_id: node for node in graph.nodes}


def _require_node(graph: WebKobeGraph, node_id: str, *, role: str):
    nodes = _nodes_by_id(graph)
    if node_id not in nodes:
        raise ValueError(f"Unknown {role} node: {node_id}")
    return nodes[node_id]


def _initial_predicates(graph: WebKobeGraph, *, start_node_id: str) -> list[str]:
    start = _require_node(graph, start_node_id, role="start")
    predicates = [_at(start.node_id)]
    for key, value in start.last_state_snapshot.items():
        if isinstance(value, bool) and value is True:
            predicates.append(_predicate(key))
        elif _is_positive_number(value):
            predicates.append(_positive_predicate(key))
    return sorted(set(predicates))


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
        elif _is_zero_or_negative_number(delta.before) and _is_positive_number(
            delta.after
        ):
            effects.append(f"({_positive_predicate(delta.field)})")
        elif _is_positive_number(delta.before) and _is_zero_or_negative_number(
            delta.after
        ):
            effects.append(f"(not ({_positive_predicate(delta.field)}))")
    return effects


def compile_web_kobe_graph_to_pddl(
    graph: WebKobeGraph,
    *,
    goal_node_id: str,
    start_node_id: str | None = None,
) -> WebKobePddlArtifacts:
    selected_start_node_id = start_node_id or graph.start_node_id
    _require_node(graph, selected_start_node_id, role="start")
    _require_node(graph, goal_node_id, role="goal")

    predicates = sorted(
        set([_at(node.node_id) for node in graph.nodes] + _state_predicates(graph))
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
    init_text = " ".join(
        f"({name})"
        for name in _initial_predicates(
            graph,
            start_node_id=selected_start_node_id,
        )
    )
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
