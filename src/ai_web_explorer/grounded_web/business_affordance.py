from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.graph import BusinessAffordance

VisualAffordanceProvider = Callable[..., str]


@dataclass(frozen=True)
class VisualAffordanceRequest:
    goal: str
    current_screenshot_path: str
    current_signature: dict[str, Any] | None = None
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
    state_label: str | None = None


def _prompt_for_request(request: VisualAffordanceRequest) -> str:
    payload = {
        "instruction": (
            "You are a web interface observer. Inspect the current web page "
            "screenshot, identify its functional regions, and select "
            "representative business actions that are directly executable "
            "now. First classify the page as multi_region, single_surface, "
            "or uncertain. Group visible elements by shared functional "
            "purpose. Spatial proximity is only supporting evidence and is "
            "not sufficient to merge different functions. If the page is "
            "mainly focused on one object, form, dialog, detail view, or "
            "workflow, use single_surface and do not force multiple regions. "
            "Optimize for breadth of functional coverage, not interaction "
            "count. Choose at most one representative action per functional "
            "family. Prioritize actions likely to reveal a new surface, "
            "object, dialog, page, or workflow stage as core. Classify major "
            "same-surface functions as supporting. Classify local refinement "
            "actions as low_value when broader functions are available. "
            "Order core actions before supporting actions, and supporting "
            "actions before low_value actions. Avoid ambiguous umbrella "
            "actions: every action must name one concrete visible target. "
            "An action must be directly executable, have a clear business "
            "meaning, and have a visible target. For each action, list only "
            "short, stable snake_case observation fact IDs that support why it "
            "is executable. Do not include hidden, disabled, speculative, or low-level "
            "interaction steps. Do not infer actions from common website patterns "
            "or expected workflows. If multiple controls have the same purpose "
            "and expected effect, select one representative action. Keep "
            "actions separate when they affect different objects, produce "
            "different results, or serve different workflow roles. The action "
            "limit is an upper bound, not a quota. Return fewer actions when "
            "fewer are actually available. Also provide a short English "
            "snake_case state_label describing only the currently visible "
            "state. Do not describe action history, concrete objects, search "
            "terms, or item counts in the state_label. Return JSON only."
        ),
        "max_candidates": request.max_actions,
        "output_schema": {
            "state_label": "short snake_case visible state name",
            "page_mode": "multi_region | single_surface | uncertain",
            "regions": [
                {
                    "region_id": "stable identifier",
                    "purpose": "shared functional purpose",
                    "actions": [
                        {
                            "intent": "snake_case business action name",
                            "label": "visible action label or description",
                            "target": "visible action target",
                            "relevance_hint": "core | supporting | low_value",
                            "confidence": "number from 0.0 to 1.0",
                            "supporting_facts": [
                                "short_stable_snake_case_fact_id"
                            ],
                        }
                    ],
                }
            ],
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


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _clean_text(value)


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


def _supporting_fact_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    facts: list[str] = []
    for item in value:
        text = str(item).strip() if item is not None else ""
        if text and text not in facts:
            facts.append(text)
        if len(facts) >= 8:
            break
    return facts


def _affordances_from_response(
    parsed: dict[str, Any],
    *,
    max_actions: int,
) -> list[BusinessAffordance]:
    raw_items: list[Any] = []
    regions = parsed.get("regions")
    if isinstance(regions, list):
        for region in regions:
            if not isinstance(region, dict):
                continue
            actions = region.get("actions")
            if isinstance(actions, list):
                raw_items.extend(actions)
    else:
        # Keep older traces and test doubles readable after the prompt change.
        legacy_items = parsed.get("business_affordances")
        if isinstance(legacy_items, list):
            raw_items = legacy_items

    affordances: list[BusinessAffordance] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        action_name = _clean_text(item.get("intent") or item.get("action_name"))
        if action_name is None or action_name in seen:
            continue
        seen.add(action_name)
        affordances.append(
            BusinessAffordance(
                action_name=action_name,
                label=_clean_text(item.get("label")),
                relevance_hint=_relevance(item.get("relevance_hint")),
                target_hint=_clean_text(item.get("target") or item.get("target_hint")),
                source="vlm",
                confidence=_confidence(item.get("confidence")),
                supporting_facts=_supporting_fact_list(
                    item.get("supporting_facts")
                ),
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
        state_label=_optional_string(parsed.get("state_label")),
    )


__all__ = [
    "VisualAffordanceProvider",
    "VisualAffordanceRequest",
    "VisualAffordanceResult",
    "VisualAffordanceTrace",
    "summarize_visual_affordances",
]
