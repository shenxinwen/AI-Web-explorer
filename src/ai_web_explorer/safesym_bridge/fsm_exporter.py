from __future__ import annotations

from collections import defaultdict
from typing import Any

from ai_web_explorer.safesym_bridge.models import (
    ObservedTransition,
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)


def schema_type_for(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "string"


def _remember_page(page_id: str, page_order: list[str]) -> None:
    if page_id not in page_order:
        page_order.append(page_id)


def _collect_page_schemas(
    transitions: list[ObservedTransition],
) -> tuple[list[str], dict[str, dict[str, str]]]:
    page_order: list[str] = []
    schemas: dict[str, dict[str, str]] = defaultdict(dict)

    for transition in transitions:
        _remember_page(transition.source.page_id, page_order)
        _remember_page(transition.target.page_id, page_order)

        for snapshot in (transition.source, transition.target):
            for path, value in snapshot.signature.items():
                schemas[snapshot.page_id][path] = schema_type_for(value)

        for effect in transition.effects:
            path = str(effect["path"])
            value = effect.get("value")
            value_type = schema_type_for(value)
            schemas[transition.source.page_id][path] = value_type
            schemas[transition.target.page_id][path] = value_type

    return page_order, {
        page_id: dict(sorted(schema.items())) for page_id, schema in schemas.items()
    }


def build_fsm(
    app: str,
    initial_page_id: str,
    terminal_pages: list[str],
    transitions: list[ObservedTransition],
) -> SafeSymFsm:
    page_order, schemas = _collect_page_schemas(transitions)
    actions_by_page: dict[str, list[SafeSymAction]] = defaultdict(list)

    for transition in transitions:
        action_id = transition.action.semantic_id
        actions_by_page[transition.source.page_id].append(
            SafeSymAction(
                id=action_id,
                name=action_id,
                from_page=transition.source.page_id,
                to_page=transition.target.page_id,
                is_navigation=transition.source.page_id != transition.target.page_id,
                preconditions=transition.preconditions,
                effects=transition.effects,
            )
        )

    pages = [
        SafeSymPage(
            id=page_id,
            signature_schema=schemas.get(page_id, {}),
            actions=actions_by_page.get(page_id, []),
        )
        for page_id in page_order
    ]

    return SafeSymFsm(
        app=app,
        initial_page_id=initial_page_id,
        terminal_pages=terminal_pages,
        pages=pages,
    )
