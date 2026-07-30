from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
)
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.graph import BusinessTransition

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
    visual_change_summary: str | None = None
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
            "visual_change_summary": self.visual_change_summary,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class VisualDeltaResult:
    planning_delta: PlanningDelta
    trace: VisualDeltaTrace
    business_transition: BusinessTransition | None = None


def _fact_ids(profile: BusinessFlowProfile) -> set[str]:
    return {fact.fact_id for fact in profile.planning_facts}


def _prompt_for_request(request: VisualDeltaRequest) -> str:
    payload = {
        "instruction": (
            "Compare the before and after screenshots for the executed web "
            "action. Return JSON only. Prefer candidate planning facts from "
            "the provided profile when they fit, but you may propose new "
            "candidate facts for meaningful business states not covered by "
            "the profile. Do not mark anything verified."
        ),
        "goal": request.goal,
        "action": request.action.to_dict(),
        "profile": request.profile.to_dict(),
        "before_signature": dict(request.before_signature or {}),
        "after_signature": dict(request.after_signature or {}),
        "required_json_fields": [
            "visible_change_summary",
            "business_action_name",
            "business_relevance",
            "meaningful_change",
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
    visual_change_summary: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> VisualDeltaTrace:
    return VisualDeltaTrace(
        prompt=prompt,
        raw_response=raw_response,
        llm_response=llm_response,
        status=status,
        visual_change_summary=visual_change_summary,
        error_type=error_type,
        error_message=error_message,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _summary_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return None


def _fact_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    facts: list[str] = []
    for item in value:
        candidate = item.get("fact_id") if isinstance(item, dict) else item
        text = str(candidate).strip() if candidate is not None else ""
        if text:
            facts.append(text)
    return facts


def _evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    evidence: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("description"):
            evidence.append(str(item["description"]))
        elif isinstance(item, (dict, list)):
            evidence.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        else:
            evidence.append(str(item))
    return evidence


def _meaningful_change(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "meaningful", "changed"}:
            return True
        if lowered in {"false", "no", "no_change", "unchanged"}:
            return False
    return None


def _business_relevance(value: Any) -> str:
    relevance = str(value or "unknown").strip().lower()
    if relevance in {"core", "supporting", "low_value", "unknown"}:
        return relevance
    return "unknown"


def _business_transition_from_response(
    parsed: dict[str, Any],
    *,
    visual_change_summary: str,
    evidence: list[str],
) -> BusinessTransition | None:
    action_name = parsed.get("business_action_name")
    relevance = parsed.get("business_relevance")
    meaningful_change = parsed.get("meaningful_change")
    if action_name is None and relevance is None and meaningful_change is None:
        return None
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
    return BusinessTransition(
        action_name=str(action_name).strip() if action_name is not None else None,
        relevance=_business_relevance(relevance),
        meaningful_change=_meaningful_change(meaningful_change),
        judge_source="vlm",
        summary=_summary_text(parsed.get("business_change_summary"))
        or visual_change_summary,
        evidence=evidence,
        confidence=confidence,
    )


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

    allowed = _fact_ids(request.profile)
    visual_change_summary = _summary_text(parsed.get("visible_change_summary"))
    if visual_change_summary is None:
        return VisualDeltaResult(
            planning_delta=_empty_delta(),
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                llm_response=parsed,
                status="failed",
                error_type="missing_visual_change_summary",
                error_message="Visual delta response must include visible_change_summary.",
            ),
        )

    candidate_added = _fact_id_list(parsed.get("candidate_added_facts"))
    candidate_removed = _fact_id_list(parsed.get("candidate_removed_facts"))
    profile_facts = [
        fact for fact in candidate_added + candidate_removed if fact in allowed
    ]
    generated_facts = [
        fact for fact in candidate_added + candidate_removed if fact not in allowed
    ]

    evidence = _evidence_list(parsed.get("evidence"))
    delta = PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=[],
        verified_removed_facts=[],
        profile_fact_ids=list(dict.fromkeys(profile_facts)),
        generated_fact_ids=list(dict.fromkeys(generated_facts)),
        evidence=evidence,
        confidence=parsed.get("confidence"),
        uncertainty_reason="visual delta has not been structurally verified",
    )
    business_transition = _business_transition_from_response(
        parsed,
        visual_change_summary=visual_change_summary,
        evidence=evidence,
    )
    return VisualDeltaResult(
        planning_delta=delta,
        trace=_trace(
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="summarized",
            visual_change_summary=visual_change_summary,
        ),
        business_transition=business_transition,
    )


__all__ = [
    "VisualDeltaProvider",
    "VisualDeltaRequest",
    "VisualDeltaResult",
    "VisualDeltaTrace",
    "summarize_visual_delta",
]
