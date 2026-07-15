from __future__ import annotations

import re

from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate
from ai_web_explorer.grounded_web.graph import BrowserAction


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unnamed"


def _input_values_for(candidate: DomInteractableCandidate) -> dict[str, str]:
    if candidate.kind in {"input", "textarea"}:
        return {candidate.locator: "test"}
    if candidate.kind == "select":
        raw_options = candidate.metadata.get("option-values", "")
        options = [
            option.strip() for option in raw_options.split(",") if option.strip()
        ]
        if options:
            return {candidate.locator: options[0]}
    return {}


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
        semantic_id = f"{candidate.id}_{candidate.kind}_{_slug(visible)}"
        actions.append(
            BrowserAction(
                action_kind=action_kind,
                locator=candidate.locator,
                semantic_id=semantic_id,
                input_values=_input_values_for(candidate),
                description=candidate.name,
            )
        )
    return actions
