from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ai_web_explorer.grounded_web.semantic_model import (
    SemanticAction,
    SemanticPlanningGraph,
    normalize_semantic_id,
)


@dataclass(frozen=True)
class MinimalSemanticPddlArtifacts:
    domain: str = ""
    problem: str = ""
    report: dict[str, object] | None = None


def _predicate(value: str) -> str:
    normalized = normalize_semantic_id(value)
    return normalized or "unnamed"


def _domain_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "web_kobe_semantic"


def _atom(name: str) -> str:
    return f"({_predicate(name)})"


def _at(location: str) -> str:
    return _atom(f"at_{location}")


def _unique(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _action_name(action: SemanticAction, used: set[str]) -> str:
    base = _predicate(action.action_id or action.action_name)
    if base not in used:
        used.add(base)
        return base
    suffix = 2
    while f"{base}_{suffix}" in used:
        suffix += 1
    result = f"{base}_{suffix}"
    used.add(result)
    return result


def _render_action(action: SemanticAction, action_name: str) -> list[str]:
    preconditions = _unique(
        [_at(action.source_location)]
        + [_atom(fact) for fact in action.required_facts]
    )
    effects: list[str] = []
    if action.source_location != action.target_location:
        effects.append(f"(not {_at(action.source_location)})")
    effects.append(_at(action.target_location))
    effects.extend(_atom(fact) for fact in action.added_facts)
    effects.extend(f"(not {_atom(fact)})" for fact in action.removed_facts)
    effects.extend(_atom(fact) for fact in action.preserved_facts)
    effects = _unique(effects)
    lines = [
        f"  (:action {action_name}",
        "    :parameters ()",
        f"    :precondition (and {' '.join(preconditions)})",
        f"    :effect (and {' '.join(effects)})",
        "  )",
    ]
    return lines


def compile_minimal_semantic_domain(
    graph: SemanticPlanningGraph,
    *,
    domain_name: str = "web_kobe_semantic",
) -> MinimalSemanticPddlArtifacts:
    normalized_domain_name = _domain_name(domain_name)
    locations = sorted({_predicate(location) for location in graph.locations})
    facts = sorted(
        {
            _predicate(fact)
            for fact in [
                *graph.capability_facts,
                *graph.business_facts,
                *graph.initial_business_facts,
                *[fact for action in graph.actions for fact in action.required_facts],
                *[fact for action in graph.actions for fact in action.added_facts],
                *[fact for action in graph.actions for fact in action.removed_facts],
                *[fact for action in graph.actions for fact in action.preserved_facts],
            ]
            if _predicate(fact)
        }
    )
    predicate_names = [f"at_{location}" for location in locations] + facts
    lines = [
        f"(define (domain {normalized_domain_name})",
        "  (:requirements :strips)",
        "  (:predicates",
    ]
    lines.extend(f"    ({name})" for name in sorted(set(predicate_names)))
    lines.append("  )")
    used_action_names: set[str] = set()
    for action in sorted(
        graph.actions,
        key=lambda item: (
            _predicate(item.action_id or item.action_name),
            item.source_location,
            item.target_location,
            item.required_facts,
            item.added_facts,
            item.removed_facts,
        ),
    ):
        lines.extend(_render_action(action, _action_name(action, used_action_names)))
    lines.append(")")
    return MinimalSemanticPddlArtifacts(
        domain="\n".join(lines) + "\n",
        report={
            "domain_name": normalized_domain_name,
            "locations": locations,
            "facts": facts,
        },
    )


def _compiled_state_reachable(
    graph: SemanticPlanningGraph,
    *,
    goal_location: str | None,
    goal_facts: set[str],
) -> bool:
    state = {_predicate(f"at_{graph.start_location}")} | {
        _predicate(fact) for fact in graph.initial_business_facts
    }
    pending = [state]
    seen: set[frozenset[str]] = set()
    while pending:
        current = pending.pop()
        frozen = frozenset(current)
        if frozen in seen:
            continue
        seen.add(frozen)
        if (
            (goal_location is None or _predicate(f"at_{goal_location}") in current)
            and goal_facts.issubset(current)
        ):
            return True
        for action in graph.actions:
            if _predicate(f"at_{action.source_location}") not in current:
                continue
            if not set(_predicate(fact) for fact in action.required_facts).issubset(current):
                continue
            next_state = set(current)
            if action.source_location != action.target_location:
                next_state.discard(_predicate(f"at_{action.source_location}"))
            next_state.add(_predicate(f"at_{action.target_location}"))
            next_state.update(_predicate(fact) for fact in action.added_facts)
            next_state.difference_update(_predicate(fact) for fact in action.removed_facts)
            pending.append(next_state)
    return False


def compile_minimal_semantic_problem(
    graph: SemanticPlanningGraph,
    *,
    goal_location: str | None = None,
    goal_facts: Iterable[str] = (),
    problem_name: str = "web_kobe_semantic_problem",
    domain_name: str = "web_kobe_semantic",
) -> MinimalSemanticPddlArtifacts:
    requested_facts = {_predicate(fact) for fact in goal_facts if _predicate(fact)}
    if goal_location is None and not requested_facts:
        raise ValueError("goal_required")
    known_locations = {_predicate(location) for location in graph.locations}
    known_facts = {
        _predicate(fact)
        for fact in [
            *graph.capability_facts,
            *graph.business_facts,
            *graph.initial_business_facts,
            *[fact for action in graph.actions for fact in action.required_facts],
            *[fact for action in graph.actions for fact in action.added_facts],
            *[fact for action in graph.actions for fact in action.removed_facts],
            *[fact for action in graph.actions for fact in action.preserved_facts],
        ]
    }
    normalized_goal_location = _predicate(goal_location) if goal_location is not None else None
    if normalized_goal_location is not None and normalized_goal_location not in known_locations:
        raise ValueError(f"unknown_goal_location: {goal_location}")
    unknown_facts = requested_facts - known_facts
    if unknown_facts:
        raise ValueError(f"unknown_goal_fact: {sorted(unknown_facts)[0]}")
    if not _compiled_state_reachable(
        graph,
        goal_location=normalized_goal_location,
        goal_facts=requested_facts,
    ):
        raise ValueError("goal_unreachable")
    normalized_domain_name = _domain_name(domain_name)
    normalized_problem_name = _domain_name(problem_name)
    init = [_at(graph.start_location)] + [
        _atom(fact) for fact in sorted(graph.initial_business_facts)
    ]
    goals = ([] if normalized_goal_location is None else [_at(normalized_goal_location)]) + [
        _atom(fact) for fact in sorted(requested_facts)
    ]
    problem = "\n".join(
        [
            f"(define (problem {normalized_problem_name})",
            f"  (:domain {normalized_domain_name})",
            f"  (:init {' '.join(_unique(init))})",
            f"  (:goal (and {' '.join(_unique(goals))}))",
            ")",
            "",
        ]
    )
    return MinimalSemanticPddlArtifacts(
        problem=problem,
        report={
            "problem_name": normalized_problem_name,
            "domain_name": normalized_domain_name,
            "goal_location": normalized_goal_location,
            "goal_facts": sorted(requested_facts),
        },
    )


__all__ = [
    "MinimalSemanticPddlArtifacts",
    "compile_minimal_semantic_domain",
    "compile_minimal_semantic_problem",
]
