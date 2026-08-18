"""Minimal VLM observation contract for one executed browser action."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id

ActionOutcomeProvider = Callable[..., str]
VALID_OUTCOMES = frozenset({"success", "failed", "uncertain"})


@dataclass(frozen=True)
class ActionOutcomeTrace:
    prompt: str
    raw_response: str
    llm_response: dict[str, Any] | None
    status: str
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "llm_response": (
                dict(self.llm_response) if self.llm_response is not None else None
            ),
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ActionOutcomeResult:
    outcome: str
    location_change: bool
    evidence: tuple[str, ...] = ()
    trace: ActionOutcomeTrace | None = None


def semantic_observation_from_action_outcome(
    result: ActionOutcomeResult,
    *,
    source_location: str,
    target_location_hint: str | None,
    target_node_id: str,
) -> SemanticObservation | None:
    if result.outcome != "success":
        return None
    source = normalize_semantic_id(source_location)
    target = (
        normalize_semantic_id(target_location_hint)
        if result.location_change
        else source
    )
    if result.location_change and (not target or target == source):
        target = normalize_semantic_id(target_node_id)
    if not target:
        target = source
    return SemanticObservation(
        action_role=(
            "navigation" if result.location_change else "presentation_capability"
        ),
        source_location=source,
        target_location=target,
        completion_facts=[],
        candidate_required_facts=[],
        preserved_facts=[],
        evidence=list(result.evidence),
        confidence=None,
    )


def build_action_outcome_prompt(action_description: str) -> str:
    return json.dumps(
        {
            "instruction": (
                "Compare the before and after screenshots for this one executed "
                "action. Prefer a definite success or failed judgment when the "
                "screenshots provide visible evidence; use uncertain only when "
                "the images are missing, not comparable, or conflicting. Decide "
                "whether the before and after show the same active interaction "
                "surface. Field values, counts, selections, filtering, search, "
                "sorting, pagination, and styling remain the same location. If "
                "the same main heading, controls, and page layout remain active "
                "and only items change, location_change must be false. A stable "
                "page, modal, drawer, detail view, workflow step, or result "
                "interface becoming active is a location change. A brief toast, "
                "loading state, dropdown, or temporary acknowledgement does not "
                "change location. Return only the three fields in the output "
                "schema. Do not return facts, completion fields, roles, "
                "confidence, or planning data."
            ),
            "action_description": str(action_description).strip(),
            "output_schema": {
                "outcome": "success | failed | uncertain",
                "location_change": True,
                "evidence": ["short visible evidence"],
            },
            "few_shot_examples": [
                {
                    "before": "A record list is visible with several rows.",
                    "after": "The same list remains visible with fewer rows after filtering.",
                    "answer": {
                        "outcome": "success",
                        "location_change": False,
                        "evidence": ["The same record-list surface remains active."],
                    },
                },
                {
                    "before": "A table is visible with its current row order.",
                    "after": "The same table remains visible with rows in a new order after sorting.",
                    "answer": {
                        "outcome": "success",
                        "location_change": False,
                        "evidence": ["Only the table ordering changed."],
                    },
                },
                {
                    "before": "A list page is visible behind an open export dialog.",
                    "after": "A stable export dialog is active over the list page.",
                    "answer": {
                        "outcome": "success",
                        "location_change": True,
                        "evidence": ["The export dialog is now the active surface."],
                    },
                },
                {
                    "before": "A form is visible with an empty required field.",
                    "after": "The same form remains visible and shows a validation error.",
                    "answer": {
                        "outcome": "failed",
                        "location_change": False,
                        "evidence": ["The form remains active and shows validation feedback."],
                    },
                },
                {
                    "before": "A project-detail form is visible with editable fields.",
                    "after": "The same project-detail form remains visible with completed values.",
                    "answer": {
                        "outcome": "success",
                        "location_change": False,
                        "evidence": ["The same detail form remains the active surface."],
                    },
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _evidence(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, list):
        return tuple(text for item in value if (text := str(item).strip()))
    raise ValueError("action outcome evidence must be a string or array")


def parse_action_outcome(payload: str | dict[str, Any]) -> ActionOutcomeResult:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid action outcome JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("action outcome must be a JSON object")
    expected = {"outcome", "location_change", "evidence"}
    if set(payload) != expected:
        raise ValueError("action outcome has unsupported or missing fields")
    outcome = str(payload["outcome"] or "").strip().lower()
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"unsupported action outcome: {outcome}")
    if not isinstance(payload["location_change"], bool):
        raise ValueError("location_change must be boolean")
    return ActionOutcomeResult(
        outcome=outcome,
        location_change=payload["location_change"],
        evidence=_evidence(payload["evidence"]),
    )


def summarize_action_outcome(
    *,
    before_screenshot_path: str,
    after_screenshot_path: str,
    action_description: str,
    provider: ActionOutcomeProvider,
) -> ActionOutcomeResult:
    prompt = build_action_outcome_prompt(action_description)
    raw_response = ""
    try:
        raw_response = provider(
            prompt,
            before_screenshot_path=before_screenshot_path,
            after_screenshot_path=after_screenshot_path,
        )
        parsed = parse_action_outcome(raw_response)
    except Exception as error:
        return ActionOutcomeResult(
            outcome="uncertain",
            location_change=False,
            trace=ActionOutcomeTrace(
                prompt=prompt,
                raw_response=raw_response,
                llm_response=None,
                status="failed",
                error_type=type(error).__name__,
                error_message=str(error),
            ),
        )
    trace = ActionOutcomeTrace(
        prompt=prompt,
        raw_response=raw_response,
        llm_response={
            "outcome": parsed.outcome,
            "location_change": parsed.location_change,
            "evidence": list(parsed.evidence),
        },
        status="summarized",
    )
    return ActionOutcomeResult(
        outcome=parsed.outcome,
        location_change=parsed.location_change,
        evidence=parsed.evidence,
        trace=trace,
    )


__all__ = [
    "ActionOutcomeProvider",
    "ActionOutcomeResult",
    "ActionOutcomeTrace",
    "VALID_OUTCOMES",
    "build_action_outcome_prompt",
    "parse_action_outcome",
    "summarize_action_outcome",
    "semantic_observation_from_action_outcome",
]
