from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from typing import Any

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.grounded_web.state_signature import schema_delta, slug_identifier
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
from ai_web_explorer.grounded_web.business_state_policy import (
    resolve_business_target_node,
    should_materialize_business_state,
)
from ai_web_explorer.grounded_web.exploration_index import (
    ExplorationContext,
    build_exploration_context,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.planning_fact_verifier import verify_planning_delta
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor
from ai_web_explorer.grounded_web.semantic_naming import (
    SemanticNamingProvider,
    SemanticNamingRequest,
    apply_semantic_naming,
    apply_transition_naming,
)
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


def _merged_unique(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    for items in lists:
        for item in items:
            if item not in merged:
                merged.append(item)
    return merged


def _merge_planning_deltas(
    structured: PlanningDelta | None,
    visual: PlanningDelta | None,
) -> PlanningDelta | None:
    if structured is None:
        return visual
    if visual is None:
        return structured
    return PlanningDelta(
        candidate_added_facts=_merged_unique(
            visual.candidate_added_facts,
            structured.candidate_added_facts,
        ),
        candidate_removed_facts=_merged_unique(
            visual.candidate_removed_facts,
            structured.candidate_removed_facts,
        ),
        verified_added_facts=list(structured.verified_added_facts),
        verified_removed_facts=list(structured.verified_removed_facts),
        profile_fact_ids=_merged_unique(
            visual.profile_fact_ids,
            structured.profile_fact_ids,
        ),
        generated_fact_ids=_merged_unique(
            visual.generated_fact_ids,
            structured.generated_fact_ids,
        ),
        evidence=list(visual.evidence) + list(structured.evidence),
        confidence=structured.confidence or visual.confidence,
        uncertainty_reason=visual.uncertainty_reason,
    )


def _planning_delta_has_fact_change(delta: PlanningDelta | None) -> bool:
    if delta is None:
        return False
    return bool(
        delta.candidate_added_facts
        or delta.candidate_removed_facts
        or delta.verified_added_facts
        or delta.verified_removed_facts
    )


def _state_label_hints_from_profile(
    profile: BusinessFlowProfile | None,
) -> dict[str, str]:
    if profile is None:
        return {}
    return {
        fact.fact_id: fact.state_label_hint
        for fact in profile.planning_facts
        if fact.state_label_hint
    }


def _is_ignorable_stagehand_tool_choice_error(error: str | None) -> bool:
    return bool(error and "Thinking mode does not support this tool_choice" in error)


def _planning_transition_has_fact_change(
    transition: PlanningTransition | None,
) -> bool:
    if transition is None:
        return False
    return set(transition.pre_facts) != set(transition.post_facts)


def _should_advance_current_node(
    *,
    source_id: str,
    target_id: str,
    edge_status: str,
    business_transition: BusinessTransition | None,
    planning_transition: PlanningTransition | None,
) -> bool:
    if source_id == target_id:
        return False
    if edge_status not in {
        "succeeded_with_navigation",
        "succeeded_with_observed_change",
    }:
        return False
    if (
        edge_status == "succeeded_with_observed_change"
        and business_transition is None
        and planning_transition is None
    ):
        return True
    return (
        should_materialize_business_state(business_transition)
        or _planning_transition_has_fact_change(planning_transition)
        or edge_status == "succeeded_with_navigation"
    )


def _facts_compatible(
    existing_facts: list[str] | None,
    post_facts: list[str],
) -> bool:
    if existing_facts is None:
        return not post_facts
    return set(existing_facts) == set(post_facts)


def _state_variant_node_id(
    *,
    node: WebKobeNode,
    post_facts: list[str],
    state_label_hints: dict[str, str],
) -> tuple[str, str]:
    label = _state_variant_label(
        node=node,
        post_facts=post_facts,
        state_label_hints=state_label_hints,
    )
    payload = {
        "base_node_id": node.node_id,
        "post_facts": sorted(post_facts),
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    return f"{label}__state_{digest}", label


def _state_variant_label(
    *,
    node: WebKobeNode,
    post_facts: list[str],
    state_label_hints: dict[str, str],
) -> str:
    for fact in post_facts:
        hint = state_label_hints.get(fact)
        if hint:
            return slug_identifier(hint, fallback="state")
    return slug_identifier(
        node.node_label or node.page_frame.page_type or node.node_id,
        fallback="state",
    )


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
        semantic_naming_provider: SemanticNamingProvider | None = None,
        state_embedding_provider: EmbeddingProvider | None = None,
        state_embedding_records: list[StateEmbeddingRecord] | None = None,
        enable_exploration_memory: bool = False,
    ):
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.goal = goal
        self.business_profile = business_profile
        self.capture_screenshots = capture_screenshots
        self.visual_delta_provider = visual_delta_provider
        self.semantic_naming_provider = semantic_naming_provider
        self.state_embedding_provider = state_embedding_provider
        self.state_embedding_records = list(state_embedding_records or [])
        self.enable_exploration_memory = enable_exploration_memory
        self.manager = WebKobeGraphManager(app=adapter.app_name)
        self._start_node_id: str | None = None
        self._current_node_id: str | None = None
        self._visit_stack: list[str] = []

    async def explore_one_step(self) -> WebKobeGraph:
        before = await self.adapter.observe_state()
        before_facts = getattr(self.adapter, "last_state_facts", None)
        before_interactables = await self.adapter.list_interactables(before)
        before_draft = self.semantic_assistor.describe_state(
            snapshot=before,
            interactables=before_interactables,
        )
        source_id = self.manager.identify_or_add_node(_node_from_draft(before_draft))
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
            did_backtrack = await self._try_backtrack()
            if not did_backtrack:
                self.manager.meta["last_step_kind"] = "no_available_action"
                self.manager.meta["last_step_status"] = "unproductive"
            return self.manager.to_graph(start_node_id=self._start_node_id)

        if (
            self.semantic_naming_provider is not None
            and selected.action_kind != "business_intent"
        ):
            node_fields, selected = apply_semantic_naming(
                SemanticNamingRequest(
                    goal=self.goal,
                    state=before,
                    action=selected,
                ),
                provider=self.semantic_naming_provider,
            )
            source_node = _node_from_draft(before_draft)
            self.manager.identify_or_add_node(replace(source_node, **node_fields))

        execution_success = await self.adapter.execute(selected)
        execution_error = getattr(self.adapter, "last_execution_error", None)
        after = await self._observe_after_action(
            before=before,
            before_facts=before_facts,
            execution_success=execution_success,
        )
        after_screenshot_path = await self._capture_screenshot("after")
        after_interactables = await self.adapter.list_interactables(after)
        after_draft = self.semantic_assistor.describe_state(
            snapshot=after,
            interactables=after_interactables,
        )

        delta = schema_delta(
            before_draft.last_state_snapshot,
            after_draft.last_state_snapshot,
        )
        observed_delta = _observed_delta_from_facts_or_signature(
            before_facts=before_facts,
            after_facts=getattr(self.adapter, "last_state_facts", None),
            before_signature=before.signature,
            after_signature=after.signature,
            url=after.url,
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
        visual_planning_delta = None
        business_transition = None
        if (
            self.business_profile is not None
            and self.visual_delta_provider is not None
            and before_screenshot_path is not None
            and after_screenshot_path is not None
        ):
            visual_result = summarize_visual_delta(
                VisualDeltaRequest(
                    goal=self.goal,
                    action=selected,
                    profile=self.business_profile,
                    before_screenshot_path=before_screenshot_path,
                    after_screenshot_path=after_screenshot_path,
                    before_signature=before.signature,
                    after_signature=after.signature,
                ),
                provider=self.visual_delta_provider,
            )
            visual_planning_delta = visual_result.planning_delta
            business_transition = visual_result.business_transition
            execution_metadata["visual_delta_trace"] = visual_result.trace.to_dict()
            if visual_result.trace.visual_change_summary:
                execution_metadata["visual_change_summary"] = (
                    visual_result.trace.visual_change_summary
                )
                if self.semantic_naming_provider is not None:
                    selected = apply_transition_naming(
                        action=selected,
                        goal=self.goal,
                        visual_change_summary=(
                            visual_result.trace.visual_change_summary
                        ),
                        provider=self.semantic_naming_provider,
                    )
        planning_delta = _merge_planning_deltas(
            structured_planning_delta,
            visual_planning_delta,
        )
        planning_transition = None
        if self.business_profile is not None:
            planning_transition = self.manager.build_planning_transition(
                source_id,
                planning_delta=planning_delta,
                profile=self.business_profile,
            )
        target_node = resolve_business_target_node(
            source_node=self.manager.node_for_id(source_id),
            candidate_node=_node_from_draft(after_draft),
            business_transition=business_transition,
            planning_transition=planning_transition,
            state_label_hints=_state_label_hints_from_profile(self.business_profile),
        )
        target_node = self._avoid_incompatible_existing_target_state(
            target_node=target_node,
            planning_transition=planning_transition,
        )
        target_node, target_match = self._match_existing_target_node(
            target_node=target_node,
            after=after,
            after_interactables=after_interactables,
            planning_transition=planning_transition,
            visual_summary=execution_metadata.get("visual_change_summary"),
        )
        if target_match is not None:
            execution_metadata["target_state_match"] = {
                "status": target_match.status,
                "node_id": target_match.node_id,
                "score": target_match.score,
                "blocked_reason": target_match.blocked_reason,
                "accepted": target_node.node_id == target_match.node_id,
            }
        target_id = self.manager.identify_or_add_node(target_node)
        if edge_status == "no_observed_change" and should_materialize_business_state(
            business_transition
        ):
            edge_status = "succeeded_with_observed_change"
        if (
            edge_status in {"failed_execution", "no_observed_change"}
            and _is_ignorable_stagehand_tool_choice_error(execution_error)
            and _planning_delta_has_fact_change(planning_delta)
        ):
            edge_status = "succeeded_with_observed_change"
        if source_id != target_id and edge_status in {
            "no_observed_change",
            "failed_execution",
        }:
            edge_status = "succeeded_with_navigation"
        self._record_target_embedding(
            target_id=target_id,
            after=after,
            after_interactables=after_interactables,
            visual_summary=execution_metadata.get("visual_change_summary"),
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
            business_transition=business_transition,
            status=edge_status,
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        if self.business_profile is not None:
            self.manager.apply_planning_transition(edge)
        self.manager.add_edge(edge)
        self.manager.meta["last_step_kind"] = "business_edge"
        self.manager.meta["last_step_status"] = (
            "productive"
            if edge_status
            in {
                "verified",
                "succeeded",
                "succeeded_with_observed_change",
                "succeeded_with_navigation",
            }
            else "unproductive"
        )
        if _should_advance_current_node(
            source_id=source_id,
            target_id=target_id,
            edge_status=edge_status,
            business_transition=business_transition,
            planning_transition=planning_transition,
        ):
            self._set_current_node(target_id)
        elif self._current_node_id is None:
            self._set_current_node(source_id)
        return self.manager.to_graph(start_node_id=self._start_node_id)

    def _avoid_incompatible_existing_target_state(
        self,
        *,
        target_node: WebKobeNode,
        planning_transition: PlanningTransition | None,
    ) -> WebKobeNode:
        if planning_transition is None:
            return target_node
        try:
            existing = self.manager.node_for_id(target_node.node_id)
        except KeyError:
            return target_node
        existing_facts = (
            list(existing.planning_state.active_facts)
            if existing.planning_state is not None
            else None
        )
        post_facts = list(planning_transition.post_facts)
        if _facts_compatible(existing_facts, post_facts):
            return target_node
        node_id, label = _state_variant_node_id(
            node=target_node,
            post_facts=post_facts,
            state_label_hints=_state_label_hints_from_profile(self.business_profile),
        )
        return replace(target_node, node_id=node_id, node_label=label)

    def _match_existing_target_node(
        self,
        *,
        target_node: WebKobeNode,
        after: StateSnapshot,
        after_interactables: list[dict[str, Any]],
        planning_transition: PlanningTransition | None,
        visual_summary: str | None,
    ) -> tuple[WebKobeNode, StateMatch | None]:
        if (
            not self.enable_exploration_memory
            or self.state_embedding_provider is None
            or not self.state_embedding_records
            or planning_transition is None
        ):
            return target_node, None
        target_summary = build_state_summary(
            snapshot=after,
            interactables=after_interactables,
            active_planning_facts=planning_transition.post_facts,
            visual_summary=visual_summary,
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
        existing_facts = (
            list(existing.planning_state.active_facts)
            if existing.planning_state is not None
            else None
        )
        if not _facts_compatible(existing_facts, list(planning_transition.post_facts)):
            return target_node, replace(
                target_match,
                status="blocked",
                blocked_reason="planning_fact_conflict",
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

    async def _try_backtrack(self) -> bool:
        go_back = getattr(self.adapter, "go_back", None)
        if go_back is None:
            return False
        did_go_back = await go_back()
        if did_go_back and len(self._visit_stack) > 1:
            self.manager.meta["backtrack_count"] = (
                int(self.manager.meta.get("backtrack_count", 0)) + 1
            )
            self._visit_stack.pop()
            self._current_node_id = self._visit_stack[-1]
            self.manager.meta["last_step_kind"] = "control_backtrack"
            self.manager.meta["last_step_status"] = "productive"
        elif did_go_back:
            self.manager.meta["last_step_kind"] = "control_backtrack"
            self.manager.meta["last_step_status"] = "unproductive"
        return did_go_back

    def _set_current_node(self, node_id: str) -> None:
        self._current_node_id = node_id
        self._record_visit_node(node_id)

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
        if self.business_profile is None or self.visual_delta_provider is None:
            return
        source_node = self.manager.node_for_id(source_id)
        if source_node.business_affordances:
            return
        active_facts = (
            list(source_node.planning_state.active_facts)
            if source_node.planning_state is not None
            else []
        )
        result = summarize_visual_affordances(
            VisualAffordanceRequest(
                goal=self.goal,
                profile=self.business_profile,
                current_screenshot_path=before_screenshot_path,
                current_signature=before.signature,
                current_planning_facts=active_facts,
            ),
            provider=self.visual_delta_provider,
        )
        if result.trace.status != "summarized":
            return
        self.manager.identify_or_add_node(
            replace(
                source_node,
                business_affordances=result.business_affordances,
                state_summary=result.state_summary or source_node.state_summary,
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
        default_node = self.manager.node_for_id(default_source_id)
        matched_node = self.manager.node_for_id(matched_source_id)
        default_facts = (
            list(default_node.planning_state.active_facts)
            if default_node.planning_state is not None
            else None
        )
        matched_facts = (
            list(matched_node.planning_state.active_facts)
            if matched_node.planning_state is not None
            else None
        )
        return _facts_compatible(default_facts, matched_facts or [])

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

    def _record_target_embedding(
        self,
        *,
        target_id: str,
        after: StateSnapshot,
        after_interactables: list[dict[str, Any]],
        visual_summary: str | None,
        active_planning_facts: list[str],
    ) -> None:
        if not self.enable_exploration_memory or self.state_embedding_provider is None:
            return
        target_summary = build_state_summary(
            snapshot=after,
            interactables=after_interactables,
            active_planning_facts=active_planning_facts,
            visual_summary=visual_summary,
        )
        target_embedding = self.state_embedding_provider(target_summary.text)
        self.state_embedding_records = [
            record
            for record in self.state_embedding_records
            if record.node_id != target_id
        ]
        self.state_embedding_records.append(
            StateEmbeddingRecord(
                node_id=target_id,
                summary_text=target_summary.text,
                embedding=list(target_embedding),
                planning_facts=target_summary.planning_facts,
                context_markers=target_summary.context_markers,
            )
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

        local_tried = set(exploration_context.tried_action_ids)
        local_avoid = set(exploration_context.avoid_action_ids)
        ranked = sorted(
            node.business_affordances,
            key=_affordance_rank,
            reverse=True,
        )
        for affordance in ranked:
            if affordance.action_name in local_avoid:
                continue
            if affordance.action_name in local_tried:
                continue
            return _business_action_from_affordance(affordance)
        return None
