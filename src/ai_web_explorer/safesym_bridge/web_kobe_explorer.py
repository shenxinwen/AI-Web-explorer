from __future__ import annotations

from typing import Any, Protocol

from ai_web_explorer.safesym_bridge.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph_manager import WebKobeGraphManager
from ai_web_explorer.safesym_bridge.web_semantic_assistor import SemanticAssistor


class WebKobeAdapter(Protocol):
    app_name: str

    async def observe_state(self) -> StateSnapshot:
        ...

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        ...

    async def execute(self, action: BrowserAction) -> bool:
        ...


def _schema_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any] | None:
    delta: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            delta[key] = {"before": before_value, "after": after_value}
    return delta or None


def _observed_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    evidence = [Evidence(source="web_kobe_transition_diff", url=url)]
    deltas: list[ObservedDelta] = []
    for key, value in (_schema_delta(before, after) or {}).items():
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


def _first_unexplored_action(
    interactables: list[dict[str, Any]],
) -> BrowserAction | None:
    for item in interactables:
        if item.get("explored"):
            continue
        semantic_id = str(item.get("semantic_id") or "unknown_action")
        return BrowserAction(
            action_kind=str(item.get("action_kind") or "click"),
            locator=item.get("locator"),
            semantic_id=semantic_id,
            description=item.get("description"),
        )
    return None


class WebKobeExplorer:
    def __init__(
        self,
        *,
        adapter: WebKobeAdapter,
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

        selected = _first_unexplored_action(before_interactables)
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

        delta = _schema_delta(
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
                error=None if success else "adapter execution returned false",
            ),
            status="verified" if success else "failed_execution",
            evidence=[Evidence(source="web_kobe_explorer", url=before.url)],
        )
        self.manager.add_edge(edge)
        self.manager.mark_interactable_explored(source_id, selected.semantic_id)
        return self.manager.to_graph(start_node_id=source_id)
