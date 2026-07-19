from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
)
from ai_web_explorer.grounded_web.graph import BrowserAction

VisualDeltaProvider = Callable[..., str]


@dataclass(frozen=True)
class VisualDeltaRequest:
    goal: str
    action: BrowserAction
    profile: BusinessFlowProfile
    before_screenshot_path: str
    after_screenshot_path: str
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


def _fact_ids(profile: BusinessFlowProfile) -> set[str]:
    return {fact.fact_id for fact in profile.planning_facts}


def _prompt_for_request(request: VisualDeltaRequest) -> str:
    payload = {
        "instruction": (
            "Compare the before and after screenshots for the executed web "
            "action. Return JSON only. Propose candidate planning facts from "
            "the provided profile, but do not mark anything verified."
        ),
        "goal": request.goal,
        "action": request.action.to_dict(),
        "profile": request.profile.to_dict(),
        "before_signature": dict(request.before_signature or {}),
        "after_signature": dict(request.after_signature or {}),
        "required_json_fields": [
            "visible_change_summary",
            "candidate_added_facts",
            "candidate_removed_facts",
            "evidence",
            "confidence",
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


def summarize_visual_delta(
    request: VisualDeltaRequest,
    *,
    provider: VisualDeltaProvider,
) -> VisualDeltaResult:
    prompt = _prompt_for_request(request)
    raw_response = provider(
        prompt,
        before_screenshot_path=request.before_screenshot_path,
        after_screenshot_path=request.after_screenshot_path,
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

    allowed = _fact_ids(request.profile)
    candidate_added = _string_list(parsed.get("candidate_added_facts"))
    candidate_removed = _string_list(parsed.get("candidate_removed_facts"))
    unknown = sorted(
        {fact for fact in candidate_added + candidate_removed if fact not in allowed}
    )
    if unknown:
        return VisualDeltaResult(
            planning_delta=_empty_delta(),
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                llm_response=parsed,
                status="failed",
                error_type="unknown_fact",
                error_message=f"Unknown profile facts: {', '.join(unknown)}",
            ),
        )

    delta = PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=[],
        verified_removed_facts=[],
        evidence=_string_list(parsed.get("evidence")),
        confidence=parsed.get("confidence"),
        uncertainty_reason="visual delta has not been structurally verified",
    )
    return VisualDeltaResult(
        planning_delta=delta,
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
