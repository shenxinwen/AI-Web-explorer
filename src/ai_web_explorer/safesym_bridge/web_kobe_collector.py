from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai_web_explorer.safesym_bridge.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph_manager import (
    WebKobeGraphManager,
)
from ai_web_explorer.safesym_bridge.web_kobe_observer import WebKobeObservation


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "unknown"


def _node_id(web_state, observation: WebKobeObservation) -> str:
    return _slug(
        observation.llm_title
        or getattr(web_state, "title", "")
        or observation.url_pattern
    )


def _schema_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any] | None:
    delta = {}
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            delta[key] = {"before": before.get(key), "after": after.get(key)}
    return delta or None


class NoOpWebKobeCollector:
    def on_state_observed(self, **kwargs) -> None:
        return None

    def on_action_selected(self, **kwargs) -> None:
        return None

    def on_action_executed(self, **kwargs) -> None:
        return None

    def on_transition(self, **kwargs) -> None:
        return None


@dataclass
class _ExecutedAction:
    success: bool
    tool_calls: list
    error: str | None


class WebKobeCollector:
    def __init__(self, *, app: str):
        self.app = app
        self.manager = WebKobeGraphManager(app=app)
        self._executed: dict[int, _ExecutedAction] = {}
        self._start_node_id: str | None = None

    def on_state_observed(
        self,
        *,
        page,
        web_state,
        observation: WebKobeObservation,
    ) -> None:
        node_id = self._add_state(web_state, observation)
        if self._start_node_id is None:
            self._start_node_id = node_id

    def on_action_selected(self, *, source_state, action) -> None:
        return None

    def on_action_executed(
        self,
        *,
        action,
        success: bool,
        tool_calls: list,
        error: str | None = None,
    ) -> None:
        self._executed[id(action)] = _ExecutedAction(success, tool_calls, error)

    def on_transition(
        self,
        *,
        source_state,
        action,
        target_state,
        before_observation: WebKobeObservation,
        after_observation: WebKobeObservation,
    ) -> None:
        source_id = self._add_state(source_state, before_observation)
        target_id = self._add_state(target_state, after_observation)
        executed = self._executed.get(
            id(action),
            _ExecutedAction(
                success=getattr(action, "status", "") == "success",
                tool_calls=[],
                error=None,
            ),
        )
        semantic_id = _slug(action.description)
        delta = _schema_delta(
            before_observation.state_indicators,
            after_observation.state_indicators,
        )
        evidence = [Evidence(source="web_kobe_collector", url=before_observation.url)]
        edge = WebKobeEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            instruction=action.description,
            action=BrowserAction(
                action_kind="composite" if executed.tool_calls else "unknown",
                locator=None,
                semantic_id=semantic_id,
                description=action.description,
            ),
            capability=None,
            target_observation=(
                after_observation.llm_title or after_observation.browser_title
            ),
            observed_delta=[
                ObservedDelta(
                    field=field,
                    before=value["before"],
                    after=value["after"],
                    delta_type="state_indicator_change",
                    evidence=evidence,
                )
                for field, value in (delta or {}).items()
            ],
            schema_delta=delta,
            execution_trace=ExecutionTrace(
                concrete_action_kind="composite" if executed.tool_calls else "unknown",
                concrete_locator=None,
                concrete_target_sample=action.description,
                input_values_used={},
                before_observation_id=source_id,
                after_observation_id=target_id,
                success=executed.success,
                error=executed.error,
            ),
            status="verified" if executed.success else "failed_execution",
            evidence=evidence,
        )
        self.manager.add_edge(edge)

    def to_web_kobe_graph(self) -> WebKobeGraph:
        return self.manager.to_graph(start_node_id=self._start_node_id)

    def _add_state(self, web_state, observation: WebKobeObservation) -> str:
        node_id = _node_id(web_state, observation)
        evidence = [Evidence(source="web_kobe_collector", url=observation.url)]
        node = WebKobeNode(
            node_id=node_id,
            page_description=observation.llm_title or observation.browser_title,
            page_frame=PageFrame(
                page_id=f"{self.app}:{node_id}",
                page_type=node_id,
                url=observation.url,
                url_pattern=observation.url_pattern,
                title=observation.browser_title,
                heading=observation.heading,
                signature_hints=dict(observation.state_indicators),
                evidence=evidence,
            ),
            state_schema={
                key: [value] for key, value in observation.state_indicators.items()
            },
            last_state_snapshot=dict(observation.state_indicators),
            reference_observation=ReferenceObservation(
                url=observation.url,
                title=observation.browser_title,
            ),
            evidence=evidence,
        )
        return self.manager.identify_or_add_node(node)
