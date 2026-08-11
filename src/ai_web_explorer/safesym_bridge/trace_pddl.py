from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ai_web_explorer.grounded_web.graph import WebKobeEdge, WebKobeGraph


TRACE_PROJECTION_SCHEMA_VERSION = "trace-pddl-projection-v1"


@dataclass(frozen=True)
class TraceDomainProjection:
    domain: str
    report: dict[str, Any]


@dataclass(frozen=True)
class TraceProblemProjection:
    problem: str
    start_checkpoint: str
    goal_checkpoint: str


@dataclass(frozen=True)
class _TraceCompilation:
    domain_name: str
    checkpoints: list[dict[str, Any]]
    predicates: list[str]
    actions: list[dict[str, Any]]
    excluded_edges: list[dict[str, str]]


def _stable_digest(edge_id: str, trace_index: int) -> str:
    value = f"{edge_id}:{trace_index}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _normalized_symbol(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not text:
        return ""
    if text[0].isdigit():
        return f"n_{text}"
    return text


def _domain_name(value: str) -> str:
    normalized = _normalized_symbol(value)
    if normalized:
        return normalized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"domain_{digest}"


def _problem_name(value: str) -> str:
    normalized = _normalized_symbol(value)
    if normalized:
        return normalized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"problem_{digest}"


def _action_identity(edge: WebKobeEdge) -> str:
    return (
        edge.action.canonical_action_name or edge.action.semantic_id or ""
    ).strip()


def _exclusion_reason(edge: WebKobeEdge) -> str | None:
    if not edge.execution_trace.success or edge.status == "failed_execution":
        return "failed_execution"
    if not edge.execution_trace.after_observation_id.strip():
        return "missing_after_observation"
    if not _normalized_symbol(_action_identity(edge)):
        return "invalid_action_identity"
    return None


def _unique_name(
    base: str,
    *,
    edge_id: str,
    trace_index: int,
    used_names: set[str],
) -> tuple[str, bool]:
    if base not in used_names:
        used_names.add(base)
        return base, False
    candidate = f"{base}__{_stable_digest(edge_id, trace_index)}"
    used_names.add(candidate)
    return candidate, True


def _render_domain(
    *,
    domain_name: str,
    predicates: list[str],
    actions: list[dict[str, str]],
) -> str:
    lines = [
        f"(define (domain {domain_name})",
        "  (:requirements :strips)",
        "  (:predicates",
    ]
    lines.extend(f"    ({predicate})" for predicate in predicates)
    lines.extend(["  )"])
    for action in actions:
        lines.extend(
            [
                f"  (:action {action['pddl_action']}",
                "    :parameters ()",
                f"    :precondition ({action['source_predicate']})",
                "    :effect (and",
                f"      (not ({action['source_predicate']}))",
                f"      ({action['target_predicate']})",
                "    )",
                "  )",
            ]
        )
    lines.extend([")", ""])
    return "\n".join(lines)


def _compile_trace(
    graph: WebKobeGraph,
    *,
    domain_name: str = "web_kobe_trace",
) -> _TraceCompilation:
    checkpoints: list[dict[str, Any]] = [
        {
            "checkpoint_id": "checkpoint_000",
            "trace_index": 0,
            "pddl_predicate": "state_initial",
            "incoming_raw_edge_id": None,
            "after_observation_id": graph.start_node_id or None,
        }
    ]
    actions: list[dict[str, Any]] = []
    excluded_edges: list[dict[str, str]] = []
    predicates = ["state_initial"]
    used_action_names: set[str] = set()
    used_predicate_names: set[str] = set(predicates)
    trace_index = 0
    source_checkpoint = checkpoints[0]

    for edge in graph.edges:
        reason = _exclusion_reason(edge)
        if reason is not None:
            excluded_edges.append(
                {"raw_edge_id": edge.edge_id, "reason": reason}
            )
            continue

        trace_index += 1
        action_identity = _action_identity(edge)
        action_base = _normalized_symbol(action_identity)
        target_base = f"state_after_{action_base}"
        action_name, action_collided = _unique_name(
            action_base,
            edge_id=edge.edge_id,
            trace_index=trace_index,
            used_names=used_action_names,
        )
        target_predicate, predicate_collided = _unique_name(
            target_base,
            edge_id=edge.edge_id,
            trace_index=trace_index,
            used_names=used_predicate_names,
        )
        collision = action_collided or predicate_collided
        checkpoint_id = f"checkpoint_{trace_index:03d}"
        if collision:
            checkpoint_id = (
                f"{checkpoint_id}__{_stable_digest(edge.edge_id, trace_index)}"
            )
        target_checkpoint = {
            "checkpoint_id": checkpoint_id,
            "trace_index": trace_index,
            "pddl_predicate": target_predicate,
            "incoming_raw_edge_id": edge.edge_id,
            "after_observation_id": edge.execution_trace.after_observation_id,
        }
        checkpoints.append(target_checkpoint)
        predicates.append(target_predicate)
        actions.append(
            {
                "raw_edge_id": edge.edge_id,
                "source_checkpoint_id": source_checkpoint["checkpoint_id"],
                "target_checkpoint_id": checkpoint_id,
                "pddl_action": action_name,
                "source_predicate": source_checkpoint["pddl_predicate"],
                "target_predicate": target_predicate,
                "original_action_identity": action_identity,
                "after_observation_id": edge.execution_trace.after_observation_id,
            }
        )
        source_checkpoint = target_checkpoint

    return _TraceCompilation(
        domain_name=_domain_name(domain_name),
        checkpoints=checkpoints,
        predicates=predicates,
        actions=actions,
        excluded_edges=excluded_edges,
    )


def compile_trace_domain(
    graph: WebKobeGraph,
    *,
    domain_name: str = "web_kobe_trace",
) -> TraceDomainProjection:
    compilation = _compile_trace(graph, domain_name=domain_name)
    report = {
        "schema_version": TRACE_PROJECTION_SCHEMA_VERSION,
        "domain_name": compilation.domain_name,
        "checkpoints": compilation.checkpoints,
        "actions": compilation.actions,
        "excluded_edges": compilation.excluded_edges,
    }
    return TraceDomainProjection(
        domain=_render_domain(
            domain_name=compilation.domain_name,
            predicates=compilation.predicates,
            actions=compilation.actions,
        ),
        report=report,
    )


def compile_trace_problem(
    graph: WebKobeGraph,
    *,
    start_checkpoint_id: str,
    goal_checkpoint_id: str,
    domain_name: str = "web_kobe_trace",
    problem_name: str = "web_kobe_trace_problem",
) -> TraceProblemProjection:
    compilation = _compile_trace(graph, domain_name=domain_name)
    checkpoints = {
        checkpoint["checkpoint_id"]: checkpoint
        for checkpoint in compilation.checkpoints
    }
    if start_checkpoint_id not in checkpoints:
        raise ValueError(f"unknown_start_checkpoint: {start_checkpoint_id}")
    if goal_checkpoint_id not in checkpoints:
        raise ValueError(f"unknown_goal_checkpoint: {goal_checkpoint_id}")
    start_checkpoint = checkpoints[start_checkpoint_id]
    goal_checkpoint = checkpoints[goal_checkpoint_id]
    if start_checkpoint["trace_index"] > goal_checkpoint["trace_index"]:
        raise ValueError(
            "goal_unreachable_in_explored_trace: "
            f"{start_checkpoint_id} -> {goal_checkpoint_id}"
        )
    problem = "\n".join(
        [
            f"(define (problem {_problem_name(problem_name)})",
            f"  (:domain {compilation.domain_name})",
            f"  (:init ({start_checkpoint['pddl_predicate']}))",
            f"  (:goal ({goal_checkpoint['pddl_predicate']}))",
            ")",
            "",
        ]
    )
    return TraceProblemProjection(
        problem=problem,
        start_checkpoint=start_checkpoint_id,
        goal_checkpoint=goal_checkpoint_id,
    )
