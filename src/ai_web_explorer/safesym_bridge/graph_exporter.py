from __future__ import annotations

"""Compatibility exporter from WebObservedGraph to the older SafeSym FSM shape."""

from ai_web_explorer.safesym_bridge.models import (
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)
from ai_web_explorer.safesym_bridge.observed_graph import WebObservedGraph


def graph_to_fsm(
    graph: WebObservedGraph,
    *,
    terminal_pages: list[str],
) -> SafeSymFsm:
    actions_by_page: dict[str, list[SafeSymAction]] = {
        node.id: [] for node in graph.nodes
    }
    for edge in graph.edges:
        actions_by_page.setdefault(edge.source, []).append(
            SafeSymAction(
                id=edge.semantic_action,
                name=edge.semantic_action,
                from_page=edge.source,
                to_page=edge.target,
                is_navigation=edge.source != edge.target,
                preconditions=edge.preconditions,
                effects=edge.effects,
            )
        )

    pages = [
        SafeSymPage(
            id=node.id,
            signature_schema=node.state_schema,
            actions=actions_by_page.get(node.id, []),
        )
        for node in graph.nodes
    ]
    return SafeSymFsm(
        app=graph.app,
        initial_page_id=graph.start_node,
        terminal_pages=terminal_pages,
        pages=pages,
    )
