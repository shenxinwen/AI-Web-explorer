from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ai_web_explorer.grounded_web.graph import BusinessAffordance
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id

VisualAffordanceProvider = Callable[..., str]


@dataclass(frozen=True)
class VisualAffordanceRequest:
    goal: str
    current_screenshot_path: str
    current_signature: dict[str, Any] | None = None
    max_actions: int = 5
    scan_kind: str = "initial"
    semantic_location: str | None = None
    existing_action_ids: list[str] = field(default_factory=list)
    completed_action_ids: list[str] = field(default_factory=list)
    added_business_facts: list[str] = field(default_factory=list)
    removed_business_facts: list[str] = field(default_factory=list)
    semantic_profile_context: dict[str, Any] | None = None


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
    requires_by_action_id: dict[str, list[str]] = field(default_factory=dict)
    state_summary: str | None = None
    state_label: str | None = None
    location_id: str | None = None
    replacements: list[tuple[str, str]] = field(default_factory=list)
    disabled_action_ids: list[str] = field(default_factory=list)


def _prompt_for_request(request: VisualAffordanceRequest) -> str:
    scan_kind = str(request.scan_kind or "initial").strip().lower()
    if scan_kind == "initial":
        instruction = (
            "Inspect the current screenshot and return all clearly visible "
            "semantic actions that can be described precisely. First cover each "
            "distinct functional family once, then consider another action from "
            "a family. Return at most 8 actions. Use a stable action_id for "
            "each action, a concise execution description, and the visible target. "
            "Requires may reference only another action in this same response and "
            "must represent a direct prerequisite supported by visible required "
            "fields, disabled controls, labels, or visible workflow structure; "
            "this permits reasonable inference from clearly shown login or "
            "checkout steps. Independent actions must use an empty requires list. "
            "An action that has a same-response prerequisite is blocked until that "
            "prerequisite succeeds. Do not infer dependencies from undisplayed "
            "site capabilities or a complete typical workflow. Do not use visual "
            "proximity alone. "
            "Success or result text is not an action. Evidence must be short and "
            "directly visible. Do not return result states, facts, roles, or planner "
            "fields. Return JSON only."
        )
        output_schema: dict[str, Any] = {
            "actions": [
                {
                    "action_id": "stable_snake_case_action",
                    "description": "one precise visible semantic operation",
                    "target": "visible target",
                    "requires": ["other_action_id"],
                }
            ]
        }
    elif scan_kind == "targeted":
        instruction = (
            "Inspect the current screenshot only for business consequences of "
            "the supplied business fact delta. Return empty arrays when no new "
            "candidate is justified. Do not repeat completed actions. Report "
            "newly_enabled, semantically_changed, and disabled actions only."
        )
        output_schema: dict[str, Any] = {
            "location_id": "semantic location anchor",
            "newly_enabled": [
                {
                    "intent": "snake_case canonical business action",
                    "label": "visible action label or description",
                    "target": "visible action target",
                    "relevance_hint": "core | supporting | low_value",
                    "confidence": "number from 0.0 to 1.0",
                    "supporting_facts": ["short_stable_snake_case_fact_id"],
                }
            ],
            "semantically_changed": [
                {"old_action": "previous action", "new_action": "new action"}
            ],
            "disabled": ["canonical action that is no longer executable"],
        }
    else:
        instruction = (
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
        )
        output_schema = {
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
        }
    payload = {
        "instruction": instruction,
        "max_candidates": request.max_actions,
        "output_schema": output_schema,
    }
    if scan_kind != "initial":
        payload["scan_kind"] = scan_kind
    if request.semantic_location is not None:
        payload["semantic_location"] = request.semantic_location
    if request.existing_action_ids:
        payload["existing_action_ids"] = list(request.existing_action_ids)
    if request.completed_action_ids:
        payload["completed_action_ids"] = list(request.completed_action_ids)
    if request.added_business_facts or request.removed_business_facts:
        payload["business_delta"] = {
            "added": list(request.added_business_facts),
            "removed": list(request.removed_business_facts),
        }
    if request.semantic_profile_context is not None and scan_kind != "initial":
        payload["semantic_profile_context"] = request.semantic_profile_context
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


def _targeted_affordances_from_response(
    parsed: dict[str, Any], *, max_actions: int, excluded_action_ids: set[str]
) -> list[BusinessAffordance]:
    raw_items = parsed.get("newly_enabled")
    if not isinstance(raw_items, list):
        raw_items = []
    affordances = _affordances_from_response(
        {"business_affordances": raw_items}, max_actions=max_actions
    )
    return [
        affordance
        for affordance in affordances
        if affordance.action_name not in excluded_action_ids
    ][:max_actions]


def _action_id(value: Any) -> str | None:
    text = _clean_text(value)
    return text


def _initial_actions_from_response(
    parsed: dict[str, Any],
    *,
    max_actions: int,
) -> tuple[list[BusinessAffordance], dict[str, list[str]], str | None]:
    raw_items = parsed.get("actions")
    if not isinstance(raw_items, list):
        return [], {}, "initial response actions must be an array"

    records: dict[str, tuple[str, str, list[str]]] = {}
    ordered_ids: list[str] = []
    for item in raw_items[:max_actions]:
        if not isinstance(item, dict):
            return [], {}, "initial response action must be an object"
        action_id = normalize_semantic_id(item.get("action_id", ""))
        description = _clean_text(item.get("description"))
        target = _clean_text(item.get("target"))
        if not action_id or not description or not target:
            return [], {}, "initial action requires action_id, description, and target"
        if action_id in records:
            return [], {}, f"duplicate initial action_id: {action_id}"
        raw_requires = item.get("requires", [])
        if isinstance(raw_requires, str):
            raw_requires = [raw_requires]
        if not isinstance(raw_requires, list):
            return [], {}, f"requires must be an array for {action_id}"
        requires: list[str] = []
        for value in raw_requires:
            requirement = normalize_semantic_id(value)
            if requirement and requirement not in requires:
                requires.append(requirement)
        records[action_id] = (description, target, requires)
        ordered_ids.append(action_id)

    requires_by_action_id = {
        action_id: list(records[action_id][2]) for action_id in ordered_ids
    }
    known_ids = set(records)
    for action_id, requires in requires_by_action_id.items():
        for requirement in requires:
            if requirement == action_id:
                return [], {}, f"self dependency: {action_id}"
            if requirement not in known_ids:
                return [], {}, f"dangling dependency: {requirement} -> {action_id}"

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(action_id: str) -> bool:
        if action_id in visiting:
            return False
        if action_id in visited:
            return True
        visiting.add(action_id)
        for requirement in requires_by_action_id[action_id]:
            if not visit(requirement):
                return False
        visiting.remove(action_id)
        visited.add(action_id)
        return True

    if not all(visit(action_id) for action_id in ordered_ids):
        return [], {}, "cyclic initial dependency graph"

    affordances = [
        BusinessAffordance(
            action_name=action_id,
            label=records[action_id][0],
            target_hint=records[action_id][1],
            source="vlm",
        )
        for action_id in ordered_ids
    ]
    return affordances, requires_by_action_id, None


def _targeted_metadata(
    parsed: dict[str, Any],
) -> tuple[str | None, list[tuple[str, str]], list[str]]:
    location_id = _clean_text(parsed.get("location_id"))
    replacements: list[tuple[str, str]] = []
    changed = parsed.get("semantically_changed")
    if isinstance(changed, list):
        for item in changed:
            if not isinstance(item, dict):
                continue
            old_action = _action_id(item.get("old_action"))
            new_action = _action_id(item.get("new_action"))
            if old_action and new_action and (old_action, new_action) not in replacements:
                replacements.append((old_action, new_action))
    disabled: list[str] = []
    raw_disabled = parsed.get("disabled")
    if isinstance(raw_disabled, list):
        for item in raw_disabled:
            action_id = _action_id(item)
            if action_id and action_id not in disabled:
                disabled.append(action_id)
    return location_id, replacements, disabled


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

    scan_kind = str(request.scan_kind or "initial").strip().lower()
    is_initial = scan_kind == "initial"
    is_targeted = scan_kind == "targeted"
    requires_by_action_id: dict[str, list[str]] = {}
    if is_initial:
        if not isinstance(parsed.get("actions"), list):
            return VisualAffordanceResult(
                business_affordances=[],
                requires_by_action_id={},
                trace=_trace(
                    prompt=prompt,
                    raw_response=raw_response,
                    llm_response=parsed,
                    status="failed",
                    error_type="response_contract_error",
                    error_message="Initial response must contain an actions array.",
                ),
            )

        affordances, requires_by_action_id, contract_error = (
            _initial_actions_from_response(
                parsed,
                max_actions=request.max_actions,
            )
        )
        if contract_error is not None:
            return VisualAffordanceResult(
                business_affordances=[],
                requires_by_action_id={},
                trace=_trace(
                    prompt=prompt,
                    raw_response=raw_response,
                    llm_response=parsed,
                    status="failed",
                    error_type="response_contract_error",
                    error_message=contract_error,
                ),
            )
    else:
        affordances = []
    location_id = _clean_text(parsed.get("location_id"))
    replacements: list[tuple[str, str]] = []
    disabled_action_ids: list[str] = []
    if is_targeted:
        affordances = _targeted_affordances_from_response(
            parsed,
            max_actions=request.max_actions,
            excluded_action_ids={
                str(action_id).strip()
                for action_id in request.completed_action_ids
            },
        )
        targeted_location, replacements, disabled_action_ids = _targeted_metadata(parsed)
        location_id = targeted_location or location_id
    elif not is_initial:
        affordances = _affordances_from_response(
            parsed,
            max_actions=request.max_actions,
        )
        if str(request.scan_kind or "initial").strip().lower() == "supplement":
            existing = {
                str(action_id).strip() for action_id in request.existing_action_ids
            }
            affordances = [
                affordance
                for affordance in affordances
                if affordance.action_name not in existing
            ][: request.max_actions]
    return VisualAffordanceResult(
        business_affordances=affordances,
        requires_by_action_id=requires_by_action_id,
        trace=_trace(
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="summarized",
        ),
        state_summary=_clean_text(parsed.get("state_summary")),
        state_label=_optional_string(parsed.get("state_label")),
        location_id=location_id,
        replacements=replacements,
        disabled_action_ids=disabled_action_ids,
    )


__all__ = [
    "VisualAffordanceProvider",
    "VisualAffordanceRequest",
    "VisualAffordanceResult",
    "VisualAffordanceTrace",
    "summarize_visual_affordances",
]
