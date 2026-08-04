from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.business_profile import BusinessFlowProfile
from ai_web_explorer.grounded_web.graph import BusinessAffordance

VisualAffordanceProvider = Callable[..., str]


@dataclass(frozen=True)
class VisualAffordanceRequest:
    goal: str
    profile: BusinessFlowProfile
    current_screenshot_path: str
    current_signature: dict[str, Any] | None = None
    current_planning_facts: list[str] | None = None
    max_actions: int = 5


@dataclass(frozen=True)
class VisualAffordanceTrace:
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
class VisualAffordanceResult:
    business_affordances: list[BusinessAffordance]
    trace: VisualAffordanceTrace
    state_summary: str | None = None


def _prompt_for_request(request: VisualAffordanceRequest) -> str:
    payload = {
        "instruction": (
            "Inspect the current web page screenshot and list direct next-step "
            "business actions that are immediately executable from the visible "
            "current state. Return JSON only. "
            f"Return at most {request.max_actions} actions. This limit is an "
            "upper bound, not a quota. Return fewer actions when fewer are "
            "actually available. Do not fill the list with "
            "background, global, generic, or merely visible controls. Only "
            "include actions grounded in controls clearly visible in the "
            "screenshot. Do not infer actions from common website patterns or "
            "expected workflows. Do not infer graph memory, business stages, "
            "whether an action was previously attempted, or whether Web-KOBE "
            "should create or merge a node. "
            "Identify the current active business surface first. An active "
            "surface may be the main page content, a focused panel, modal, "
            "dialog, drawer, popover, form, details view, table row, selected "
            "item, selected object, or visible workflow step. If a focused "
            "surface is open, only include actions inside that focused surface "
            "plus explicit close, dismiss, back, cancel, or return actions for "
            "leaving it. Exclude background or global page controls when a "
            "focused surface is open, unless the control is visibly part of "
            "that focused surface. "
            "A business action is a visible action that can directly change "
            "the user's business state, reveal a new business state, submit or "
            "edit business data, select or configure a business object, "
            "navigate to a directly relevant business surface, or close/leave "
            "the current active business surface. Each returned action must "
            "have a concrete expected visible change. If you cannot describe "
            "a concrete visible change, omit the action. Presentation, "
            "preference, display, sorting, filtering, search, theme, language, "
            "newsletter, footer, social, or cosmetic actions should be omitted "
            "when any more direct active-surface business action is available. "
            "Include those lower-information actions only when they are the "
            "main available actions in the current active business surface."
        ),
        "goal": request.goal,
        "current_signature": dict(request.current_signature or {}),
        "required_json_fields": [
            "active_surface",
            "state_summary",
            "business_affordances",
        ],
        "relevance_hint_meaning": {
            "core": (
                "A primary action in the active surface that directly changes, "
                "reveals, submits, edits, selects, configures, or advances a "
                "business state."
            ),
            "supporting": (
                "A secondary active-surface action such as close, back, cancel, "
                "dismiss, return, open details, expand a relevant panel, or "
                "navigate to a directly related surface."
            ),
            "low_value": (
                "A visible action that mostly changes presentation, ordering, "
                "filtering, preference settings, search results, or "
                "non-essential content."
            ),
            "unknown": (
                "Use only when the action is visible but its business role is "
                "unclear."
            ),
        },
        "examples": [
            (
                "If a focused dialog or details view contains one submit/select "
                "action and one close action, return only those actions."
            ),
            (
                "If a form step is active, return the visible actions that "
                "submit, continue, save, cancel, or edit that form step."
            ),
            (
                "If a table row, record view, item view, or selected object is "
                "active, return actions directly available for that object, not "
                "unrelated page-wide controls."
            ),
            "Do not return an action unless its target control is clearly visible.",
        ],
        "business_affordance_schema": {
            "action_name": "snake_case next-step business action name",
            "label": "optional visible label",
            "relevance_hint": "core | supporting | low_value | unknown",
            "target_hint": "short visible target hint for Stagehand execution",
            "expected_change": "short expected visible business change",
            "evidence": "one short sentence grounded in visible page evidence",
            "confidence": "number from 0 to 1",
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _trace(
    *,
    prompt: str,
    raw_response: str = "",
    llm_response: dict[str, Any] | None = None,
    status: str,
    error_type: str | None = None,
    error_message: str | None = None,
) -> VisualAffordanceTrace:
    return VisualAffordanceTrace(
        prompt=prompt,
        raw_response=raw_response,
        llm_response=llm_response,
        status=status,
        error_type=error_type,
        error_message=error_message,
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relevance(value: Any) -> str:
    relevance = str(value or "unknown").strip().lower()
    if relevance in {"core", "supporting", "low_value", "unknown"}:
        return relevance
    return "unknown"


def _affordances_from_response(
    parsed: dict[str, Any],
    *,
    max_actions: int,
) -> list[BusinessAffordance]:
    raw_items = parsed.get("business_affordances")
    if not isinstance(raw_items, list):
        return []

    affordances: list[BusinessAffordance] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        action_name = _clean_text(item.get("action_name"))
        if action_name is None or action_name in seen:
            continue
        seen.add(action_name)
        affordances.append(
            BusinessAffordance(
                action_name=action_name,
                label=_clean_text(item.get("label")),
                relevance_hint=_relevance(item.get("relevance_hint")),
                target_hint=_clean_text(item.get("target_hint")),
                expected_change=_clean_text(item.get("expected_change")),
                source="vlm",
                confidence=_confidence(item.get("confidence")),
                evidence=_clean_text(item.get("evidence")),
            )
        )
        if len(affordances) >= max_actions:
            break
    return affordances


def summarize_visual_affordances(
    request: VisualAffordanceRequest,
    *,
    provider: VisualAffordanceProvider,
) -> VisualAffordanceResult:
    prompt = _prompt_for_request(request)
    try:
        raw_response = provider(
            prompt,
            current_screenshot_path=request.current_screenshot_path,
        )
    except Exception as error:
        return VisualAffordanceResult(
            business_affordances=[],
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
        return VisualAffordanceResult(
            business_affordances=[],
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                status="failed",
                error_type="parse_error",
                error_message=str(error),
            ),
        )
    if not isinstance(parsed, dict):
        return VisualAffordanceResult(
            business_affordances=[],
            trace=_trace(
                prompt=prompt,
                raw_response=raw_response,
                llm_response={"value": parsed},
                status="failed",
                error_type="parse_error",
                error_message="Visual affordance response must be a JSON object.",
            ),
        )

    return VisualAffordanceResult(
        business_affordances=_affordances_from_response(
            parsed,
            max_actions=request.max_actions,
        ),
        trace=_trace(
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="summarized",
        ),
        state_summary=_clean_text(parsed.get("state_summary")),
    )


__all__ = [
    "VisualAffordanceProvider",
    "VisualAffordanceRequest",
    "VisualAffordanceResult",
    "VisualAffordanceTrace",
    "summarize_visual_affordances",
]
