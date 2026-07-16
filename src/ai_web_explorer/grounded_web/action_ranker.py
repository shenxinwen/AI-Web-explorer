from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.graph import BrowserAction


def _truthy_metadata(item: dict[str, Any], key: str) -> bool:
    metadata = item.get("metadata") or {}
    return bool(metadata.get(key))


def _metadata_value(item: dict[str, Any], key: str) -> str:
    metadata = item.get("metadata") or {}
    return str(metadata.get(key) or "")


def _rank_score(item: dict[str, Any]) -> tuple[int, int, str]:
    action_kind = str(item.get("action_kind") or "click")
    description = str(item.get("description") or "")
    locator = str(item.get("locator") or "")
    semantic_id = str(item.get("semantic_id") or "")

    if item.get("explored"):
        return (100, 0, semantic_id)
    if _truthy_metadata(item, "data-action") or _truthy_metadata(item, "data-test"):
        return (0, 0, semantic_id)
    if action_kind == "click" and description:
        return (1, 0, semantic_id)
    if action_kind == "click":
        return (2, 0, semantic_id)
    if action_kind == "select":
        return (3, 0, semantic_id)
    if action_kind in {"fill", "fill_then_click"}:
        already_has_value = bool(_metadata_value(item, "value").strip())
        return (4, 1 if already_has_value else 0, semantic_id)
    if locator:
        return (5, 0, semantic_id)
    return (6, 0, semantic_id)


def rank_interactables(interactables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(interactables, key=_rank_score)


def select_unexplored_action(
    interactables: list[dict[str, Any]],
) -> BrowserAction | None:
    for item in rank_interactables(interactables):
        if item.get("explored"):
            continue
        semantic_id = str(item.get("semantic_id") or "unknown_action")
        return BrowserAction(
            action_kind=str(item.get("action_kind") or "click"),
            locator=item.get("locator"),
            semantic_id=semantic_id,
            input_values=dict(item.get("input_values") or {}),
            description=item.get("description"),
        )
    return None
