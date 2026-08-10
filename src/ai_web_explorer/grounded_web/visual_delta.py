from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
)
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.graph import BusinessTransition

VisualDeltaProvider = Callable[..., str]
VISUAL_CHANGE_KINDS = frozenset(
    {"none", "presentation", "state_indicator", "surface", "mixed", "unknown"}
)


@dataclass(frozen=True)
class VisualDeltaRequest:
    goal: str
    action: BrowserAction
    before_screenshot_path: str
    after_screenshot_path: str
    profile: BusinessFlowProfile | None = None
    before_signature: dict[str, Any] | None = None
    after_signature: dict[str, Any] | None = None


@dataclass(frozen=True)
class VisualDeltaTrace:
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
class VisualDeltaResult:
    planning_delta: PlanningDelta
    trace: VisualDeltaTrace
    visual_change_kind: str = "unknown"
    # Kept for loading/caller compatibility; new visual-delta exploration does
    # not produce or consume business-transition judgments.
    business_transition: BusinessTransition | None = None


def _prompt_for_request(request: VisualDeltaRequest) -> str:
    action = request.action.to_dict()
    action.pop("supporting_facts", None)
    payload = {
        "instruction": (
            "Compare the before and after screenshots for the executed web "
            "action. candidate_added_facts must contain facts visible after "
            "the action and not before. candidate_removed_facts must contain "
            "facts visible before the action and not after. Omit unchanged "
            "facts. Both lists may be empty when no fact-level visual change "
            "is visible. Return JSON only. Each fact must be a lowercase "
            "snake_case string, not an object or explanation sentence. Do "
            "not predict effects, infer hidden state, or mark anything "
            "verified. Classify the observed visual change as exactly one of "
            "none (no visible change), presentation (styling or layout only), "
            "state_indicator (a visible indicator of an existing state), "
            "surface (a visible page or component surface changed), mixed "
            "(more than one kind), or unknown (insufficient visual basis). This "
            "classification is observation metadata only, not planning authority."
        ),
        "action": action,
        "required_json_fields": [
            "candidate_added_facts",
            "candidate_removed_facts",
            "visual_change_kind",
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _empty_delta() -> PlanningDelta:
    return PlanningDelta()


def _trace(
    *,
    prompt: str,
    raw_response: str = "",
    llm_response: dict[str, Any] | None = None,
    status: str,
    error_type: str | None = None,
    error_message: str | None = None,
) -> VisualDeltaTrace:
    return VisualDeltaTrace(
        prompt=prompt,
        raw_response=raw_response,
        llm_response=llm_response,
        status=status,
        error_type=error_type,
        error_message=error_message,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _fact_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    facts: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip().lower()
        if text and re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", text):
            if text not in facts:
                facts.append(text)
        if len(facts) >= 8:
            break
    return facts


def _visual_change_kind(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in VISUAL_CHANGE_KINDS:
            return normalized
    return "unknown"


def summarize_visual_delta(
    request: VisualDeltaRequest,
    *,
    provider: VisualDeltaProvider,
) -> VisualDeltaResult:
    prompt = _prompt_for_request(request)
    try:
        raw_response = provider(
            prompt,
            before_screenshot_path=request.before_screenshot_path,
            after_screenshot_path=request.after_screenshot_path,
        )
    except Exception as error:
        return VisualDeltaResult(
            planning_delta=_empty_delta(),
            trace=_trace(
                prompt=prompt,
                status="failed",
                error_type="provider_error",
                error_message=str(error),
            ),
        )
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as error:
        return VisualDeltaResult(
            planning_delta=_empty_delta(),
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                status="failed",
                error_type="parse_error",
                error_message=str(error),
            ),
        )
    if not isinstance(parsed, dict):
        return VisualDeltaResult(
            planning_delta=_empty_delta(),
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                llm_response={"value": parsed},
                status="failed",
                error_type="parse_error",
                error_message="Visual delta response must be a JSON object.",
            ),
        )

    candidate_added = _fact_id_list(parsed.get("candidate_added_facts"))
    candidate_removed = _fact_id_list(parsed.get("candidate_removed_facts"))
    overlap = set(candidate_added) & set(candidate_removed)
    candidate_added = [fact for fact in candidate_added if fact not in overlap]
    candidate_removed = [fact for fact in candidate_removed if fact not in overlap]
    visual_change_kind = _visual_change_kind(parsed.get("visual_change_kind"))

    delta = PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=[],
        verified_removed_facts=[],
        profile_fact_ids=[],
        generated_fact_ids=[],
    )
    return VisualDeltaResult(
        planning_delta=delta,
        visual_change_kind=visual_change_kind,
        trace=_trace(
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="summarized",
        ),
    )


__all__ = [
    "VisualDeltaProvider",
    "VisualDeltaRequest",
    "VisualDeltaResult",
    "VisualDeltaTrace",
    "summarize_visual_delta",
]
