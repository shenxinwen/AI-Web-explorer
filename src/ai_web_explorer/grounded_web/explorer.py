from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.action_ranker import select_unexplored_action
from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor


def _observed_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    evidence = [Evidence(source="web_kobe_transition_diff", url=url)]
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


class WebKobeExplorer:
    def __init__(
        self,
        *,
        adapter: AutomationBackend,
        semantic_assistor: SemanticAssistor,
    ):
        self.adapter = adapter
        self.semantic_assistor = semantic_assistor
        self.manager = WebKobeGraphManager(app=adapter.app_name)

    async def explore_one_step(self) -> WebKobeGraph:
        before = await self.adapter.observe_state()
        before_interactables = await self.adapter.list_interactables(before)
        before_draft = self.semantic_assistor.describe_state(
            snapshot=before,
            interactables=before_interactables,
        )
        source_id = self.manager.identify_or_add_node(_node_from_draft(before_draft))
        source_interactables = self.manager.interactables_for_node(source_id)

        selected = select_unexplored_action(source_interactables)
        if selected is None:
            return self.manager.to_graph(start_node_id=source_id)

        success = await self.adapter.execute(selected)
        after = await self.adapter.observe_state()
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
        edge = WebKobeEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            instruction=selected.description or selected.semantic_id,
            action=selected,
            capability=None,
            target_observation=after_draft.page_description,
            observed_delta=_observed_delta(
                before_draft.last_state_snapshot,
                after_draft.last_state_snapshot,
                after.url,
            ),
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind=selected.action_kind,
                concrete_locator=selected.locator,
                concrete_target_sample=selected.semantic_id,
                input_values_used=dict(selected.input_values),
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=success,
                error=(
                    None
                    if success
                    else str(
                        getattr(
                            self.adapter,
                            "last_execution_error",
                            "adapter execution returned false",
                        )
                        or "adapter execution returned false"
                    )
                ),
            ),
            status="verified" if success else "failed_execution",
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(
            source_id,
            selected.semantic_id,
            locator=selected.locator,
        )
        return self.manager.to_graph(start_node_id=source_id)
