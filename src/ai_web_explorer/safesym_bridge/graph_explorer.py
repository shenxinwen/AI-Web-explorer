from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)
from ai_web_explorer.safesym_bridge.observed_graph import (
    InteractableElement,
    WebObservedGraph,
    build_observed_graph,
)


@dataclass(frozen=True)
class ExplorationAction:
    raw_description: str
    semantic_id: str
    page_id: str
    execution_kind: str
    selector: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    position: str = ""


class ExplorationAdapter(Protocol):
    start_url: str
    app_name: str
    start_node: str

    async def observe_state(self, page) -> StateSnapshot:
        ...

    async def list_actions(
        self,
        page,
        state: StateSnapshot,
    ) -> list[ExplorationAction]:
        ...

    async def execute_action(self, page, action: ExplorationAction) -> None:
        ...

    def is_goal_state(self, state: StateSnapshot) -> bool:
        ...


@dataclass(frozen=True)
class ExplorationRunResult:
    graph: WebObservedGraph
    transitions: list[ObservedTransition]
    final_state: StateSnapshot
    stop_reason: str
    failed_actions: list[str] = field(default_factory=list)


def choose_next_unexplored_action(
    current_state: StateSnapshot,
    actions: list[ExplorationAction],
    graph: WebObservedGraph | None,
) -> ExplorationAction | None:
    explored = set()
    if graph is not None:
        explored = {
            edge.semantic_action
            for edge in graph.edges
            if edge.source == current_state.page_id
        }
    for action in actions:
        if action.page_id == current_state.page_id and action.semantic_id not in explored:
            return action
    return None


def _element_for_action(
    action: ExplorationAction,
    *,
    explored: bool,
) -> InteractableElement:
    hints = {}
    if action.selector:
        hints["selector"] = action.selector
    hints["execution_kind"] = action.execution_kind
    return InteractableElement(
        description=action.raw_description,
        position=action.position,
        explored=explored,
        execution_hints=hints,
    )


class GraphExplorer:
    def __init__(self, adapter: ExplorationAdapter, *, max_steps: int = 20):
        self.adapter = adapter
        self.max_steps = max_steps

    async def run(self, page, *, output_path: Path | None = None) -> ExplorationRunResult:
        transitions: list[ObservedTransition] = []
        failed_actions: list[str] = []
        interactables: dict[str, dict[str, InteractableElement]] = {}
        graph: WebObservedGraph | None = None
        current_state = await self.adapter.observe_state(page)
        stop_reason = "max_steps_reached"

        for _ in range(self.max_steps):
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
                interactable_elements_by_node=self._interactables_by_node(
                    interactables
                ),
            )
            if self.adapter.is_goal_state(current_state):
                stop_reason = "goal_reached"
                break

            actions = await self.adapter.list_actions(page, current_state)
            page_elements = interactables.setdefault(current_state.page_id, {})
            for candidate in actions:
                page_elements.setdefault(
                    candidate.semantic_id,
                    _element_for_action(candidate, explored=False),
                )
            selected = choose_next_unexplored_action(current_state, actions, graph)
            if selected is None:
                stop_reason = "no_unexplored_actions"
                break

            before = current_state
            try:
                await self.adapter.execute_action(page, selected)
            except Exception:
                failed_actions.append(selected.raw_description)
                continue

            after = await self.adapter.observe_state(page)
            interactables[before.page_id][selected.semantic_id] = _element_for_action(
                selected,
                explored=True,
            )
            transitions.append(
                ObservedTransition(
                    source=before,
                    target=after,
                    action=ObservedAction(
                        raw_description=selected.raw_description,
                        semantic_id=selected.semantic_id,
                        playwright_calls=[],
                    ),
                    preconditions=preconditions_for(selected.semantic_id),
                    effects=infer_effects(before, after),
                )
            )
            current_state = after
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
                interactable_elements_by_node=self._interactables_by_node(
                    interactables
                ),
            )
            self._write_graph(graph, output_path)
        else:
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
                interactable_elements_by_node=self._interactables_by_node(
                    interactables
                ),
            )

        if graph is None:
            graph = build_observed_graph(
                app=self.adapter.app_name,
                start_node=self.adapter.start_node,
                transitions=transitions,
                interactable_elements_by_node=self._interactables_by_node(
                    interactables
                ),
            )
        self._write_graph(graph, output_path)
        return ExplorationRunResult(
            graph=graph,
            transitions=transitions,
            final_state=current_state,
            stop_reason=stop_reason,
            failed_actions=failed_actions,
        )

    @staticmethod
    def _write_graph(graph: WebObservedGraph, output_path: Path | None) -> None:
        if output_path is None:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _interactables_by_node(
        interactables: dict[str, dict[str, InteractableElement]],
    ) -> dict[str, list[InteractableElement]]:
        return {
            node_id: list(elements.values())
            for node_id, elements in interactables.items()
        }
