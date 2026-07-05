from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "web-observed-graph-v1"


@dataclass(frozen=True)
class InteractableElement:
    description: str
    position: str
    explored: bool = False
    execution_hints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "description": self.description,
            "position": self.position,
            "explored": self.explored,
        }
        if self.execution_hints:
            data["execution_hints"] = dict(self.execution_hints)
        return data


@dataclass(frozen=True)
class WebObservedNode:
    id: str
    page_description: str
    url_patterns: list[str]
    state_schema: dict[str, str]
    observed_values: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    interactable_elements: list[InteractableElement] = field(default_factory=list)
    visit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_description": self.page_description,
            "url_patterns": self.url_patterns,
            "state_schema": self.state_schema,
            "observed_values": self.observed_values,
            "last_state_snapshot": self.last_state_snapshot,
            "interactable_elements": [
                element.to_dict() for element in self.interactable_elements
            ],
            "visit_count": self.visit_count,
        }


@dataclass(frozen=True)
class WebObservedEdge:
    source: str
    target: str
    semantic_action: str
    instructions: list[str]
    target_observations: list[str]
    schema_deltas: list[dict[str, dict[str, Any]]]
    preconditions: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    visit_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "semantic_action": self.semantic_action,
            "instructions": self.instructions,
            "target_observations": self.target_observations,
            "schema_deltas": self.schema_deltas,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "visit_count": self.visit_count,
        }


@dataclass(frozen=True)
class WebObservedGraph:
    app: str
    start_node: str
    total_steps_completed: int
    nodes: list[WebObservedNode]
    edges: list[WebObservedEdge]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "app": self.app,
                "start_node": self.start_node,
                "total_steps_completed": self.total_steps_completed,
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
