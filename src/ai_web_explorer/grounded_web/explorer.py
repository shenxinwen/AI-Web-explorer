from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Callable

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionRequest,
    LlmActionSelectionResult,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager
from ai_web_explorer.grounded_web.business_profile import BusinessFlowProfile
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
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


def _browser_action_from_interactable(item: dict[str, Any]) -> BrowserAction:
    return BrowserAction(
        action_kind=str(item.get("action_kind") or "click"),
        locator=item.get("locator"),
        semantic_id=str(item.get("semantic_id") or "unknown_action"),
        input_values=dict(item.get("input_values") or {}),
        description=item.get("description"),
        action_label=item.get("action_label"),
        canonical_action_name=item.get("canonical_action_name"),
        naming_provenance=item.get("naming_provenance"),
    )


def _first_unexplored_action(
    interactables: list[dict[str, Any]],
) -> BrowserAction | None:
    for item in interactables:
        if not item.get("explored"):
            return _browser_action_from_interactable(item)
    return None


def _business_action_from_affordance(affordance: BusinessAffordance) -> BrowserAction:
    details = [f"Business action: {affordance.action_name}."]
    if affordance.target_hint:
        details.append(f"Target hint: {affordance.target_hint}.")
    if affordance.evidence:
        details.append(f"Evidence: {affordance.evidence}.")
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


def _is_ignorable_stagehand_tool_choice_error(error: str | None) -> bool:
    return bool(error and "Thinking mode does not support this tool_choice" in error)


class WebKobeExplorer:
    def __init__(
        self,
        *,
        adapter: AutomationBackend,
        semantic_assistor: SemanticAssistor,
        goal: str = "Explore the web task.",
        action_selector: (
            Callable[[LlmActionSelectionRequest], LlmActionSelectionResult] | None
        ) = None,
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
        self.action_selector = action_selector
        self.business_profile = business_profile
        self.capture_screenshots = capture_screenshots
        self.visual_delta_provider = visual_delta_provider
        self.semantic_naming_provider = semantic_naming_provider
        self.state_embedding_provider = state_embedding_provider
        self.state_embedding_records = list(state_embedding_records or [])
        self.enable_exploration_memory = enable_exploration_memory
        self.selection_traces: list[dict] = []
        self.manager = WebKobeGraphManager(app=adapter.app_name)
        self._start_node_id: str | None = None

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
        before_screenshot_path = await self._capture_screenshot("before")
        if before_screenshot_path is not None:
            self._record_source_business_affordances(
                source_id=source_id,
                before=before,
                before_screenshot_path=before_screenshot_path,
            )
        source_interactables = self.manager.interactables_for_node(source_id)
        exploration_context = self._exploration_context_for_source(
            before=before,
            source_id=source_id,
            source_interactables=source_interactables,
        )
        set_context = getattr(self.adapter, "set_exploration_context", None)
        if set_context is not None:
            set_context(exploration_context.to_prompt_block())

        selected = self._select_action(
            before,
            source_interactables,
            exploration_context=exploration_context,
        )
        if selected is None:
            await self._try_backtrack()
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
        )
        target_id = self.manager.identify_or_add_node(target_node)
        if edge_status == "no_observed_change" and should_materialize_business_state(
            business_transition
        ):
            edge_status = "succeeded_with_observed_change"
        if source_id != target_id and edge_status in {
            "no_observed_change",
            "failed_execution",
        }:
            edge_status = "succeeded_with_navigation"
        if (
            edge_status == "failed_execution"
            and _is_ignorable_stagehand_tool_choice_error(execution_error)
            and _planning_delta_has_fact_change(planning_delta)
        ):
            edge_status = "succeeded_with_observed_change"
        self._record_target_embedding(
            target_id=target_id,
            after=after,
            after_interactables=after_interactables,
            visual_summary=execution_metadata.get("visual_change_summary"),
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
        self.manager.mark_interactable_explored(
            source_id,
            selected.semantic_id,
            locator=selected.locator,
        )
        return self.manager.to_graph(start_node_id=self._start_node_id)

    async def _try_backtrack(self) -> bool:
        go_back = getattr(self.adapter, "go_back", None)
        if go_back is None:
            return False
        return await go_back()

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
        if not execution_success:
            return "failed_execution"
        return "no_observed_change"

    def _exploration_context_for_source(
        self,
        *,
        before: StateSnapshot,
        source_id: str,
        source_interactables: list[dict[str, Any]],
    ) -> ExplorationContext:
        graph_before_action = self.manager.to_graph(start_node_id=self._start_node_id)
        nodes_by_id = {node.node_id: node for node in graph_before_action.nodes}
        source_node = nodes_by_id.get(source_id)
        active_facts = (
            list(source_node.planning_state.active_facts)
            if source_node is not None and source_node.planning_state is not None
            else []
        )
        source_summary = build_state_summary(
            snapshot=before,
            interactables=source_interactables,
            active_planning_facts=active_facts,
        )
        state_match = None
        if self.enable_exploration_memory and self.state_embedding_provider is not None:
            state_match = find_best_state_match(
                source_summary,
                self.state_embedding_records,
                embedding_provider=self.state_embedding_provider,
            )
        return build_exploration_context(
            graph_before_action,
            current_node_id=source_id,
            state_match=state_match,
        )

    def _record_target_embedding(
        self,
        *,
        target_id: str,
        after: StateSnapshot,
        after_interactables: list[dict[str, Any]],
        visual_summary: str | None,
    ) -> None:
        if not self.enable_exploration_memory or self.state_embedding_provider is None:
            return
        target_summary = build_state_summary(
            snapshot=after,
            interactables=after_interactables,
            active_planning_facts=[],
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
        state,
        interactables: list[dict],
        *,
        exploration_context: ExplorationContext,
    ) -> BrowserAction | None:
        selected_business_action = self._select_business_affordance_action(
            exploration_context=exploration_context,
        )
        if selected_business_action is not None:
            return selected_business_action

        if self.action_selector is None:
            return _first_unexplored_action(interactables)

        candidate_actions = [
            _browser_action_from_interactable(item)
            for item in interactables
            if not item.get("explored")
        ]
        if not candidate_actions:
            return None

        result = self.action_selector(
            LlmActionSelectionRequest(
                goal=self.goal,
                state=state,
                candidate_actions=candidate_actions,
                exploration_context={
                    "prompt_block": exploration_context.to_prompt_block(),
                    "avoid_action_ids": list(exploration_context.avoid_action_ids),
                    "tried_action_ids": list(exploration_context.tried_action_ids),
                },
            )
        )
        self.selection_traces.append(result.trace.to_dict())
        candidate_ids = {action.semantic_id for action in candidate_actions}
        if (
            result.selected_action is not None
            and result.selected_action.semantic_id in candidate_ids
        ):
            return result.selected_action
        return _first_unexplored_action(interactables)

    def _select_business_affordance_action(
        self,
        *,
        exploration_context: ExplorationContext,
    ) -> BrowserAction | None:
        node = self.manager.node_for_id(exploration_context.current_node_id)
        if not node.business_affordances:
            return None

        completed_actions = self._completed_business_action_names()
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
            if affordance.action_name in completed_actions:
                continue
            if affordance.action_name in local_tried:
                continue
            return _business_action_from_affordance(affordance)

        for affordance in ranked:
            if affordance.action_name not in local_avoid:
                return _business_action_from_affordance(affordance)
        return None

    def _completed_business_action_names(self) -> set[str]:
        completed: set[str] = set()
        for edge in self.manager.to_graph(start_node_id=self._start_node_id).edges:
            action_name = (
                edge.business_transition.action_name
                if edge.business_transition is not None
                else None
            )
            action_name = (
                action_name
                or edge.action.canonical_action_name
                or edge.action.semantic_id
            )
            if edge.status in {
                "verified",
                "succeeded",
                "succeeded_with_observed_change",
                "succeeded_with_navigation",
            }:
                completed.add(action_name)
        return completed
