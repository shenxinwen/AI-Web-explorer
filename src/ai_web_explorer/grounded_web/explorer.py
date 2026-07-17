from __future__ import annotations

import asyncio
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
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
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
    )


def _browser_action_from_interactable(item: dict[str, Any]) -> BrowserAction:
    return BrowserAction(
        action_kind=str(item.get("action_kind") or "click"),
        locator=item.get("locator"),
        semantic_id=str(item.get("semantic_id") or "unknown_action"),
        input_values=dict(item.get("input_values") or {}),
        description=item.get("description"),
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
    ):
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.goal = goal
        self.action_selector = action_selector
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

        execution_success = await self.adapter.execute(selected)
        execution_error = getattr(self.adapter, "last_execution_error", None)
        after = await self._observe_after_action(
            before=before,
            before_facts=before_facts,
            execution_success=execution_success,
        )
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
        if (
            execution_success
            and source_id != target_id
            and edge_status == "no_observed_change"
        ):
            edge_status = "succeeded_with_navigation"
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
                success=execution_success,
                error=execution_error,
                metadata=dict(
                    getattr(self.adapter, "last_execution_metadata", {}) or {}
                ),
            ),
            status=edge_status,
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(
            source_id,
            selected.semantic_id,
            locator=selected.locator,
        )
        return self.manager.to_graph(start_node_id=self._start_node_id)

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
        if not execution_success:
            return "failed_execution"
        if observed_delta:
            return "succeeded_with_observed_change"
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
