from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from ai_web_explorer.grounded_web.models import StateSnapshot


@dataclass(frozen=True)
class StateSummary:
    text: str
    context_markers: tuple[str, ...]
    planning_facts: tuple[str, ...]


def _normalized_path(snapshot: StateSnapshot) -> str:
    signature_path = snapshot.signature.get("url_path")
    if signature_path:
        return str(signature_path)
    return urlsplit(snapshot.url).path or "/"


def _control_description(item: dict[str, Any]) -> str:
    description = str(item.get("description") or "")
    if item.get("action_kind") == "business_intent" or _looks_like_policy_text(
        description
    ):
        description = str(
            item.get("action_label")
            or item.get("canonical_action_name")
            or item.get("semantic_id")
            or ""
        )
    if not description:
        description = str(item.get("semantic_id") or "")
    return " ".join(description.split())


def _looks_like_policy_text(description: str) -> bool:
    return any(
        marker in description
        for marker in (
            "Action policy:",
            "Memory policy:",
            "Site purpose:",
        )
    )


def _control_descriptions(interactables: list[dict[str, Any]]) -> list[str]:
    controls: list[str] = []
    for item in interactables:
        description = _control_description(item)
        if description and description not in controls:
            controls.append(description)
    return controls[:12]


def _context_markers(signature: dict[str, Any]) -> tuple[str, ...]:
    markers: list[str] = []
    cart_count = signature.get("cart_count")
    if cart_count not in (None, "", 0, "0", False):
        markers.append("cart_non_empty")
    if signature.get("cart_has_items") is True:
        markers.append("cart_non_empty")
    if signature.get("modal_open") is True or signature.get("dialog_open") is True:
        markers.append("modal_open")
    if signature.get("form_visible") is True:
        markers.append("form_visible")
    return tuple(dict.fromkeys(markers))


def build_state_summary(
    *,
    snapshot: StateSnapshot,
    interactables: list[dict[str, Any]],
    active_planning_facts: Iterable[str] = (),
    visual_summary: str | None = None,
) -> StateSummary:
    facts = tuple(dict.fromkeys(str(fact) for fact in active_planning_facts))
    controls = _control_descriptions(interactables)
    lines = [
        f"url_path: {_normalized_path(snapshot)}",
        f"title: {snapshot.title}",
    ]
    if facts:
        lines.append("planning_facts: " + ", ".join(facts))
    markers = _context_markers(snapshot.signature)
    if markers:
        lines.append("context_markers: " + ", ".join(markers))
    if controls:
        lines.append("controls: " + "; ".join(controls))
    if visual_summary:
        lines.append("visual: " + " ".join(visual_summary.split()))
    return StateSummary(
        text="\n".join(lines),
        context_markers=markers,
        planning_facts=facts,
    )
