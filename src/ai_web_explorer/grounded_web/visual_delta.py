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
    business_transition: BusinessTransition | None = None


def _prompt_for_request(request: VisualDeltaRequest) -> str:
    payload = {
        "instruction": (
            "Compare the before and after screenshots for the executed web "
            "action and report only short business-state fact phrases visibly "
            "observed after the action or visibly removed by the action. "
            "Return JSON only. Each candidate fact must be a lowercase "
            "snake_case string, not an object or explanation sentence. Do "
            "not predict effects, infer hidden state, or mark anything "
            "verified. The "
            "business_relevance field must be exactly one enum value from "
            "business_relevance_enum, not an explanation sentence."
        ),
        "business_relevance_enum": ["core", "supporting", "low_value", "unknown"],
        "action": request.action.to_dict(),
        "before_signature": dict(request.before_signature or {}),
        "after_signature": dict(request.after_signature or {}),
        "required_json_fields": [
            "business_action_name",
            "business_relevance",
            "meaningful_change",
            "candidate_added_facts",
            "candidate_removed_facts",
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
    if "low_value" in relevance or "low value" in relevance:
        return "low_value"
    if any(
        token in relevance
        for token in (
            "minor",
            "cosmetic",
            "sort",
            "filter",
            "preference",
            "does not affect",
        )
    ):
        return "low_value"
    if any(
        token in relevance
        for token in (
            "supporting",
            "auxiliary",
            "navigation",
            "helps",
            "assist",
        )
    ):
        return "supporting"
    if any(
        token in relevance
        for token in (
            "core",
            "key",
            "primary",
            "purchase",
            "checkout",
            "cart",
            "product selection",
            "order",
        )
    ):
        return "core"
    return "unknown"


def _business_transition_from_response(
    parsed: dict[str, Any],
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

    candidate_added = _fact_id_list(parsed.get("candidate_added_facts"))
    candidate_removed = _fact_id_list(parsed.get("candidate_removed_facts"))
    generated_facts = list(dict.fromkeys(candidate_added + candidate_removed))

    delta = PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=[],
        verified_removed_facts=[],
        profile_fact_ids=[],
        generated_fact_ids=generated_facts,
        confidence=parsed.get("confidence"),
        uncertainty_reason="visual delta has not been structurally verified",
    )
    business_transition = _business_transition_from_response(parsed)
    return VisualDeltaResult(
        planning_delta=delta,
        trace=_trace(
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="summarized",
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
