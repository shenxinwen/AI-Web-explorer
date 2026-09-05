from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import replace
from typing import Any, Callable
from urllib.parse import urlsplit

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.state_signature import slug_identifier
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager
from ai_web_explorer.grounded_web.business_profile import BusinessFlowProfile
from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    PlanningTransition,
)
from ai_web_explorer.grounded_web.exploration_index import (
    ExplorationContext,
    build_exploration_context,
    semantically_matches_action,
)
from ai_web_explorer.grounded_web.location_exploration import (
    LOCATION_EXPLORATION_META_KEY,
    ExplorationLimits,
    LocationExplorationCoordinator,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.planning_fact_verifier import verify_planning_delta
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)
from ai_web_explorer.grounded_web.state_embedding import (
    EmbeddingProvider,
    StateMatch,
    StateEmbeddingRecord,
    find_best_state_match,
)
from ai_web_explorer.grounded_web.state_summary import build_state_summary
from ai_web_explorer.grounded_web.visual_delta import (
    VisualDeltaProvider,
    VisualDeltaRequest,
    summarize_visual_delta,
)
from ai_web_explorer.grounded_web.action_outcome import (
    ActionOutcomeProvider,
    semantic_observation_from_action_outcome,
    summarize_action_outcome,
)
from ai_web_explorer.grounded_web.resume import (
    ActionAttemptKey,
    ResumePolicy,
    is_action_eligible,
)
from ai_web_explorer.grounded_web.risk_detection import (
    DEFAULT_RISK_TAXONOMY_PATH,
    RiskAssessment,
    RiskDetectionRequest,
    RiskTaxonomy,
    load_risk_taxonomy,
)


OBSERVATION_WAIT_TIMEOUT_MS = 1200
OBSERVATION_WAIT_INTERVAL_MS = 200
CURRENT_NODE_MATCH_THRESHOLD = 0.88
TARGET_NODE_MATCH_THRESHOLD = 0.90


def _url_path(url: str) -> str:
    return urlsplit(url).path or "/"


def _optional_semantic_id(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return normalize_semantic_id(text) if text else ""


def _semantic_location_anchor(node: WebKobeNode) -> tuple[str | None, bool]:
    unresolved = bool(
        (node.naming_provenance or {}).get("semantic_location_hint_conflict")
    )
    if unresolved:
        return None, True
    return _optional_semantic_id(node.semantic_location_hint) or None, False


def _safe_vlm_state_label(value: str | None, *, fallback: str) -> str:
    if value:
        cleaned = slug_identifier(value, fallback="")
        if cleaned:
            return cleaned
    return slug_identifier(fallback, fallback="state")


def observation_change_node_id(
    *,
    source_node_id: str,
    action_name: str,
    after_signature: dict[str, Any],
    added_facts: list[str],
    removed_facts: list[str],
) -> str:
    payload = {
        "source_node_id": source_node_id,
        "action_name": action_name,
        "after_signature": after_signature,
        "added_facts": sorted(set(added_facts)),
        "removed_facts": sorted(set(removed_facts)),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    return f"{source_node_id}__observation_{digest}"


def _node_from_draft(draft) -> WebKobeNode:
    return WebKobeNode(
        node_id=draft.node_id,
        page_description=draft.page_description,
        page_frame=draft.page_frame,
        state_schema=draft.state_schema,
        last_state_snapshot=draft.last_state_snapshot,
        interactable_elements=draft.interactable_elements,
        reference_observation=ReferenceObservation(
            url=draft.page_frame.url,
            title=draft.page_frame.title,
        ),
        evidence=draft.evidence,
        node_label=draft.node_label,
        state_summary=draft.state_summary,
        naming_provenance=draft.naming_provenance,
    )


def _business_action_from_affordance(affordance: BusinessAffordance) -> BrowserAction:
    label = (
        affordance.label or affordance.action_name.replace("_", " ").capitalize()
    ).strip()
    if label and label[-1] not in ".!?":
        label += "."
    details = [label]
    if affordance.target_hint:
        target = affordance.target_hint.strip().rstrip(".")
        details.append(f"Target: {target}.")
    return BrowserAction(
        action_kind="business_intent",
        locator=None,
        semantic_id=affordance.action_name,
        input_values={},
        description=" ".join(details),
        action_label=affordance.label
        or affordance.action_name.replace("_", " ").title(),
        canonical_action_name=affordance.action_name,
        naming_provenance={
            "source": "business_affordance",
            "affordance_source": affordance.source,
            "confidence": affordance.confidence,
        },
        supporting_facts=list(affordance.supporting_facts),
        execution_policy=affordance.execution_policy,
    )


def _affordance_rank(affordance: BusinessAffordance) -> tuple[int, float]:
    relevance_rank = {
        "core": 3,
        "supporting": 2,
        "unknown": 1,
        "low_value": 0,
    }
    return (
        relevance_rank.get(affordance.relevance_hint, 1),
        affordance.confidence or 0.0,
    )


def _schema_observed_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    evidence = [Evidence(source="web_kobe_explorer_schema_diff", url=url)]
    deltas: list[ObservedDelta] = []
    for key, value in (schema_delta(before, after) or {}).items():
        deltas.append(
            ObservedDelta(
                field=key,
                before=value["before"],
                after=value["after"],
                delta_type="state_indicator_change",
                evidence=evidence,
            )
        )
    return deltas


def _observed_delta_from_facts_or_signature(
    *,
    before_facts,
    after_facts,
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    if before_facts is not None and after_facts is not None:
        typed = typed_deltas_from_facts(before_facts, after_facts)
        return observed_deltas_from_typed(typed, url=url)
    return _schema_observed_delta(before_signature, after_signature, url)


def _is_ignorable_stagehand_tool_choice_error(error: str | None) -> bool:
    return bool(error and "Thinking mode does not support this tool_choice" in error)


def _should_advance_current_node(
    *,
    source_id: str,
    target_id: str,
    edge_status: str,
) -> bool:
    if source_id == target_id:
        return False
    if edge_status not in {
        "succeeded_with_navigation",
        "succeeded_with_observed_change",
    }:
        return False
    return True


def _edge_novelty_key(edge: WebKobeEdge) -> tuple[str, str, str]:
    semantic_action = edge.action.canonical_action_name or edge.action.semantic_id
    return (edge.source_node_id, semantic_action, edge.target_node_id)


class WebKobeExplorer:
    def __init__(
        self,
        *,
        adapter: AutomationBackend,
        semantic_assistor: SemanticAssistor,
        goal: str = "Explore the web task.",
        business_profile: BusinessFlowProfile | None = None,
        capture_screenshots: bool = False,
        visual_delta_provider: VisualDeltaProvider | None = None,
        action_outcome_provider: ActionOutcomeProvider | None = None,
        state_embedding_provider: EmbeddingProvider | None = None,
        action_embedding_provider: EmbeddingProvider | None = None,
        state_embedding_records: list[StateEmbeddingRecord] | None = None,
        enable_exploration_memory: bool = False,
        max_candidates: int = 5,
        attempt_checkpoint: Callable[[WebKobeGraph], None] | None = None,
        resume_policy: ResumePolicy | None = None,
        location_exploration_coordinator: LocationExplorationCoordinator | None = None,
        exploration_limits: ExplorationLimits | None = None,
        risk_detection_provider: (
            Callable[[RiskDetectionRequest], RiskAssessment] | None
        ) = None,
        risk_taxonomy: RiskTaxonomy | None = None,
    ):
        if max_candidates < 1:
            raise ValueError("max_candidates must be at least 1.")
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.goal = goal
        self.business_profile = business_profile
        self.max_candidates = max_candidates
        self.capture_screenshots = capture_screenshots
        self.visual_delta_provider = visual_delta_provider
        self.action_outcome_provider = action_outcome_provider
        self.risk_detection_provider = risk_detection_provider
        self.risk_taxonomy = (
            risk_taxonomy
            if risk_taxonomy is not None
            else (
                load_risk_taxonomy(DEFAULT_RISK_TAXONOMY_PATH)
                if risk_detection_provider is not None
                else None
            )
        )
        self.state_embedding_provider = state_embedding_provider
        self.action_embedding_provider = action_embedding_provider
        self.state_embedding_records = list(state_embedding_records or [])
        self.enable_exploration_memory = enable_exploration_memory
        self.attempt_checkpoint = attempt_checkpoint
        self.resume_policy = resume_policy
        self.location_exploration_coordinator = (
            location_exploration_coordinator
            or LocationExplorationCoordinator(
                limits=exploration_limits,
            )
        )
        self._preferred_resume_action_key: ActionAttemptKey | None = None
        self.manager = WebKobeGraphManager(app=adapter.app_name)
        self._start_node_id: str | None = None
        self._current_node_id: str | None = None
        self._replay_handoff_pending = False
        self._visit_stack: list[str] = []
        self._visual_affordance_observed_node_ids: set[str] = set()

    @property
    def start_node_id(self) -> str | None:
        return self._start_node_id

    def restore_graph(self, graph: WebKobeGraph) -> None:
        if graph.app != self.adapter.app_name:
            raise ValueError("resume_app_mismatch")
        self.manager = WebKobeGraphManager.from_graph(graph)
        persisted_memory = graph.meta.get(LOCATION_EXPLORATION_META_KEY)
        if persisted_memory is not None:
            self.location_exploration_coordinator = LocationExplorationCoordinator(
                memory=LocationExplorationMemory.from_dict(persisted_memory),
            )
        else:
            self._seed_location_memory_from_graph(graph)
        self._start_node_id = graph.start_node_id
        self._current_node_id = None
        self._replay_handoff_pending = False
        self._visit_stack = []
        self._visual_affordance_observed_node_ids = {
            node.node_id for node in graph.nodes if node.business_affordances
        }

    def _seed_location_memory_from_graph(self, graph: WebKobeGraph) -> None:
        """Migrate legacy node snapshots into location memory without rewriting meta."""

        coordinator = self.location_exploration_coordinator
        for node in graph.nodes:
            location_id, unresolved = _semantic_location_anchor(node)
            if unresolved or not location_id:
                continue
            if node.business_affordances:
                coordinator.memory.merge_scan(
                    location_id,
                    node.business_affordances,
                    kind="initial",
                )
        nodes_by_id = {node.node_id: node for node in graph.nodes}
        for edge in graph.edges:
            source = nodes_by_id.get(edge.source_node_id)
            if source is None:
                continue
            location_id, unresolved = _semantic_location_anchor(source)
            if unresolved or not location_id:
                continue
            action_id = edge.action.canonical_action_name or edge.action.semantic_id
            pool = coordinator.memory.pool_for(location_id)
            if normalize_semantic_id(action_id) not in pool.candidates:
                continue
            coordinator.memory.record_attempt(
                location_id,
                action_id,
                observable_change=edge.status
                in {
                    "succeeded",
                    "succeeded_with_observed_change",
                    "succeeded_with_navigation",
                },
                failed=edge.status == "failed_execution",
            )

    def prefer_resume_action(self, key: ActionAttemptKey) -> None:
        self._preferred_resume_action_key = key

    async def explore_one_step(self) -> WebKobeGraph:
        before = await self.adapter.observe_state()
        before_facts = getattr(self.adapter, "last_state_facts", None)
        before_interactables = await self.adapter.list_interactables(before)
        before_draft = self.semantic_assistor.describe_state(
            snapshot=before,
            interactables=before_interactables,
        )
        current_pointer_id = self._current_node_id
        if current_pointer_id is not None:
            try:
                self.manager.node_for_id(current_pointer_id)
            except KeyError:
                self._current_node_id = None
                current_pointer_id = None
        source_id = (
            current_pointer_id
            if current_pointer_id is not None
            else self.manager.identify_or_add_node(_node_from_draft(before_draft))
        )
        if self._start_node_id is None:
            self._start_node_id = source_id
        source_id = self._current_source_id(default_source_id=source_id)
        source_match = self._match_current_state(
            before=before,
            before_interactables=before_interactables,
        )
        source_id, accepted_source_match = self._resolve_current_source_id(
            default_source_id=source_id,
            source_match=source_match,
        )
        self._record_visit_node(source_id)
        if source_id != before_draft.node_id:
            self._refresh_matched_source_node(
                source_id=source_id,
                before_draft=before_draft,
            )
        source_node = self.manager.node_for_id(source_id)
        source_anchor, anchor_unresolved = _semantic_location_anchor(source_node)
        if (
            source_anchor
            and not anchor_unresolved
            and source_node.semantic_location_hint != source_anchor
        ):
            self.manager.identify_or_add_node(
                replace(source_node, semantic_location_hint=source_anchor)
            )
            source_node = self.manager.node_for_id(source_id)
        self._ensure_source_embedding(
            node_id=source_id,
            before=before,
            before_interactables=before_interactables,
        )
        before_screenshot_path = await self._capture_screenshot("before")
        if before_screenshot_path is not None:
            self._record_source_business_affordances(
                source_id=source_id,
                before=before,
                before_screenshot_path=before_screenshot_path,
            )
            source_node = self.manager.node_for_id(source_id)
            source_anchor, anchor_unresolved = _semantic_location_anchor(source_node)
        exploration_context = self._exploration_context_for_source(
            source_id=source_id,
            state_match=accepted_source_match,
        )
        set_context = getattr(self.adapter, "set_exploration_context", None)
        if set_context is not None:
            set_context(exploration_context.to_prompt_block())

        selected = self._select_action(
            exploration_context=exploration_context,
            current_interactables=before_interactables,
        )
        if selected is None:
            self.manager.meta.setdefault("formal_action_attempts", 0)
            self.manager.meta["last_step_kind"] = "current_state_exhausted"
            self.manager.meta["last_step_status"] = "unproductive"
            self.manager.meta["last_step_graph_changed"] = False
            return self.manager.to_graph(start_node_id=self._start_node_id)

        formal_attempts = int(self.manager.meta.get("formal_action_attempts", 0))
        max_attempts = (
            self.location_exploration_coordinator.memory.limits.max_exploration_steps
        )
        if formal_attempts >= max_attempts:
            self.manager.meta["last_step_kind"] = "formal_action_budget_exhausted"
            self.manager.meta["last_step_status"] = "unproductive"
            self.manager.meta["last_step_graph_changed"] = False
            self.manager.meta["last_step_semantic_progress"] = False
            return self.manager.to_graph(start_node_id=self._start_node_id)

        replay_handoff_active = self._replay_handoff_pending
        self._replay_handoff_pending = False
        attempt_id = self._begin_action_attempt(
            source_id=source_id,
            action=selected,
        )
        risk_detection_metadata = self._assess_action_risk(
            action=selected,
            screenshot_path=before_screenshot_path,
        )
        execution_success = await self.adapter.execute(selected)
        execution_error = getattr(self.adapter, "last_execution_error", None)
        observation_allowed = (
            execution_success
            or _is_ignorable_stagehand_tool_choice_error(execution_error)
        )
        if observation_allowed:
            after = await self._observe_after_action(
                before=before,
                before_facts=before_facts,
                execution_success=True,
            )
            after_screenshot_path = await self._capture_screenshot("after")
            after_interactables = await self.adapter.list_interactables(after)
            after_draft = self.semantic_assistor.describe_state(
                snapshot=after,
                interactables=after_interactables,
            )
        else:
            after = before
            after_screenshot_path = None
            after_interactables = before_interactables
            after_draft = before_draft

        delta = schema_delta(
            before_draft.last_state_snapshot,
            after_draft.last_state_snapshot,
        )
        observed_delta = (
            _observed_delta_from_facts_or_signature(
                before_facts=before_facts,
                after_facts=getattr(self.adapter, "last_state_facts", None),
                before_signature=before.signature,
                after_signature=after.signature,
                url=after.url,
            )
            if observation_allowed
            else []
        )
        edge_status = self._edge_status(
            execution_success=execution_success,
            execution_error=execution_error,
            observed_delta=observed_delta,
        )
        execution_metadata = dict(
            getattr(self.adapter, "last_execution_metadata", {}) or {}
        )
        execution_metadata["backend_reported_success"] = execution_success
        execution_metadata["attempt_id"] = attempt_id
        execution_metadata.update(risk_detection_metadata)
        if source_match is not None:
            execution_metadata["source_state_match"] = {
                "status": source_match.status,
                "node_id": source_match.node_id,
                "score": source_match.score,
                "blocked_reason": source_match.blocked_reason,
                "accepted": accepted_source_match is not None,
            }
        if before_screenshot_path is not None:
            execution_metadata["before_screenshot_path"] = before_screenshot_path
        if after_screenshot_path is not None:
            execution_metadata["after_screenshot_path"] = after_screenshot_path
        structured_planning_delta = (
            verify_planning_delta(
                profile=self.business_profile,
                before_signature=before.signature,
                after_signature=after.signature,
            )
            if self.business_profile is not None
            else None
        )
        visual_delta_facts = ([], [])
        visual_delta_evidence: list[str] = []
        visual_change_kind = "unknown"
        semantic_observation = None
        visual_observable_change = False
        action_outcome_result = None
        source_location_hint = None if anchor_unresolved else source_anchor
        allowed_location_ids = sorted(
            {
                node.semantic_location_hint
                for node in self.manager.to_graph().nodes
                if node.semantic_location_hint
            }
        )
        if (
            observation_allowed
            and self.action_outcome_provider is not None
            and before_screenshot_path is not None
            and after_screenshot_path is not None
        ):
            action_outcome_result = summarize_action_outcome(
                before_screenshot_path=before_screenshot_path,
                after_screenshot_path=after_screenshot_path,
                action_description=selected.description or selected.semantic_id,
                provider=self.action_outcome_provider,
            )
            if action_outcome_result.trace is not None:
                execution_metadata["action_outcome_trace"] = (
                    action_outcome_result.trace.to_dict()
                )
            visual_delta_evidence = list(action_outcome_result.evidence)
            visual_observable_change = action_outcome_result.outcome == "success"
            visual_change_kind = (
                "surface" if action_outcome_result.location_change else "none"
            )
        elif (
            observation_allowed
            and self.visual_delta_provider is not None
            and before_screenshot_path is not None
            and after_screenshot_path is not None
        ):
            visual_result = summarize_visual_delta(
                VisualDeltaRequest(
                    goal=self.goal,
                    action=selected,
                    before_screenshot_path=before_screenshot_path,
                    after_screenshot_path=after_screenshot_path,
                    before_signature=before.signature,
                    after_signature=after.signature,
                    source_location_hint=source_location_hint,
                    source_location_hint_confirmed=bool(source_location_hint),
                    source_location_anchor_unresolved=anchor_unresolved,
                    allowed_location_ids=allowed_location_ids,
                    current_location_context=(
                        source_node.state_summary or source_node.page_description
                    ),
                ),
                provider=self.visual_delta_provider,
            )
            visual_delta_facts = (
                list(visual_result.planning_delta.candidate_added_facts),
                list(visual_result.planning_delta.candidate_removed_facts),
            )
            visual_delta_evidence = list(visual_result.planning_delta.evidence)
            visual_change_kind = visual_result.visual_change_kind
            semantic_observation = visual_result.semantic_observation
            visual_observable_change = visual_result.observable_change
            visual_trace = visual_result.trace.to_dict()
            visual_trace["candidate_added_facts"] = list(visual_delta_facts[0])
            visual_trace["candidate_removed_facts"] = list(visual_delta_facts[1])
            execution_metadata["visual_delta_trace"] = visual_trace

        planning_delta = structured_planning_delta
        planning_transition = None
        visual_fact_change = bool(visual_delta_facts[0] or visual_delta_facts[1])
        path_changed = _url_path(before.url) != _url_path(after.url)
        signature_changed = before.signature != after.signature
        visual_kind_change = visual_change_kind in {
            "presentation",
            "state_indicator",
            "surface",
            "mixed",
        }
        state_changed = (
            path_changed
            or signature_changed
            or visual_fact_change
            or visual_kind_change
            or visual_observable_change
            or bool(
                action_outcome_result is not None
                and action_outcome_result.location_change
            )
        )
        if self.business_profile is not None:
            planning_transition = self.manager.build_planning_transition(
                source_id,
                planning_delta=planning_delta,
                profile=self.business_profile,
            )

        target_node = _node_from_draft(after_draft)
        outcome_location_hint = source_location_hint
        outcome_location_change_accepted = bool(
            action_outcome_result is not None
            and action_outcome_result.outcome == "success"
            and action_outcome_result.location_change
        )
        if outcome_location_change_accepted:
            outcome_location_hint = (
                _optional_semantic_id(after_draft.page_frame.page_type)
                or _optional_semantic_id(after.page_id)
                or source_location_hint
            )
        target_node = replace(
            target_node,
            semantic_location_hint=(
                None
                if outcome_location_change_accepted
                else (
                    semantic_observation.target_location
                    if semantic_observation is not None
                    else source_location_hint
                )
            ),
        )
        if not observation_allowed or not state_changed:
            target_node = self.manager.node_for_id(source_id)
        elif not path_changed:
            action_name = selected.canonical_action_name or selected.semantic_id
            target_node = replace(
                target_node,
                node_id=observation_change_node_id(
                    source_node_id=source_id,
                    action_name=action_name,
                    after_signature=after.signature,
                    added_facts=visual_delta_facts[0],
                    removed_facts=visual_delta_facts[1],
                ),
            )
        if action_outcome_result is not None:
            semantic_observation = semantic_observation_from_action_outcome(
                action_outcome_result,
                source_location=source_location_hint or source_id,
                target_location_hint=outcome_location_hint,
                target_node_id=target_node.node_id,
            )

        target_match = None
        if state_changed:
            target_node, target_match = self._match_existing_target_node(
                target_node=target_node,
                after=after,
                after_interactables=after_interactables,
                planning_transition=planning_transition,
                source_node_id=source_id,
                has_explicit_change=state_changed,
            )
        if target_match is not None:
            execution_metadata["target_state_match"] = {
                "status": target_match.status,
                "node_id": target_match.node_id,
                "score": target_match.score,
                "blocked_reason": target_match.blocked_reason,
                "accepted": target_node.node_id == target_match.node_id,
            }
        known_node_ids = {node.node_id for node in self.manager.to_graph().nodes}
        target_id = self.manager.identify_or_add_node(target_node)
        node_was_new = target_id not in known_node_ids

        replay_handoff_location = None
        if replay_handoff_active and outcome_location_change_accepted:
            replay_handoff_location = self._unique_location_for_url_pattern(
                after_draft.page_frame.url_pattern
            )
            if replay_handoff_location:
                outcome_location_hint = replay_handoff_location
                semantic_observation = semantic_observation_from_action_outcome(
                    action_outcome_result,
                    source_location=source_location_hint or source_id,
                    target_location_hint=replay_handoff_location,
                    target_node_id=target_id,
                )
                self.manager.identify_or_add_node(
                    replace(
                        self.manager.node_for_id(target_id),
                        semantic_location_hint=replay_handoff_location,
                    )
                )
                self._sync_location_affordance_snapshots(replay_handoff_location)

        location_scan_novel = False
        if (
            outcome_location_change_accepted
            and replay_handoff_location is None
            and after_screenshot_path is not None
            and self.visual_delta_provider is not None
        ):
            provisional_target = normalize_semantic_id(target_id)
            target_location, target_result, target_added = (
                self.location_exploration_coordinator.ensure_candidates(
                    provisional_target,
                    goal=self.goal,
                    screenshot_path=after_screenshot_path,
                    current_signature=after.signature,
                    provider=self.visual_delta_provider,
                    max_actions=self.max_candidates,
                    scan_kind="initial",
                )
            )
            if target_result is not None and target_result.location_id:
                location_scan_novel = bool(target_added)
                outcome_location_hint = target_location
                semantic_observation = semantic_observation_from_action_outcome(
                    action_outcome_result,
                    source_location=source_location_hint or source_id,
                    target_location_hint=target_location,
                    target_node_id=target_id,
                )
                self.manager.identify_or_add_node(
                    replace(
                        self.manager.node_for_id(target_id),
                        semantic_location_hint=target_location,
                    )
                )
                self._sync_location_affordance_snapshots(target_location)
        if edge_status == "no_observed_change" and (
            visual_fact_change or visual_kind_change
        ):
            edge_status = "succeeded_with_observed_change"
        if action_outcome_result is not None:
            if action_outcome_result.outcome == "failed":
                edge_status = "failed_execution"
            elif action_outcome_result.outcome == "uncertain":
                edge_status = "no_observed_change"
            elif (
                action_outcome_result.outcome == "success"
                and edge_status == "no_observed_change"
            ):
                edge_status = "succeeded"
        allow_outcome_navigation = (
            action_outcome_result is None or outcome_location_change_accepted
        )
        if (
            allow_outcome_navigation
            and source_id != target_id
            and edge_status in {"no_observed_change", "failed_execution"}
        ):
            edge_status = "succeeded_with_navigation"
        self._record_state_embedding(
            node_id=target_id,
            after=after,
            after_interactables=after_interactables,
            active_planning_facts=(
                planning_transition.post_facts
                if planning_transition is not None
                else []
            ),
        )
        location_before = source_anchor or _optional_semantic_id(source_id)
        location_after = (
            semantic_observation.target_location
            if semantic_observation is not None
            else outcome_location_hint or location_before
        )
        outcome_is_non_success = bool(
            action_outcome_result is not None
            and action_outcome_result.outcome != "success"
        )
        completion_facts = (
            list(semantic_observation.completion_facts)
            if semantic_observation is not None
            else []
        )
        business_added = (
            list(planning_delta.verified_added_facts)
            if planning_delta is not None
            else []
        )
        business_removed = (
            list(planning_delta.verified_removed_facts)
            if planning_delta is not None
            else []
        )
        outcome = self.location_exploration_coordinator.record_action_outcome(
            location_before=location_before,
            location_after=location_after,
            action_id=selected.canonical_action_name or selected.semantic_id,
            observable_change=(
                False
                if outcome_is_non_success
                else bool(
                    observed_delta
                    or state_changed
                    or (
                        action_outcome_result is not None
                        and action_outcome_result.outcome == "success"
                    )
                )
            ),
            completion_facts=completion_facts,
            business_added=business_added,
            business_removed=business_removed,
            failed=(
                edge_status == "failed_execution"
                or (
                    action_outcome_result is not None
                    and action_outcome_result.outcome == "failed"
                )
            ),
        )
        required_action_ids: list[str] = []
        candidate_record = self.location_exploration_coordinator.memory.pool_for(
            location_before
        ).candidates.get(
            normalize_semantic_id(
                selected.canonical_action_name or selected.semantic_id
            )
        )
        if candidate_record is not None:
            required_action_ids = list(candidate_record.requires)
        edge = WebKobeEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            instruction=selected.description or selected.semantic_id,
            action=selected,
            capability=None,
            target_observation=after_draft.page_description,
            observed_delta=observed_delta,
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind=selected.action_kind,
                concrete_locator=selected.locator,
                concrete_target_sample=selected.semantic_id,
                input_values_used=dict(selected.input_values),
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=edge_status != "failed_execution",
                error=execution_error,
                metadata=execution_metadata,
            ),
            planning_delta=planning_delta,
            planning_transition=planning_transition,
            semantic_observation=semantic_observation,
            required_action_ids=required_action_ids,
            visual_change_kind=visual_change_kind,
            status=edge_status,
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        if self.business_profile is not None and edge_status != "failed_execution":
            self.manager.apply_planning_transition(edge)
        known_edge_keys = {
            _edge_novelty_key(existing_edge)
            for existing_edge in self.manager.to_graph().edges
        }
        edge_was_new = _edge_novelty_key(edge) not in known_edge_keys
        self.manager.add_edge(edge)
        if (
            action_outcome_result is not None
            and outcome.new_location
            and after_screenshot_path is not None
            and self.visual_delta_provider is not None
        ):
            _target_location, _target_result, target_added = (
                self.location_exploration_coordinator.ensure_candidates(
                    location_after,
                    goal=self.goal,
                    screenshot_path=after_screenshot_path,
                    current_signature=after.signature,
                    provider=self.visual_delta_provider,
                    max_actions=self.max_candidates,
                    scan_kind="initial",
                )
            )
            location_scan_novel = location_scan_novel or bool(target_added)
            self._sync_location_affordance_snapshots(location_after)
        self.manager.meta.pop("inflight_action", None)
        graph_changed = node_was_new or edge_was_new
        self.manager.meta["last_step_kind"] = "business_edge"
        self.manager.meta["last_step_graph_changed"] = graph_changed
        self.manager.meta["last_step_semantic_progress"] = bool(
            outcome.has_progress or location_scan_novel
        )
        self.manager.meta["last_step_kind"] = (
            "initial_location_scan" if location_scan_novel else outcome.step_kind
        )
        self.manager.meta["last_step_status"] = (
            "productive" if graph_changed else "unproductive"
        )
        self.location_exploration_coordinator.sync_graph_meta(self.manager)
        if _should_advance_current_node(
            source_id=source_id,
            target_id=target_id,
            edge_status=edge_status,
        ):
            self._set_current_node(target_id)
        elif self._current_node_id is None:
            self._set_current_node(source_id)
        self.manager.meta["resume_cursor_node_id"] = self._current_node_id or source_id
        return self.manager.to_graph(start_node_id=self._start_node_id)

    def _sync_location_affordance_snapshots(self, location_id: str) -> None:
        normalized_location = _optional_semantic_id(location_id)
        affordances = self.location_exploration_coordinator.affordances_for(
            normalized_location
        )
        graph = self.manager.to_graph(start_node_id=self._start_node_id)
        for node in graph.nodes:
            node_location, unresolved = _semantic_location_anchor(node)
            if unresolved or node_location != normalized_location:
                continue
            self.manager.identify_or_add_node(
                replace(node, business_affordances=list(affordances))
            )

    def _begin_action_attempt(self, *, source_id: str, action: BrowserAction) -> str:
        attempt_id = uuid.uuid4().hex
        self.manager.meta["formal_action_attempts"] = (
            int(self.manager.meta.get("formal_action_attempts", 0)) + 1
        )
        self.manager.meta["inflight_action"] = {
            "attempt_id": attempt_id,
            "source_node_id": source_id,
            "action_id": action.canonical_action_name or action.semantic_id,
        }
        if self.attempt_checkpoint is not None:
            self.attempt_checkpoint(self.manager.to_graph(self._start_node_id))
        return attempt_id

    def _match_existing_target_node(
        self,
        *,
        target_node: WebKobeNode,
        after: StateSnapshot,
        after_interactables: list[dict[str, Any]],
        planning_transition: PlanningTransition | None,
        source_node_id: str | None = None,
        has_explicit_change: bool = False,
    ) -> tuple[WebKobeNode, StateMatch | None]:
        if (
            not self.enable_exploration_memory
            or self.state_embedding_provider is None
            or not self.state_embedding_records
        ):
            return target_node, None
        target_summary = build_state_summary(
            snapshot=after,
            interactables=after_interactables,
            active_planning_facts=(
                planning_transition.post_facts
                if planning_transition is not None
                else []
            ),
        )
        target_match = find_best_state_match(
            target_summary,
            self.state_embedding_records,
            embedding_provider=self.state_embedding_provider,
            same_threshold=TARGET_NODE_MATCH_THRESHOLD,
        )
        if target_match.status != "same" or target_match.node_id is None:
            return target_node, target_match
        try:
            existing = self.manager.node_for_id(target_match.node_id)
        except KeyError:
            return target_node, target_match
        if has_explicit_change:
            return target_node, replace(
                target_match,
                status="blocked",
                blocked_reason="explicit_observation_change",
            )
        if not self._has_known_revisit_evidence(
            default_node_id=source_node_id,
            matched_node_id=existing.node_id,
        ):
            return target_node, replace(
                target_match,
                status="blocked",
                blocked_reason="embedding_only",
            )
        return (
            replace(
                target_node,
                node_id=existing.node_id,
                node_label=existing.node_label or target_node.node_label,
                state_summary=target_node.state_summary or existing.state_summary,
                naming_provenance=(
                    target_node.naming_provenance or existing.naming_provenance
                ),
                planning_state=existing.planning_state,
            ),
            target_match,
        )

    def _has_known_revisit_evidence(
        self,
        *,
        default_node_id: str | None,
        matched_node_id: str,
    ) -> bool:
        if default_node_id == matched_node_id:
            return True
        if matched_node_id == self._current_node_id:
            return True
        if default_node_id is None:
            return False
        graph = self.manager.to_graph()
        return any(
            {
                edge.source_node_id,
                edge.target_node_id,
            }
            == {default_node_id, matched_node_id}
            for edge in graph.edges
        )

    def _set_current_node(self, node_id: str) -> None:
        self._current_node_id = node_id
        self._record_visit_node(node_id)

    def restore_replay_context(self, node_id: str) -> None:
        """Restore a frontier and enable one URL-based handoff lookup."""

        self._set_current_node(node_id)
        self._replay_handoff_pending = True

    def _unique_location_for_url_pattern(self, url_pattern: str) -> str | None:
        locations: set[str] = set()
        for node in self.manager.to_graph().nodes:
            if node.page_frame.url_pattern != url_pattern:
                continue
            location_id, unresolved = _semantic_location_anchor(node)
            if location_id and not unresolved:
                locations.add(location_id)
        if len(locations) != 1:
            return None
        return next(iter(locations))

    async def execute_replay_action(self, action: BrowserAction) -> bool:
        """Execute one stored action without recording a new exploration edge."""
        if self.risk_detection_provider is not None:
            audits = self.manager.meta.setdefault("replay_risk_assessments", [])
            screenshot_path = None
            capture = getattr(self.adapter, "capture_screenshot", None)
            if self.capture_screenshots and capture is not None:
                screenshot_path = await capture(f"replay_before_{len(audits) + 1:04d}")
            candidate_label = self._risk_candidate_label(action)
            audit = {
                "action_id": action.canonical_action_name or action.semantic_id,
                "candidate_label": candidate_label,
                "screenshot_path": screenshot_path,
            }
            audit.update(
                self._assess_action_risk(
                    action=action,
                    screenshot_path=screenshot_path,
                )
            )
            audits.append(audit)
        replay_execute = getattr(self.adapter, "execute_replay_action", None)
        if replay_execute is not None:
            return await replay_execute(action)
        return await self.adapter.execute(action)

    @staticmethod
    def _risk_candidate_label(action: BrowserAction) -> str:
        return action.action_label or action.description or action.semantic_id

    def _assess_action_risk(
        self,
        *,
        action: BrowserAction,
        screenshot_path: str | None,
    ) -> dict[str, Any]:
        if self.risk_detection_provider is None or self.risk_taxonomy is None:
            return {}
        if screenshot_path is None:
            return {
                "risk_detection_error": {
                    "type": "ScreenshotUnavailable",
                    "message": "A screenshot is required for risk detection.",
                }
            }
        try:
            assessment = self.risk_detection_provider(
                RiskDetectionRequest(
                    screenshot_path=screenshot_path,
                    candidate_label=self._risk_candidate_label(action),
                    taxonomy=self.risk_taxonomy,
                )
            )
            return {"risk_assessment": assessment.to_dict()}
        except Exception as error:
            return {
                "risk_detection_error": {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            }

    def mark_replay_edge_validation(self, edge_id: str, status: str) -> None:
        self.manager.update_edge_replay_validation(edge_id, status)

    def _record_visit_node(self, node_id: str) -> None:
        if not self._visit_stack:
            self._visit_stack.append(node_id)
            return
        if self._visit_stack[-1] == node_id:
            return
        if node_id in self._visit_stack:
            index = self._visit_stack.index(node_id)
            self._visit_stack = self._visit_stack[: index + 1]
            return
        self._visit_stack.append(node_id)

    def _record_source_business_affordances(
        self,
        *,
        source_id: str,
        before: StateSnapshot,
        before_screenshot_path: str,
    ) -> None:
        if self.visual_delta_provider is None:
            return
        source_node = self.manager.node_for_id(source_id)
        source_anchor, anchor_unresolved = _semantic_location_anchor(source_node)
        if anchor_unresolved:
            return
        scan_anchor = source_anchor or normalize_semantic_id(source_node.node_id)
        coordinator = self.location_exploration_coordinator
        pool = coordinator.memory.pool_for(scan_anchor)
        if source_node.business_affordances and not pool.initial_scan_complete:
            coordinator.memory.merge_scan(
                scan_anchor,
                source_node.business_affordances,
                kind="initial",
            )
        if pool.initial_scan_complete:
            affordances = coordinator.affordances_for(scan_anchor)
            if affordances and affordances != source_node.business_affordances:
                self.manager.identify_or_add_node(
                    replace(source_node, business_affordances=affordances)
                )
            self._visual_affordance_observed_node_ids.add(source_id)
            return
        effective_location, result, _added = coordinator.ensure_candidates(
            scan_anchor,
            goal=self.goal,
            screenshot_path=before_screenshot_path,
            current_signature=before.signature,
            provider=self.visual_delta_provider,
            max_actions=self.max_candidates,
            scan_kind="initial",
        )
        if result is None or result.trace.status != "summarized":
            return
        if result.location_id:
            source_anchor = effective_location
        elif source_anchor is None:
            return
        if source_node.semantic_location_hint != source_anchor:
            source_node = replace(source_node, semantic_location_hint=source_anchor)
        self._visual_affordance_observed_node_ids.add(source_id)
        affordances = coordinator.affordances_for(source_anchor)
        fallback_label = (
            source_node.node_label
            or source_node.page_frame.page_type
            or source_node.node_id
        )
        accepted_vlm_label = bool(
            result.state_label and slug_identifier(result.state_label, fallback="")
        )
        self.manager.identify_or_add_node(
            replace(
                source_node,
                business_affordances=affordances,
                state_summary=result.state_summary or source_node.state_summary,
                node_label=_safe_vlm_state_label(
                    result.state_label,
                    fallback=fallback_label,
                ),
                naming_provenance=(
                    {"source": "visual_affordance_vlm"}
                    if accepted_vlm_label
                    else source_node.naming_provenance
                ),
            )
        )

    async def _capture_screenshot(self, phase: str) -> str | None:
        if not self.capture_screenshots:
            return None
        capture = getattr(self.adapter, "capture_screenshot", None)
        if capture is None:
            return None
        label = f"{phase}_{self.manager.total_steps_completed + 1:04d}"
        return await capture(label)

    async def _observe_after_action(
        self,
        *,
        before: StateSnapshot,
        before_facts,
        execution_success: bool,
    ) -> StateSnapshot:
        after = await self.adapter.observe_state()
        if not execution_success:
            return after

        observed_delta = _observed_delta_from_facts_or_signature(
            before_facts=before_facts,
            after_facts=getattr(self.adapter, "last_state_facts", None),
            before_signature=before.signature,
            after_signature=after.signature,
            url=after.url,
        )
        if observed_delta:
            return after

        timeout_s = OBSERVATION_WAIT_TIMEOUT_MS / 1000
        interval_s = OBSERVATION_WAIT_INTERVAL_MS / 1000
        deadline = asyncio.get_running_loop().time() + timeout_s
        current = after
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return current
            await asyncio.sleep(min(interval_s, remaining))
            current = await self.adapter.observe_state()
            observed_delta = _observed_delta_from_facts_or_signature(
                before_facts=before_facts,
                after_facts=getattr(self.adapter, "last_state_facts", None),
                before_signature=before.signature,
                after_signature=current.signature,
                url=current.url,
            )
            if observed_delta:
                return current

    def _edge_status(
        self,
        *,
        execution_success: bool,
        execution_error: str | None,
        observed_delta: list[ObservedDelta],
    ) -> str:
        if observed_delta:
            return "succeeded_with_observed_change"
        if _is_ignorable_stagehand_tool_choice_error(execution_error):
            return "no_observed_change"
        if not execution_success:
            return "failed_execution"
        return "no_observed_change"

    def _exploration_context_for_source(
        self,
        *,
        source_id: str,
        state_match: StateMatch | None,
    ) -> ExplorationContext:
        graph_before_action = self.manager.to_graph(start_node_id=self._start_node_id)
        return build_exploration_context(
            graph_before_action,
            current_node_id=source_id,
            state_match=state_match,
        )

    def _match_current_state(
        self,
        *,
        before: StateSnapshot,
        before_interactables: list[dict[str, Any]],
    ) -> StateMatch | None:
        if (
            not self.enable_exploration_memory
            or self.state_embedding_provider is None
            or not self.state_embedding_records
        ):
            return None
        current_summary = build_state_summary(
            snapshot=before,
            interactables=before_interactables,
            active_planning_facts=[],
        )
        return find_best_state_match(
            current_summary,
            self.state_embedding_records,
            embedding_provider=self.state_embedding_provider,
            same_threshold=CURRENT_NODE_MATCH_THRESHOLD,
        )

    def _resolve_current_source_id(
        self,
        *,
        default_source_id: str,
        source_match: StateMatch | None,
    ) -> tuple[str, StateMatch | None]:
        has_active_current_pointer = (
            self._current_node_id is not None
            and default_source_id == self._current_node_id
        )
        if has_active_current_pointer:
            return default_source_id, None
        if source_match is None:
            return default_source_id, None
        if source_match.status == "same" and source_match.node_id is not None:
            try:
                self.manager.node_for_id(source_match.node_id)
            except KeyError:
                return default_source_id, None
            if not self._can_relocate_source(
                default_source_id=default_source_id,
                matched_source_id=source_match.node_id,
            ):
                return default_source_id, None
            return source_match.node_id, source_match
        return default_source_id, None

    def _current_source_id(self, *, default_source_id: str) -> str:
        if self._current_node_id is None:
            return default_source_id
        try:
            self.manager.node_for_id(self._current_node_id)
        except KeyError:
            self._current_node_id = None
            return default_source_id
        return self._current_node_id

    def _can_relocate_source(
        self,
        *,
        default_source_id: str,
        matched_source_id: str,
    ) -> bool:
        if default_source_id == matched_source_id:
            return True
        self.manager.node_for_id(default_source_id)
        self.manager.node_for_id(matched_source_id)
        return self._has_known_revisit_evidence(
            default_node_id=default_source_id,
            matched_node_id=matched_source_id,
        )

    def _refresh_matched_source_node(
        self,
        *,
        source_id: str,
        before_draft,
    ) -> None:
        existing = self.manager.node_for_id(source_id)
        self.manager.identify_or_add_node(
            replace(
                existing,
                page_frame=before_draft.page_frame,
                state_schema=before_draft.state_schema,
                last_state_snapshot=before_draft.last_state_snapshot,
                interactable_elements=before_draft.interactable_elements,
                reference_observation=ReferenceObservation(
                    url=before_draft.page_frame.url,
                    title=before_draft.page_frame.title,
                ),
                evidence=before_draft.evidence,
            )
        )

    def _record_state_embedding(
        self,
        *,
        node_id: str,
        after: StateSnapshot,
        after_interactables: list[dict[str, Any]],
        active_planning_facts: list[str],
    ) -> None:
        if not self.enable_exploration_memory or self.state_embedding_provider is None:
            return
        target_summary = build_state_summary(
            snapshot=after,
            interactables=after_interactables,
            active_planning_facts=active_planning_facts,
        )
        target_embedding = self.state_embedding_provider(target_summary.text)
        self.state_embedding_records = [
            record
            for record in self.state_embedding_records
            if record.node_id != node_id
        ]
        self.state_embedding_records.append(
            StateEmbeddingRecord(
                node_id=node_id,
                summary_text=target_summary.text,
                embedding=list(target_embedding),
                planning_facts=target_summary.planning_facts,
                context_markers=target_summary.context_markers,
            )
        )

    def _ensure_source_embedding(
        self,
        *,
        node_id: str,
        before: StateSnapshot,
        before_interactables: list[dict[str, Any]],
    ) -> None:
        if (
            not self.enable_exploration_memory
            or self.state_embedding_provider is None
            or any(record.node_id == node_id for record in self.state_embedding_records)
        ):
            return
        source_node = self.manager.node_for_id(node_id)
        self._record_state_embedding(
            node_id=node_id,
            after=before,
            after_interactables=before_interactables,
            active_planning_facts=(
                list(source_node.planning_state.active_facts)
                if source_node.planning_state is not None
                else []
            ),
        )

    def _select_action(
        self,
        *,
        exploration_context: ExplorationContext,
        current_interactables: list[dict[str, Any]] | None = None,
    ) -> BrowserAction | None:
        return self._select_business_affordance_action(
            exploration_context=exploration_context,
            current_interactables=current_interactables,
        )

    def _select_business_affordance_action(
        self,
        *,
        exploration_context: ExplorationContext,
        current_interactables: list[dict[str, Any]] | None = None,
    ) -> BrowserAction | None:
        node = self.manager.node_for_id(exploration_context.current_node_id)

        location_id, unresolved = _semantic_location_anchor(node)
        memory_candidate = None
        if location_id and not unresolved:
            pool = self.location_exploration_coordinator.memory.pool_for(location_id)
            if pool.candidates:
                memory_candidate, _preflight = (
                    self.location_exploration_coordinator.select_candidate(
                        location_id,
                        current_interactables=current_interactables,
                        active_business_facts=self._active_business_facts(node),
                    )
                )
                self.location_exploration_coordinator.sync_graph_meta(self.manager)
                if memory_candidate is None:
                    return None
                candidate_by_id = {
                    normalize_semantic_id(item.action_name): item
                    for item in node.business_affordances
                }
                affordance = candidate_by_id.get(
                    normalize_semantic_id(memory_candidate.action_name),
                    memory_candidate,
                )
                preferred = self._preferred_resume_action_key
                if preferred is not None and preferred == ActionAttemptKey(
                    exploration_context.current_node_id,
                    affordance.action_name,
                ):
                    self._preferred_resume_action_key = None
                    return _business_action_from_affordance(affordance)
                return _business_action_from_affordance(affordance)

        if not node.business_affordances:
            return None

        ranked = sorted(
            node.business_affordances,
            key=_affordance_rank,
            reverse=True,
        )
        for affordance in ranked:
            action_id = affordance.action_name
            preferred = self._preferred_resume_action_key
            if preferred is not None and preferred == ActionAttemptKey(
                exploration_context.current_node_id, action_id
            ):
                self._preferred_resume_action_key = None
                return _business_action_from_affordance(affordance)
            if self.resume_policy is not None and not is_action_eligible(
                self.manager.to_graph(start_node_id=self._start_node_id),
                source_node_id=exploration_context.current_node_id,
                action_id=action_id,
                policy=self.resume_policy,
            ):
                continue
            if semantically_matches_action(
                action_id,
                exploration_context.avoid_action_ids,
                embedding_provider=self.action_embedding_provider,
            ):
                continue
            if semantically_matches_action(
                affordance.action_name,
                exploration_context.tried_action_ids,
                embedding_provider=self.action_embedding_provider,
            ):
                continue
            return _business_action_from_affordance(affordance)
        return None

    def _active_business_facts(self, node: WebKobeNode) -> set[str]:
        if node.planning_state is None:
            return set()
        active = {
            normalize_semantic_id(fact)
            for fact in node.planning_state.active_facts
            if normalize_semantic_id(fact)
        }
        return active
