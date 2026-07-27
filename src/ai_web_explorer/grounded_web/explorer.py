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
    ):
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.goal = goal
        self.action_selector = action_selector
        self.business_profile = business_profile
        self.capture_screenshots = capture_screenshots
        self.visual_delta_provider = visual_delta_provider
        self.semantic_naming_provider = semantic_naming_provider
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
        source_interactables = self.manager.interactables_for_node(source_id)

        selected = self._select_action(before, source_interactables)
        if selected is None:
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

        before_screenshot_path = await self._capture_screenshot("before")
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
        target_id = self.manager.identify_or_add_node(_node_from_draft(after_draft))

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
        if source_id != target_id and edge_status in {
            "no_observed_change",
            "failed_execution",
        }:
            edge_status = "succeeded_with_navigation"
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
        if (
            edge_status == "failed_execution"
            and _is_ignorable_stagehand_tool_choice_error(execution_error)
            and _planning_delta_has_fact_change(planning_delta)
        ):
            edge_status = "succeeded_with_observed_change"
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
            status=edge_status,
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        if self.business_profile is not None:
            edge = self.manager.propagate_planning_state(
                edge,
                profile=self.business_profile,
            )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(
            source_id,
            selected.semantic_id,
            locator=selected.locator,
        )
        return self.manager.to_graph(start_node_id=self._start_node_id)

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

    def _select_action(
        self,
        state,
        interactables: list[dict],
    ) -> BrowserAction | None:
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
