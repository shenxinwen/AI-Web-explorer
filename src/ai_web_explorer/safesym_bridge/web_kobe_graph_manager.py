from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace
from typing import Any

from ai_web_explorer.safesym_bridge.web_kobe_graph import (
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)


def _merge_schema(
    existing: dict[str, list[Any]],
    new_snapshot: dict[str, Any],
) -> dict[str, list[Any]]:
    merged = {key: list(values) for key, values in existing.items()}
    for key, value in new_snapshot.items():
        values = merged.setdefault(key, [])
        if value not in values:
            values.append(value)
    return merged


def _merge_interactables(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing]
    for item in incoming:
        incoming_locator = item.get("locator")
        existing_match = next(
            (
                existing_item
                for existing_item in merged
                if incoming_locator
                and existing_item.get("locator") == incoming_locator
            ),
            None,
        )
        if existing_match is not None:
            if existing_match.get("explored"):
                existing_match["explored"] = True
            continue

        key = (
            item.get("semantic_id"),
            item.get("locator"),
            item.get("description"),
        )
        if key not in {
            (
                merged_item.get("semantic_id"),
                merged_item.get("locator"),
                merged_item.get("description"),
            )
            for merged_item in merged
        }:
            merged.append(dict(item))
    return merged


class WebKobeGraphManager:
    def __init__(self, app: str):
        self.app = app
        self._nodes: OrderedDict[str, WebKobeNode] = OrderedDict()
        self._edges: OrderedDict[str, WebKobeEdge] = OrderedDict()
        self.total_steps_completed = 0

    def identify_or_add_node(self, node: WebKobeNode) -> str:
        existing = self._nodes.get(node.node_id)
        if existing is None:
            self._nodes[node.node_id] = replace(
                node,
                visit_count=max(node.visit_count, 1),
            )
            return node.node_id

        self._nodes[node.node_id] = replace(
            existing,
            state_schema=_merge_schema(existing.state_schema, node.last_state_snapshot),
            last_state_snapshot=dict(node.last_state_snapshot),
            state_indicators=list(node.state_indicators or existing.state_indicators),
            action_targets=list(node.action_targets or existing.action_targets),
            interactable_elements=_merge_interactables(
                existing.interactable_elements,
                node.interactable_elements,
            ),
            capabilities=list(node.capabilities or existing.capabilities),
            reference_observation=node.reference_observation
            or existing.reference_observation,
            visit_count=existing.visit_count + 1,
            evidence=list(existing.evidence or node.evidence),
        )
        return node.node_id

    def add_edge(self, edge: WebKobeEdge) -> None:
        existing = self._edges.get(edge.edge_id)
        if existing is None:
            self._edges[edge.edge_id] = edge
        else:
            self._edges[edge.edge_id] = replace(
                existing,
                visit_count=existing.visit_count + 1,
                observed_delta=list(edge.observed_delta or existing.observed_delta),
                schema_delta=edge.schema_delta or existing.schema_delta,
                execution_trace=edge.execution_trace,
                evidence=list(existing.evidence or edge.evidence),
            )
        self.total_steps_completed += 1

    def mark_interactable_explored(
        self,
        node_id: str,
        semantic_id: str,
        locator: str | None = None,
    ) -> None:
        node = self._nodes[node_id]
        interactables = []
        for item in node.interactable_elements:
            updated = dict(item)
            if (
                locator is not None
                and updated.get("locator") == locator
            ) or (
                locator is None
                and updated.get("semantic_id") == semantic_id
            ):
                updated["explored"] = True
            interactables.append(updated)
        self._nodes[node_id] = replace(node, interactable_elements=interactables)

    def interactables_for_node(self, node_id: str) -> list[dict[str, Any]]:
        node = self._nodes[node_id]
        return [dict(item) for item in node.interactable_elements]

    def to_graph(self, start_node_id: str | None = None) -> WebKobeGraph:
        resolved_start = start_node_id
        if resolved_start is None and self._nodes:
            resolved_start = next(iter(self._nodes))
        return WebKobeGraph(
            app=self.app,
            start_node_id=resolved_start or "",
            total_steps_completed=self.total_steps_completed,
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )
