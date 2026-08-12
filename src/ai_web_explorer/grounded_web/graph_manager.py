from __future__ import annotations

import copy
import json
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
from ai_web_explorer.grounded_web.semantic_model import (
    SemanticObservation,
    normalize_semantic_id,
)


_REPLAY_VALIDATION_STATUS = "replay_validation_status"
_REPLAY_VALIDATION_PRIORITY = {
    "unknown": 0,
    "verified": 1,
    "unstable": 2,
}
_EDGE_STATUS_PRIORITY = {
    "failed_execution": 0,
    "no_observed_change": 1,
    "succeeded": 2,
    "succeeded_with_observed_change": 3,
    "succeeded_with_navigation": 3,
    "verified": 4,
}


def _merge_execution_trace_metadata(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(
        {
            key: value
            for key, value in incoming.items()
            if key != "semantic_observation_conflict"
        }
    )
    statuses = [
        status
        for status in (
            existing.get(_REPLAY_VALIDATION_STATUS),
            incoming.get(_REPLAY_VALIDATION_STATUS),
        )
        if status in _REPLAY_VALIDATION_PRIORITY
    ]
    if statuses:
        merged[_REPLAY_VALIDATION_STATUS] = max(
            statuses,
            key=_REPLAY_VALIDATION_PRIORITY.__getitem__,
        )
    else:
        merged.pop(_REPLAY_VALIDATION_STATUS, None)
    return merged


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


def _merge_business_affordances(existing, incoming):
    if existing:
        return list(existing)
    return list(incoming)


def _merge_node_naming(
    existing: WebKobeNode,
    incoming: WebKobeNode,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    existing_source = (existing.naming_provenance or {}).get("source")
    if existing_source == "visual_affordance_vlm":
        return (
            existing.node_label,
            existing.state_summary,
            existing.naming_provenance,
        )
    return (
        incoming.node_label or existing.node_label,
        incoming.state_summary or existing.state_summary,
        incoming.naming_provenance or existing.naming_provenance,
    )


def _normalized_location_hint(value: object) -> str | None:
    normalized = normalize_semantic_id(value) if value else ""
    return normalized or None


def _merge_node_location_hint(
    existing: WebKobeNode,
    incoming: WebKobeNode,
    naming_provenance: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None]:
    existing_hint = _normalized_location_hint(existing.semantic_location_hint)
    incoming_hint = _normalized_location_hint(incoming.semantic_location_hint)
    provenance = dict(naming_provenance or {})
    existing_conflict = provenance.get("semantic_location_hint_conflict") or (
        existing.naming_provenance or {}
    ).get("semantic_location_hint_conflict")
    if existing_conflict:
        candidates = set(existing_conflict.get("candidates", []))
        candidates.update(filter(None, (existing_hint, incoming_hint)))
        for candidate in (
            (incoming.naming_provenance or {})
            .get("semantic_location_hint_conflict", {})
            .get("candidates", [])
        ):
            normalized = _normalized_location_hint(candidate)
            if normalized:
                candidates.add(normalized)
        provenance["semantic_location_hint_conflict"] = {
            "policy": "unresolved_fail_closed",
            "candidates": sorted(candidates),
            "selected": None,
        }
        return None, provenance
    if existing_hint and incoming_hint and existing_hint != incoming_hint:
        candidates = sorted({existing_hint, incoming_hint})
        provenance["semantic_location_hint_conflict"] = {
            "policy": "unresolved_fail_closed",
            "candidates": candidates,
            "selected": None,
        }
        return None, provenance
    return existing_hint or incoming_hint, (provenance or None)


def _semantic_content_dict(observation: SemanticObservation) -> dict[str, Any]:
    canonical = _canonical_observation_dict(observation)
    return {
        key: canonical[key]
        for key in (
            "action_role",
            "source_location",
            "target_location",
            "completion_facts",
            "candidate_required_facts",
            "preserved_facts",
        )
    }


def _canonical_observation_dict(observation: SemanticObservation) -> dict[str, Any]:
    return {
        "action_role": normalize_semantic_id(observation.action_role),
        "source_location": normalize_semantic_id(observation.source_location),
        "target_location": normalize_semantic_id(observation.target_location),
        "completion_facts": sorted(
            {_normalized_location_hint(fact) for fact in observation.completion_facts}
            - {None}
        ),
        "candidate_required_facts": sorted(
            {
                _normalized_location_hint(fact)
                for fact in observation.candidate_required_facts
            }
            - {None}
        ),
        "preserved_facts": sorted(
            {_normalized_location_hint(fact) for fact in observation.preserved_facts}
            - {None}
        ),
        "evidence": sorted({str(item).strip() for item in observation.evidence if str(item).strip()}),
        "confidence": observation.confidence,
    }


def _semantic_identity_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "action_role",
            "source_location",
            "target_location",
            "completion_facts",
            "candidate_required_facts",
            "preserved_facts",
        )
    }


def _semantic_identity_fingerprint(item: dict[str, Any]) -> str:
    return json.dumps(
        _semantic_identity_dict(item),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _merged_confidence(values: list[Any]) -> float | None:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if numeric:
        return min(numeric)
    return None


def _merge_canonical_candidate(
    existing: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(existing)
    merged["evidence"] = sorted(
        set(existing.get("evidence", [])) | set(incoming.get("evidence", []))
    )
    merged["confidence"] = _merged_confidence(
        [existing.get("confidence"), incoming.get("confidence")]
    )
    return merged


def _semantic_content_fingerprint(observation: SemanticObservation) -> str:
    return json.dumps(
        _semantic_content_dict(observation),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _conflict_candidates(
    metadata: dict[str, Any],
    observations: list[SemanticObservation],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    existing = metadata.get("semantic_observation_conflict") or {}
    for item in existing.get("candidates", []):
        if isinstance(item, dict):
            canonical = _canonical_candidate_dict(item)
            key = _semantic_identity_fingerprint(canonical)
            candidates[key] = (
                _merge_canonical_candidate(candidates[key], canonical)
                if key in candidates
                else canonical
            )
    for observation in observations:
        canonical = _canonical_observation_dict(observation)
        key = _semantic_identity_fingerprint(canonical)
        candidates[key] = (
            _merge_canonical_candidate(candidates[key], canonical)
            if key in candidates
            else canonical
        )
    return [candidates[key] for key in sorted(candidates)]


def _canonical_candidate_dict(item: dict[str, Any]) -> dict[str, Any]:
    def facts(key: str) -> list[str]:
        return sorted(
            {
                _normalized_location_hint(value)
                for value in item.get(key, [])
                if _normalized_location_hint(value)
            }
        )

    return {
        "action_role": normalize_semantic_id(item.get("action_role", "")),
        "source_location": normalize_semantic_id(item.get("source_location", "")),
        "target_location": normalize_semantic_id(item.get("target_location", "")),
        "completion_facts": facts("completion_facts"),
        "candidate_required_facts": facts("candidate_required_facts"),
        "preserved_facts": facts("preserved_facts"),
        "evidence": sorted(
            {str(value).strip() for value in item.get("evidence", []) if str(value).strip()}
        ),
        "confidence": item.get("confidence"),
    }


def _merge_same_identity_observations(
    existing: SemanticObservation, incoming: SemanticObservation
) -> SemanticObservation:
    canonical = _canonical_observation_dict(existing)
    merged = _merge_canonical_candidate(
        canonical, _canonical_observation_dict(incoming)
    )
    return SemanticObservation(
        action_role=merged["action_role"],
        source_location=merged["source_location"],
        target_location=merged["target_location"],
        completion_facts=merged["completion_facts"],
        candidate_required_facts=merged["candidate_required_facts"],
        preserved_facts=merged["preserved_facts"],
        evidence=merged["evidence"],
        confidence=merged["confidence"],
    )


def _canonicalize_observation(
    observation: SemanticObservation,
) -> SemanticObservation:
    canonical = _canonical_observation_dict(observation)
    return SemanticObservation(
        action_role=canonical["action_role"],
        source_location=canonical["source_location"],
        target_location=canonical["target_location"],
        completion_facts=canonical["completion_facts"],
        candidate_required_facts=canonical["candidate_required_facts"],
        preserved_facts=canonical["preserved_facts"],
        evidence=canonical["evidence"],
        confidence=canonical["confidence"],
    )


def _merge_semantic_observation(
    existing: SemanticObservation | None,
    incoming: SemanticObservation | None,
    metadata: dict[str, Any],
) -> tuple[SemanticObservation | None, dict[str, Any]]:
    existing_conflict = metadata.get("semantic_observation_conflict")
    if existing_conflict and existing_conflict.get("status") == "unresolved":
        observations = [item for item in (existing, incoming) if item is not None]
        metadata = dict(metadata)
        metadata["semantic_observation_conflict"] = {
            "status": "unresolved",
            "policy": "unresolved_fail_closed",
            "candidates": _conflict_candidates(metadata, observations),
            "selected": None,
        }
        return None, metadata
    if existing is None:
        if incoming is None:
            return None, metadata
        return _canonicalize_observation(incoming), metadata
    if incoming is None:
        return _canonicalize_observation(existing), metadata
    if _semantic_content_fingerprint(existing) == _semantic_content_fingerprint(
        incoming
    ):
        return _merge_same_identity_observations(existing, incoming), metadata
    metadata = dict(metadata)
    metadata["semantic_observation_conflict"] = {
        "status": "unresolved",
        "policy": "unresolved_fail_closed",
        "candidates": _conflict_candidates(metadata, [existing, incoming]),
        "selected": None,
    }
    return None, metadata


def _merge_edge_status(existing: str, incoming: str) -> str:
    existing_priority = _EDGE_STATUS_PRIORITY.get(existing, 0)
    incoming_priority = _EDGE_STATUS_PRIORITY.get(incoming, 0)
    if incoming_priority > existing_priority:
        return incoming
    if existing_priority > incoming_priority:
        return existing
    return min(existing, incoming)


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


def _generated_fact_ids(
    facts: list[str],
    *,
    profile_fact_ids: set[str],
    explicit_generated_fact_ids: list[str],
) -> list[str]:
    explicit = set(explicit_generated_fact_ids)
    return [
        fact
        for fact in facts
        if fact in explicit or fact not in profile_fact_ids
    ]


class WebKobeGraphManager:
    def __init__(self, app: str):
        self.app = app
        self._nodes: OrderedDict[str, WebKobeNode] = OrderedDict()
        self._edges: OrderedDict[str, WebKobeEdge] = OrderedDict()
        self._execution_events: list[WebKobeEdge] = []
        self.total_steps_completed = 0
        self.meta: dict[str, Any] = {}

    @classmethod
    def from_graph(cls, graph: WebKobeGraph) -> "WebKobeGraphManager":
        restored = copy.deepcopy(graph)
        node_ids = [node.node_id for node in restored.nodes]
        edge_ids = [edge.edge_id for edge in restored.edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate_resume_node_id")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate_resume_edge_id")
        manager = cls(app=restored.app)
        manager._nodes = OrderedDict((node.node_id, node) for node in restored.nodes)
        manager._edges = OrderedDict((edge.edge_id, edge) for edge in restored.edges)
        manager._execution_events = copy.deepcopy(restored.execution_events)
        manager.total_steps_completed = restored.total_steps_completed
        manager.meta = copy.deepcopy(restored.meta)
        return manager

    def identify_or_add_node(self, node: WebKobeNode) -> str:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = replace(
                node,
                visit_count=max(node.visit_count, 1),
                semantic_location_hint=_normalized_location_hint(
                    node.semantic_location_hint
                ),
            )
            return node.node_id

        node_label, state_summary, naming_provenance = _merge_node_naming(
            existing,
            node,
        )
        semantic_location_hint, naming_provenance = _merge_node_location_hint(
            existing,
            node,
            naming_provenance,
        )
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
            business_affordances=_merge_business_affordances(
                existing.business_affordances,
                node.business_affordances,
            ),
            capabilities=list(node.capabilities or existing.capabilities),
            reference_observation=node.reference_observation
            or existing.reference_observation,
            visit_count=existing.visit_count + 1,
            evidence=list(existing.evidence or node.evidence),
            node_label=node_label,
            state_summary=state_summary,
            naming_provenance=naming_provenance,
            planning_state=node.planning_state or existing.planning_state,
            semantic_location_hint=semantic_location_hint,
        )
        return node.node_id

    def add_edge(self, edge: WebKobeEdge) -> None:
        self._execution_events.append(edge)
        existing = self._edges.get(edge.edge_id)
        if existing is None:
            self._edges[edge.edge_id] = edge
        else:
            execution_metadata = _merge_execution_trace_metadata(
                existing.execution_trace.metadata,
                edge.execution_trace.metadata,
            )
            semantic_observation, execution_metadata = _merge_semantic_observation(
                existing.semantic_observation,
                edge.semantic_observation,
                execution_metadata,
            )
            merged_status = _merge_edge_status(existing.status, edge.status)
            trace_source = (
                edge.execution_trace
                if edge.execution_trace.success or not existing.execution_trace.success
                else existing.execution_trace
            )
            self._edges[edge.edge_id] = replace(
                existing,
                visit_count=existing.visit_count + 1,
                observed_delta=list(edge.observed_delta or existing.observed_delta),
                schema_delta=edge.schema_delta or existing.schema_delta,
                planning_delta=edge.planning_delta or existing.planning_delta,
                planning_transition=edge.planning_transition
                or existing.planning_transition,
                visual_change_kind=(
                    edge.visual_change_kind
                    if edge.visual_change_kind != "unknown"
                    else existing.visual_change_kind
                ),
                execution_trace=replace(
                    trace_source,
                    success=(
                        existing.execution_trace.success
                        or edge.execution_trace.success
                    ),
                    metadata=execution_metadata,
                ),
                semantic_observation=semantic_observation,
                status=merged_status,
                evidence=list(existing.evidence or edge.evidence),
            )
        self.total_steps_completed += 1

    def update_edge_replay_validation(
        self,
        edge_id: str,
        status: str,
    ) -> None:
        if status not in {"unknown", "verified", "unstable"}:
            raise ValueError(f"invalid_replay_validation_status: {status}")
        edge = self._edges[edge_id]
        metadata = dict(edge.execution_trace.metadata)
        current_status = metadata.get("replay_validation_status", "unknown")
        if current_status == "unstable" and status == "verified":
            return
        metadata["replay_validation_status"] = status
        self._edges[edge_id] = replace(
            edge,
            execution_trace=replace(edge.execution_trace, metadata=metadata),
        )

    def node_for_id(self, node_id: str) -> WebKobeNode:
        return self._nodes[node_id]

    def propagate_planning_state(
        self,
        edge: WebKobeEdge,
        *,
        profile: BusinessFlowProfile,
    ) -> WebKobeEdge:
        transition = self.build_planning_transition(
            edge.source_node_id,
            planning_delta=edge.planning_delta,
            profile=profile,
        )
        updated_edge = replace(edge, planning_transition=transition)
        self.apply_planning_transition(updated_edge, profile=profile)
        return updated_edge

    def build_planning_transition(
        self,
        source_node_id: str,
        *,
        planning_delta: PlanningDelta | None,
        profile: BusinessFlowProfile,
    ) -> PlanningTransition:
        source = self._nodes[source_node_id]
        active_facts = (
            list(source.planning_state.active_facts)
            if source.planning_state is not None
            else []
        )
        active_set = set(active_facts)
        removed_facts = [
            fact
            for fact in _trusted_removed_facts(planning_delta)
            if fact in active_set
        ]
        added_facts = _trusted_added_facts(planning_delta)
        added_facts = [fact for fact in added_facts if fact not in active_set]

        next_facts = [fact for fact in active_facts if fact not in removed_facts]
        for fact in added_facts:
            if fact not in next_facts:
                next_facts.append(fact)

        return PlanningTransition(
            pre_facts=active_facts,
            added_facts=added_facts,
            removed_facts=removed_facts,
            post_facts=next_facts,
            evidence=(
                list(planning_delta.evidence) if planning_delta is not None else []
            ),
            confidence=(
                planning_delta.confidence if planning_delta is not None else None
            ),
        )

    def apply_planning_transition(
        self,
        edge: WebKobeEdge,
        *,
        profile: BusinessFlowProfile | None = None,
    ) -> None:
        if edge.planning_transition is None:
            return
        source = self._nodes[edge.source_node_id]
        target = self._nodes[edge.target_node_id]
        source_profile_facts = (
            list(source.planning_state.profile_fact_ids)
            if source.planning_state is not None
            else []
        )
        source_generated_facts = (
            list(source.planning_state.generated_fact_ids)
            if source.planning_state is not None
            else []
        )
        delta_profile_facts = (
            list(edge.planning_delta.profile_fact_ids)
            if edge.planning_delta is not None
            else []
        )
        delta_generated_facts = (
            list(edge.planning_delta.generated_fact_ids)
            if edge.planning_delta is not None
            else []
        )
        post_facts = list(edge.planning_transition.post_facts)
        profile_fact_ids = [
            fact
            for fact in _unique_facts(
                source_profile_facts,
                delta_profile_facts,
            )
            if fact in post_facts
        ]
        generated_fact_ids = [
            fact
            for fact in _unique_facts(
                source_generated_facts,
                _generated_fact_ids(
                    post_facts,
                    profile_fact_ids=set(profile_fact_ids),
                    explicit_generated_fact_ids=delta_generated_facts,
                ),
            )
            if fact in post_facts and fact not in profile_fact_ids
        ]
        evidence = (
            list(source.planning_state.evidence)
            if source.planning_state is not None
            else []
        )
        if (
            edge.planning_transition.added_facts
            or edge.planning_transition.removed_facts
        ):
            evidence.append(f"propagated from edge {edge.edge_id}")

        self._nodes[edge.target_node_id] = replace(
            target,
            planning_state=PlanningState(
                active_facts=post_facts,
                profile_fact_ids=profile_fact_ids,
                generated_fact_ids=generated_fact_ids,
                evidence=evidence,
            ),
        )

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
            meta=dict(self.meta),
            execution_events=list(self._execution_events),
        )
