from __future__ import annotations

from ai_web_explorer.grounded_web.action_intent import ActionIntent
from ai_web_explorer.grounded_web.action_loop import execute_action_intent
from ai_web_explorer.grounded_web.action_ranker import select_unexplored_action
from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
)
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.graph import (
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager
from ai_web_explorer.grounded_web.semantic_assistor import SemanticAssistor


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

        result = await execute_action_intent(
            self.adapter,
            ActionIntent(
                action_kind=selected.action_kind,
                target_semantic_id=selected.semantic_id,
                target_description=selected.description,
                input_values=dict(selected.input_values),
                expectation=None,
                source="rule_based",
            ),
            before=before,
            available_actions=source_interactables,
        )
        concrete_action = result.action or selected
        after = result.after or before
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
            instruction=concrete_action.description or concrete_action.semantic_id,
            action=concrete_action,
            capability=None,
            target_observation=after_draft.page_description,
            observed_delta=result.observed_delta,
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind=concrete_action.action_kind,
                concrete_locator=concrete_action.locator,
                concrete_target_sample=concrete_action.semantic_id,
                input_values_used=dict(concrete_action.input_values),
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=result.execution_success,
                error=result.execution_error,
            ),
            status=result.outcome.status,
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(
            source_id,
            selected.semantic_id,
            locator=selected.locator,
        )
        return self.manager.to_graph(start_node_id=source_id)
