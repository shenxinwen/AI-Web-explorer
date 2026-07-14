from __future__ import annotations

import re

from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unnamed"


def browser_actions_from_candidates(
    candidates: list[DomInteractableCandidate],
) -> list[BrowserAction]:
    actions: list[BrowserAction] = []
    for candidate in candidates:
        if candidate.kind in {"input", "textarea", "select"}:
            action_kind = "fill" if candidate.kind != "select" else "select"
        else:
            action_kind = "click"
        visible = candidate.name or candidate.metadata.get("id") or candidate.locator
        semantic_id = f"{candidate.kind}_{_slug(visible)}"
        actions.append(
            BrowserAction(
                action_kind=action_kind,
                locator=candidate.locator,
                semantic_id=semantic_id,
                description=candidate.name,
            )
        )
    return actions
