from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from typing import Any
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
from ai_web_explorer.grounded_web.business_profile import PlanningDelta, PlanningTransition
from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.exploration_index import (
    ExplorationContext,
    build_exploration_context,
    semantically_matches_action,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.planning_fact_verifier import verify_planning_delta
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor
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


OBSERVATION_WAIT_TIMEOUT_MS = 1200
OBSERVATION_WAIT_INTERVAL_MS = 200
CURRENT_NODE_MATCH_THRESHOLD = 0.88
TARGET_NODE_MATCH_THRESHOLD = 0.90


def _url_path(url: str) -> str:
    return urlsplit(url).path or "/"


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
    details = [
        "Execute only this selected business action: "
        f"{affordance.action_name}.",
        "Stop after the first visible completion or clear failure.",
        "Do not continue to the next business goal.",
    ]
    if affordance.target_hint:
        details.append(f"Target hint: {affordance.target_hint}.")
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
        state_embedding_provider: EmbeddingProvider | None = None,
        action_embedding_provider: EmbeddingProvider | None = None,
        state_embedding_records: list[StateEmbeddingRecord] | None = None,
        enable_exploration_memory: bool = False,
        max_candidates: int = 5,
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
        self.state_embedding_provider = state_embedding_provider
        self.action_embedding_provider = action_embedding_provider
        self.state_embedding_records = list(state_embedding_records or [])
        self.enable_exploration_memory = enable_exploration_memory
        self.manager = WebKobeGraphManager(app=adapter.app_name)
        self._start_node_id: str | None = None
        self._current_node_id: str | None = None
        self._visit_stack: list[str] = []
        self._visual_affordance_observed_node_ids: set[str] = set()

    @property
    def start_node_id(self) -> str | None:
        return self._start_node_id

    def restore_graph(self, graph: WebKobeGraph) -> None:
        if graph.app != self.adapter.app_name:
            raise ValueError("resume_app_mismatch")
        self.manager = WebKobeGraphManager.from_graph(graph)
        self._start_node_id = graph.start_node_id
        self._current_node_id = None
        self._visit_stack = []
        self._visual_affordance_observed_node_ids = {
            node.node_id for node in graph.nodes if node.business_affordances
        }

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
        exploration_context = self._exploration_context_for_source(
            source_id=source_id,
            state_match=accepted_source_match,
        )
        set_context = getattr(self.adapter, "set_exploration_context", None)
        if set_context is not None:
            set_context(exploration_context.to_prompt_block())

        selected = self._select_action(
            exploration_context=exploration_context,
        )
        if selected is None:
            self.manager.meta["last_step_kind"] = "current_state_exhausted"
            self.manager.meta["last_step_status"] = "unproductive"
            self.manager.meta["last_step_graph_changed"] = False
            return self.manager.to_graph(start_node_id=self._start_node_id)

        execution_success = await self.adapter.execute(selected)
        execution_error = getattr(self.adapter, "last_execution_error", None)
        observation_allowed = execution_success or _is_ignorable_stagehand_tool_choice_error(
            execution_error
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
        visual_change_kind = "unknown"
        if (
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
                ),
                provider=self.visual_delta_provider,
            )
            visual_delta_facts = (
                list(visual_result.planning_delta.candidate_added_facts),
                list(visual_result.planning_delta.candidate_removed_facts),
            )
            visual_change_kind = visual_result.visual_change_kind
            visual_trace = visual_result.trace.to_dict()
            visual_trace["candidate_added_facts"] = list(visual_delta_facts[0])
            visual_trace["candidate_removed_facts"] = list(visual_delta_facts[1])
            execution_metadata["visual_delta_trace"] = visual_trace

        planning_delta = structured_planning_delta
        planning_transition = None
        if self.business_profile is not None:
            planning_transition = self.manager.build_planning_transition(
                source_id,
                planning_delta=planning_delta,
                profile=self.business_profile,
            )
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
        )

        target_node = _node_from_draft(after_draft)
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
        known_node_ids = {
            node.node_id for node in self.manager.to_graph().nodes
        }
        target_id = self.manager.identify_or_add_node(target_node)
        node_was_new = target_id not in known_node_ids
        if edge_status == "no_observed_change" and (
            visual_fact_change or visual_kind_change
        ):
            edge_status = "succeeded_with_observed_change"
        if source_id != target_id and edge_status in {
            "no_observed_change",
            "failed_execution",
        }:
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
        graph_changed = node_was_new or edge_was_new
        self.manager.meta["last_step_kind"] = "business_edge"
        self.manager.meta["last_step_graph_changed"] = graph_changed
        self.manager.meta["last_step_status"] = (
            "productive" if graph_changed else "unproductive"
        )
        if _should_advance_current_node(
            source_id=source_id,
            target_id=target_id,
            edge_status=edge_status,
        ):
            self._set_current_node(target_id)
        elif self._current_node_id is None:
            self._set_current_node(source_id)
        return self.manager.to_graph(start_node_id=self._start_node_id)

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

    async def execute_replay_action(self, action: BrowserAction) -> bool:
        """Execute one stored action without recording a new exploration edge."""
        replay_execute = getattr(self.adapter, "execute_replay_action", None)
        if replay_execute is not None:
            return await replay_execute(action)
        return await self.adapter.execute(action)

    def mark_replay_edge_validation(self, edge_id: str, status: str) -> None:
        self.manager.update_edge_replay_validation(edge_id, status)

    async def validate_current_node(self, expected_node_id: str) -> bool:
        """Check the observed surface against an existing graph node."""
        try:
            expected = self.manager.node_for_id(expected_node_id)
        except KeyError:
            return False
        snapshot = await self.adapter.observe_state()
        interactables = await self.adapter.list_interactables(snapshot)
        draft = self.semantic_assistor.describe_state(
            snapshot=snapshot,
            interactables=interactables,
        )
        if draft.node_id != expected_node_id:
            if draft.last_state_snapshot != expected.last_state_snapshot:
                return False
            if _url_path(snapshot.url) != _url_path(expected.page_frame.url):
                return False
            expected_actions = {
                item.get("semantic_id")
                or item.get("canonical_action_name")
                for item in expected.interactable_elements
                if item.get("semantic_id") or item.get("canonical_action_name")
            }
            actual_actions = {
                item.get("semantic_id")
                or item.get("canonical_action_name")
                for item in interactables
                if item.get("semantic_id") or item.get("canonical_action_name")
            }
            if expected_actions and expected_actions != actual_actions:
                return False
        self._set_current_node(expected_node_id)
        return True

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
        if (
            source_node.business_affordances
            or source_id in self._visual_affordance_observed_node_ids
        ):
            return
        result = summarize_visual_affordances(
            VisualAffordanceRequest(
                goal=self.goal,
                current_screenshot_path=before_screenshot_path,
                current_signature=before.signature,
                max_actions=self.max_candidates,
            ),
            provider=self.visual_delta_provider,
        )
        if result.trace.status != "summarized":
            return
        self._visual_affordance_observed_node_ids.add(source_id)
        fallback_label = (
            source_node.node_label
            or source_node.page_frame.page_type
            or source_node.node_id
        )
        accepted_vlm_label = bool(
            result.state_label
            and slug_identifier(result.state_label, fallback="")
        )
        self.manager.identify_or_add_node(
            replace(
                source_node,
                business_affordances=result.business_affordances,
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
    ) -> BrowserAction | None:
        return self._select_business_affordance_action(
            exploration_context=exploration_context,
        )

    def _select_business_affordance_action(
        self,
        *,
        exploration_context: ExplorationContext,
    ) -> BrowserAction | None:
        node = self.manager.node_for_id(exploration_context.current_node_id)
        if not node.business_affordances:
            return None

        ranked = sorted(
            node.business_affordances,
            key=_affordance_rank,
            reverse=True,
        )
        for affordance in ranked:
            if semantically_matches_action(
                affordance.action_name,
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
