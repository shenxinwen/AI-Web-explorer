from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.safesym_bridge.models import ObservedTransition, StateSnapshot

SCHEMA_VERSION = "web-observed-graph-v1"
PAGE_DESCRIPTIONS = {
    "login": "login page",
    "inventory": "inventory page",
    "cart": "cart page",
    "checkout_info": "checkout information page",
    "checkout_overview": "checkout overview page",
    "checkout_complete": "checkout complete page",
}


def schema_type_for(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    return "string"


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


def _url_pattern_for(url: str) -> str:
    if "saucedemo.com" not in url:
        return url
    if url.endswith("/") or url == "https://www.saucedemo.com":
        return "/"
    return "/" + url.rsplit("/", 1)[-1]


def _state_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    delta: dict[str, dict[str, Any]] = {}
    for path in sorted(set(before) & set(after)):
        before_value = before.get(path)
        after_value = after.get(path)
        if before_value != after_value:
            delta[path] = {"before": before_value, "after": after_value}
    return delta


def _target_observation(snapshot: StateSnapshot) -> str:
    parts = [
        f"{path}={value}"
        for path, value in sorted(snapshot.signature.items())
        if value is not None
    ]
    description = PAGE_DESCRIPTIONS.get(snapshot.page_id, f"{snapshot.page_id} page")
    return f"{description} ({', '.join(parts)})" if parts else description


def build_observed_graph(
    *,
    app: str,
    start_node: str,
    transitions: list[ObservedTransition],
    interactable_elements_by_node: dict[str, list[InteractableElement]] | None = None,
) -> WebObservedGraph:
    node_state: OrderedDict[str, dict[str, Any]] = OrderedDict()
    edge_state: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
    interactable_elements_by_node = interactable_elements_by_node or {}

    def merge_snapshot(snapshot: StateSnapshot) -> None:
        if snapshot.page_id not in node_state:
            node_state[snapshot.page_id] = {
                "url_patterns": [],
                "state_schema": {},
                "observed_values": {},
                "last_state_snapshot": {},
                "visit_count": 0,
            }
        record = node_state[snapshot.page_id]
        pattern = _url_pattern_for(snapshot.url)
        if pattern not in record["url_patterns"]:
            record["url_patterns"].append(pattern)
        for path, value in snapshot.signature.items():
            record["state_schema"][path] = schema_type_for(value)
            values = record["observed_values"].setdefault(path, [])
            if value not in values:
                values.append(value)
        record["last_state_snapshot"] = dict(snapshot.signature)
        record["visit_count"] += 1

    for transition in transitions:
        merge_snapshot(transition.source)
        merge_snapshot(transition.target)
        edge_key = (
            transition.source.page_id,
            transition.target.page_id,
            transition.action.semantic_id,
        )
        delta = _state_delta(transition.source.signature, transition.target.signature)
        if edge_key not in edge_state:
            edge_state[edge_key] = {
                "instructions": [],
                "target_observations": [],
                "schema_deltas": [],
                "preconditions": transition.preconditions,
                "effects": transition.effects,
                "visit_count": 0,
            }
        record = edge_state[edge_key]
        if transition.action.raw_description not in record["instructions"]:
            record["instructions"].append(transition.action.raw_description)
        observation = _target_observation(transition.target)
        if observation not in record["target_observations"]:
            record["target_observations"].append(observation)
        if delta:
            record["schema_deltas"].append(delta)
        record["visit_count"] += 1

    nodes = [
        WebObservedNode(
            id=node_id,
            page_description=PAGE_DESCRIPTIONS.get(node_id, f"{node_id} page"),
            url_patterns=record["url_patterns"],
            state_schema=dict(sorted(record["state_schema"].items())),
            observed_values={
                path: values
                for path, values in sorted(record["observed_values"].items())
            },
            last_state_snapshot=dict(sorted(record["last_state_snapshot"].items())),
            interactable_elements=interactable_elements_by_node.get(node_id, []),
            visit_count=record["visit_count"],
        )
        for node_id, record in node_state.items()
    ]
    edges = [
        WebObservedEdge(
            source=source,
            target=target,
            semantic_action=action,
            instructions=record["instructions"],
            target_observations=record["target_observations"],
            schema_deltas=record["schema_deltas"],
            preconditions=record["preconditions"],
            effects=record["effects"],
            visit_count=record["visit_count"],
        )
        for (source, target, action), record in edge_state.items()
    ]
    return WebObservedGraph(
        app=app,
        start_node=start_node,
        total_steps_completed=len(transitions),
        nodes=nodes,
        edges=edges,
    )
