"""Prompt construction for the generic Stagehand exploration path."""

from __future__ import annotations


GENERIC_EXPLORATION_ACTION_POLICY = (
    "Execute exactly one selected business action from visible page evidence. "
    "If Web-KOBE has already selected an action, complete only that action and "
    "stop after the first visible completion or clear failure. If no selected "
    "action is supplied, use this only as fallback: choose one obvious business "
    "action and execute it once. Avoid low-value footer, legal, social, theme, "
    "and language actions unless they are central to the site. Report visible "
    "evidence."
)


def build_generic_stagehand_exploration_goal(
    *,
    site_purpose: str | None = None,
    allow_final_order: bool = False,
) -> str:
    purpose = site_purpose or "the current website"
    sections = [
        f"Site purpose:\n{purpose}",
        f"Action policy:\n{GENERIC_EXPLORATION_ACTION_POLICY}",
        (
            "Memory policy:\nWeb-KOBE may append exploration memory below. "
            "Use it only as context for the already selected action, and do "
            "not choose a different business goal from memory text."
        ),
    ]
    if allow_final_order:
        sections.append(
            "Test boundary:\nThis is an explicit controlled test-site run; "
            "final confirmation is allowed when visible and relevant. Use only "
            "fictional values supplied by the test environment."
        )
    return "\n\n".join(sections)


__all__ = ["GENERIC_EXPLORATION_ACTION_POLICY", "build_generic_stagehand_exploration_goal"]
