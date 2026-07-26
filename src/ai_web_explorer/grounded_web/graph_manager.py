from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from typing import Any

from ai_web_explorer.grounded_web.graph import (
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
    PlanningState,
    PlanningTransition,
)


def _merge_schema(
    existing: dict[str, list[Any]],
    new_snapshot: dict[str, Any],
) -> dict[str, list[Any]]:
    merged = {key: list(values) for key, values in existing.items()}
    for key, value in new_snapshot.items():
        values = merged.setdefault(key, [])
        if value not in values:
            values.append(value)
    return merged


def _merge_interactables(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing]
    for item in incoming:
        incoming_locator = item.get("locator")
        existing_match = next(
            (
                existing_item
                for existing_item in merged
                if incoming_locator and existing_item.get("locator") == incoming_locator
            ),
            None,
        )
        if existing_match is not None:
            if existing_match.get("explored"):
                existing_match["explored"] = True
            continue

        key = (
            item.get("semantic_id"),
            item.get("locator"),
            item.get("description"),
        )
        if key not in {
            (
                merged_item.get("semantic_id"),
                merged_item.get("locator"),
                merged_item.get("description"),
            )
            for merged_item in merged
        }:
            merged.append(dict(item))
    return merged


def _profile_fact_ids(profile: BusinessFlowProfile) -> set[str]:
    return {fact.fact_id for fact in profile.planning_facts}


def _unique_facts(*fact_lists: list[str]) -> list[str]:
    facts: list[str] = []
    for fact_list in fact_lists:
        for fact in fact_list:
            if fact not in facts:
                facts.append(fact)
    return facts


def _trusted_added_facts(delta: PlanningDelta | None) -> list[str]:
    if delta is None:
        return []
    return _unique_facts(delta.candidate_added_facts, delta.verified_added_facts)


def _trusted_removed_facts(delta: PlanningDelta | None) -> list[str]:
    if delta is None:
        return []
    return _unique_facts(delta.candidate_removed_facts, delta.verified_removed_facts)


def _filtered_facts(facts: list[str], *, allowed_facts: set[str]) -> list[str]:
    return [fact for fact in facts if fact in allowed_facts]


class WebKobeGraphManager:
    def __init__(self, app: str):
        self.app = app
        self._nodes: OrderedDict[str, WebKobeNode] = OrderedDict()
        self._edges: OrderedDict[str, WebKobeEdge] = OrderedDict()
        self.total_steps_completed = 0

    def identify_or_add_node(self, node: WebKobeNode) -> str:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = replace(
                node,
                visit_count=max(node.visit_count, 1),
            )
            return node.node_id

        self._nodes[node.node_id] = replace(
            existing,
            state_schema=_merge_schema(existing.state_schema, node.last_state_snapshot),
            last_state_snapshot=dict(node.last_state_snapshot),
            state_indicators=list(node.state_indicators or existing.state_indicators),
            action_targets=list(node.action_targets or existing.action_targets),
            interactable_elements=_merge_interactables(
                existing.interactable_elements,
                node.interactable_elements,
            ),
            capabilities=list(node.capabilities or existing.capabilities),
            reference_observation=node.reference_observation
            or existing.reference_observation,
            visit_count=existing.visit_count + 1,
            evidence=list(existing.evidence or node.evidence),
            node_label=node.node_label or existing.node_label,
            state_summary=node.state_summary or existing.state_summary,
            naming_provenance=node.naming_provenance or existing.naming_provenance,
            planning_state=node.planning_state or existing.planning_state,
        )
        return node.node_id

    def add_edge(self, edge: WebKobeEdge) -> None:
        existing = self._edges.get(edge.edge_id)
        if existing is None:
            self._edges[edge.edge_id] = edge
        else:
            self._edges[edge.edge_id] = replace(
                existing,
                visit_count=existing.visit_count + 1,
                observed_delta=list(edge.observed_delta or existing.observed_delta),
                schema_delta=edge.schema_delta or existing.schema_delta,
                planning_delta=edge.planning_delta or existing.planning_delta,
                planning_transition=edge.planning_transition
                or existing.planning_transition,
                execution_trace=edge.execution_trace,
                evidence=list(existing.evidence or edge.evidence),
            )
        self.total_steps_completed += 1

    def propagate_planning_state(
        self,
        edge: WebKobeEdge,
        *,
        profile: BusinessFlowProfile,
    ) -> WebKobeEdge:
        source = self._nodes[edge.source_node_id]
        target = self._nodes[edge.target_node_id]
        allowed_facts = _profile_fact_ids(profile)

        active_facts = (
            list(source.planning_state.active_facts)
            if source.planning_state is not None
            else []
        )
        active_set = set(active_facts)
        removed_facts = [
            fact
            for fact in _filtered_facts(
                _trusted_removed_facts(edge.planning_delta),
                allowed_facts=allowed_facts,
            )
            if fact in active_set
        ]
        added_facts = _filtered_facts(
            _trusted_added_facts(edge.planning_delta),
            allowed_facts=allowed_facts,
        )

        next_facts = [fact for fact in active_facts if fact not in removed_facts]
        for fact in added_facts:
            if fact not in next_facts:
                next_facts.append(fact)

        evidence = (
            list(source.planning_state.evidence)
            if source.planning_state is not None
            else []
        )
        if added_facts or removed_facts:
            evidence.append(f"propagated from edge {edge.edge_id}")

        transition = PlanningTransition(
            pre_facts=active_facts,
            added_facts=added_facts,
            removed_facts=removed_facts,
            post_facts=next_facts,
            evidence=(
                list(edge.planning_delta.evidence)
                if edge.planning_delta is not None
                else []
            ),
            confidence=(
                edge.planning_delta.confidence
                if edge.planning_delta is not None
                else None
            ),
        )

        self._nodes[edge.target_node_id] = replace(
            target,
            planning_state=PlanningState(
                active_facts=next_facts,
                evidence=evidence,
            ),
        )
        return replace(edge, planning_transition=transition)

    def mark_interactable_explored(
        self,
        node_id: str,
        semantic_id: str,
        locator: str | None = None,
    ) -> None:
        node = self._nodes[node_id]
        interactables = []
        for item in node.interactable_elements:
            updated = dict(item)
            if (locator is not None and updated.get("locator") == locator) or (
                locator is None and updated.get("semantic_id") == semantic_id
            ):
                updated["explored"] = True
            interactables.append(updated)
        self._nodes[node_id] = replace(node, interactable_elements=interactables)

    def interactables_for_node(self, node_id: str) -> list[dict[str, Any]]:
        node = self._nodes[node_id]
        return [dict(item) for item in node.interactable_elements]

    def to_graph(self, start_node_id: str | None = None) -> WebKobeGraph:
        resolved_start = start_node_id
        if resolved_start is None and self._nodes:
            resolved_start = next(iter(self._nodes))
        return WebKobeGraph(
            app=self.app,
            start_node_id=resolved_start or "",
            total_steps_completed=self.total_steps_completed,
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )
