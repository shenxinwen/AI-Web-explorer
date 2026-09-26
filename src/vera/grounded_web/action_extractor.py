from __future__ import annotations

import re

from vera.grounded_web.dom_observer import DomInteractableCandidate
from vera.grounded_web.graph import BrowserAction


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return cleaned or "unnamed"


def _default_input_value(candidate: DomInteractableCandidate) -> str:
    text = " ".join(
        [
            candidate.name,
            candidate.locator,
            candidate.metadata.get("type", ""),
            candidate.metadata.get("placeholder", ""),
            candidate.metadata.get("aria-label", ""),
        ]
    ).lower()
    input_type = candidate.metadata.get("type", "").lower()

    if input_type == "email" or "email" in text:
        return "test@example.com"
    if input_type == "password" or "password" in text:
        return "test-password"
    if input_type in {"number", "range"} or "quantity" in text or "qty" in text:
        return "1"
    if input_type == "search" or "search" in text:
        return "sample"
    if "user" in text or "login" in text:
        return "test-user"
    return "test"


def _input_values_for(candidate: DomInteractableCandidate) -> dict[str, str]:
    if candidate.kind in {"input", "textarea"}:
        return {candidate.locator: _default_input_value(candidate)}
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
                action_label=candidate.name,
                canonical_action_name=f"{action_kind}_{_slug(visible)}",
                naming_provenance={"source": "dom_candidate"},
            )
        )
    return actions
