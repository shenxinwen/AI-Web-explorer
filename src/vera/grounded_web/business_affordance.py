from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from vera.grounded_web.graph import BusinessAffordance
from vera.grounded_web.semantic_model import normalize_semantic_id

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
            "You are inspecting a screenshot of a web interface. Your task is to: "
            "(1) give the currently active interaction surface a short, stable "
            "location_id; (2) identify clear semantic actions available or visibly "
            "blocked on that surface; and (3) identify only indispensable direct "
            "dependencies between those actions. Use only information visible in "
            "the screenshot. Do not assume a hidden workflow, unseen context, or "
            "actions that may appear later.\n\n"
            "ACTIVE SURFACE\nInspect only the frontmost operable active interaction "
            "surface, such as the current page, dialog, drawer, modal, form, or "
            "result surface. If a modal or dialog covers the page, return actions "
            "from that surface. Covered background controls are not candidates.\n\n"
            "LOCATION\nReturn one location_id for the active surface in short "
            "snake_case. Name the visible "
            "kind of interaction surface, not its temporary content. Base it only "
            "on the visible surface, not action history, concrete objects, search "
            "terms, values, item counts, or item identities. Good names describe stable "
            "surfaces such as account_form or confirmation_dialog. Bad names encode "
            "temporary state such as page_after_login or cart_with_2_items.\n\n"
            "ACTION GRANULARITY\nEach action must describe one meaningful, directly "
            "executable operation a user can perform, not an individual mouse click "
            "or keyboard step. Group related fields that together complete one "
            "simple form section into one action when fine-grained or "
            "independent-field order is not important. Do not split each field into "
            "a separate action. Use a stable snake_case action_id, one precise "
            "description, and a visible target.\n\n"
            "REPRESENTATIVE ACTIONS\nBefore returning actions, group visible controls "
            "by semantic effect; grouping is mandatory. When the same "
            "operation appears on different instances of the same kind of object, "
            "return one action: the concrete object is an execution parameter, not "
            "a separate semantic action. The action must execute on exactly one "
            "instance. Use a singular target for that instance and do not enumerate "
            "similar instances with targets such as each, all, or every. When one "
            "function offers several selectable values within the same business "
            "dimension, return one action for that dimension, not one action per "
            "value. Keep distinct filter dimensions as distinct actions when they "
            "operate on different business attributes or parameter types, such as "
            "category, price, rating, or availability. A category value is an "
            "execution parameter of filter_by_category; it is not a new action. "
            "A different sort field or direction is likewise an execution parameter "
            "of one sorting action. Keep actions separate only when they have "
            "meaningfully different effects or serve different workflow roles. Do "
            "not use a vague umbrella action to merge different effects.\n\n"
            "EXECUTION POLICY\nFor every action, return an execution_policy. Use "
            "single_instance when the action should operate on exactly one matching "
            "object. Multiple similar controls are alternative targets, not required "
            "steps. Use composite when multiple distinct atomic steps are all required "
            "to complete one semantic operation, such as filling several related "
            "required fields. Do not use composite merely because multiple similar "
            "controls are visible. The execution_policy describes how the caller "
            "should execute the observed Stagehand actions.\n\n"
            "EXECUTION INSTANCE\nFor every action, freeze one concrete executable "
            "instance that is visible now. execution_instance must name the exact "
            "object, option, or value to use for this attempt, such as Select In "
            "Stock Only, Select Electronics, or Click Login button. It must be "
            "specific enough for an executor to act without choosing among controls. "
            "Choose an instance expected to cause an observable state change. "
            "Opening a menu, scrolling to a control, or focusing an input is not a "
            "completed business action.\n\n"
            "VISIBLE AND BLOCKED ACTIONS\nReturn an action when its target is clearly "
            "visible and usable, or clearly visible but blocked by another semantic "
            "action visible on the same surface. Do not return hidden or speculative "
            "actions; low-level interaction steps; static labels, totals, messages, "
            "or result text; completed operations as future actions; or controls "
            "whose meaning cannot be determined confidently. A successful or "
            "informational page may return an empty actions array when it contains "
            "no clear executable action.\n\n"
            "COMMON ICON-BASED ACTIONS\nOn a shopping, catalog, or product surface, "
            "a clearly visible shopping-cart icon may represent an action for "
            "opening or viewing the cart, even when the icon has no visible text "
            "label. When such a cart icon is visible, return one representative "
            "action such as open_cart or view_cart. A visible item-count badge is "
            "supporting evidence, but a badge is not required. Do not return "
            "separate actions for the cart icon and its badge.\n\n"
            "DEPENDENCIES\nRequires may reference only another action in this "
            "response. Add a dependency only when the required action is an "
            "indispensable direct prerequisite. Use requires=[] when an action can "
            "be performed independently. Do not treat visual order, recommended "
            "order, common website conventions, two independent filters, two "
            "independent form sections, an action that merely makes another action "
            "more useful, or an assumed business workflow as a dependency.\n\n"
            "RESULT SURFACES\nText describing success, completion, history, or a "
            "generated result is not an action. If a result surface contains a clear "
            "executable control, return only the operation represented by that "
            "control. Do not return the already completed operation.\n\n"
            "PRECISION\nPrefer precision over recall. It is acceptable to omit an "
            "uncertain action. It is not acceptable to invent an action, split one "
            "operation into concrete variants, or add an unsupported dependency. "
            f"The maximum action count is an upper bound: return at most {request.max_actions} "
            "actions. The limit is not a quota. Return fewer actions when fewer clear semantic "
            "operations are visible.\n\nEXPECTED OUTCOME\nFor every action, state one "
            "concise result that can be checked from the GUI after execution. The "
            "expected_outcome must describe an observable post-action result, not "
            "hidden backend state, and must be written before execution. Equivalent "
            "visible signs may be joined with or. Return JSON only."
        )
        output_schema: dict[str, Any] = {
            "location_id": "short stable snake_case active surface name",
            "actions": [
                {
                    "action_id": "stable_snake_case_action",
                    "description": "one precise visible semantic operation",
                    "target": "visible target",
                    "execution_instance": "one concrete executable instance",
                    "expected_outcome": "one concise observable post-action result",
                    "execution_policy": "single_instance | composite",
                    "requires": ["other_action_id"],
                }
            ]
        }
        few_shot_examples: list[dict[str, Any]] = [
            {
                "screen": "Create Project dialog with related required fields and a Create button.",
                "actions": [
                    {
                        "action_id": "complete_project_details",
                        "description": "Fill the related required project fields.",
                        "target": "Create Project dialog fields",
                        "execution_instance": "Fill the visible required project fields",
                        "expected_outcome": "The required project fields contain entered values.",
                        "execution_policy": "composite",
                        "requires": [],
                    },
                    {
                        "action_id": "create_project",
                        "description": "Submit the completed project form.",
                        "target": "Create button",
                        "execution_instance": "Click the Create button",
                        "expected_outcome": "A created-project confirmation or project surface becomes visible.",
                        "execution_policy": "single_instance",
                        "requires": ["complete_project_details"],
                    },
                ],
            },
            {
                "screen": "data-table toolbar with sort and column controls.",
                "actions": [
                    {
                        "action_id": "sort_table",
                        "description": "Sort the visible table.",
                        "target": "sort control",
                        "execution_instance": "Select one visible non-default sort order",
                        "expected_outcome": "The visible table rows appear in a different order.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                    {
                        "action_id": "configure_columns",
                        "description": "Choose visible table columns.",
                        "target": "column control",
                        "execution_instance": "Select one currently hidden table column",
                        "expected_outcome": "The selected table columns become visible.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                ],
            },
            {
                "screen": "Export Complete modal with a download control and dimmed background.",
                "actions": [
                    {
                        "action_id": "download_report",
                        "description": "Download the completed report.",
                        "target": "Download control in the modal",
                        "execution_instance": "Click the Download control",
                        "expected_outcome": "The interface shows that the report download was initiated.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    }
                ],
            },
            {
                "screen": "A list contains many records, each with an Open button.",
                "correct_actions": [
                    {
                        "action_id": "open_record",
                        "description": "Open one visible record.",
                        "target": "One record's Open button",
                        "execution_instance": "Click the Open button for one visible record",
                        "expected_outcome": "A stable record detail surface becomes visible.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    }
                ],
                "incorrect_actions": [
                    "open_record_a",
                    "open_record_b",
                    "open_record_c",
                ],
                "reason": (
                    "The record is an execution parameter; the semantic effect is "
                    "the same."
                ),
            },
            {
                "screen": (
                    "A shopping results page has filters for category, price, rating, "
                    "and availability, "
                    "plus several sort orders."
                ),
                "correct_actions": [
                    {
                        "action_id": "filter_by_category",
                        "description": "Filter products by category.",
                        "target": "Electronics category option",
                        "execution_instance": "Select the Electronics category",
                        "expected_outcome": "The selected category is shown and the visible products reflect it.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                    {
                        "action_id": "filter_by_price",
                        "description": "Filter products by price.",
                        "target": "Maximum price control",
                        "execution_instance": "Set the maximum price to a visible non-default value",
                        "expected_outcome": "The selected price limit is shown and the visible products reflect it.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                    {
                        "action_id": "filter_by_rating",
                        "description": "Filter products by rating.",
                        "target": "4 stars and above option",
                        "execution_instance": "Select 4 stars and above",
                        "expected_outcome": "The selected rating threshold is shown and the visible products reflect it.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                    {
                        "action_id": "sort_results",
                        "description": "Sort the visible results.",
                        "target": "Sort controls",
                        "execution_instance": "Select one visible non-default sort order",
                        "expected_outcome": "The visible results appear in the selected order.",
                        "execution_policy": "single_instance",
                        "requires": [],
                    },
                ],
                "incorrect_actions": [
                    "filter_category_electronics",
                    "filter_category_books",
                    "sort_newest",
                    "sort_oldest",
                ],
                "reason": (
                    "Different business attributes are separate filter dimensions, "
                    "while values within one dimension are execution parameters. "
                    "Sort orders remain values of one sorting function."
                ),
            },
        ]
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
                    "execution_instance": "one concrete executable instance",
                    "expected_outcome": "concise observable post-action result",
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
                            "execution_instance": "one concrete executable instance",
                            "expected_outcome": "concise observable post-action result",
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
    if scan_kind == "initial":
        payload["few_shot_examples"] = few_shot_examples
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


def _execution_policy(value: Any) -> str:
    policy = str(value or "single_instance").strip().lower()
    if policy in {"single_instance", "composite"}:
        return policy
    return "single_instance"


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
                execution_instance=_clean_text(item.get("execution_instance")),
                expected_outcome=_clean_text(item.get("expected_outcome")),
                execution_policy=_execution_policy(item.get("execution_policy")),
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
    if len(raw_items) > max_actions:
        return [], {}, "initial response exceeds the action limit"

    records: dict[str, tuple[str, str, str, str, str, list[str]]] = {}
    ordered_ids: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            return [], {}, "initial response action must be an object"
        base_keys = {
            "action_id", "description", "target", "execution_instance", "requires"
        }
        allowed_keys = base_keys | {"expected_outcome"}
        if set(item) not in (
            base_keys,
            base_keys | {"execution_policy"},
            allowed_keys,
            allowed_keys | {"execution_policy"},
        ):
            return [], {}, "initial action keys do not match the contract"
        raw_action_id = item["action_id"]
        raw_description = item["description"]
        raw_target = item["target"]
        raw_execution_instance = item["execution_instance"]
        raw_expected_outcome = item.get("expected_outcome", raw_description)
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                raw_action_id, raw_description, raw_target, raw_execution_instance,
                raw_expected_outcome
            )
        ):
            return [], {}, "initial action text fields must be non-empty strings"
        action_id = normalize_semantic_id(raw_action_id)
        description = raw_description.strip()
        target = raw_target.strip()
        execution_instance = raw_execution_instance.strip()
        expected_outcome = raw_expected_outcome.strip()
        if not action_id or not description or not target:
            return [], {}, "initial action requires action_id, description, and target"
        if action_id in records:
            return [], {}, f"duplicate initial action_id: {action_id}"
        execution_policy = _execution_policy(item.get("execution_policy"))
        if item.get("execution_policy") not in (None, "single_instance", "composite"):
            return [], {}, f"invalid execution_policy for {action_id}"
        raw_requires = item["requires"]
        if not isinstance(raw_requires, list):
            return [], {}, f"requires must be an array for {action_id}"
        requires: list[str] = []
        for value in raw_requires:
            if not isinstance(value, str) or not value.strip():
                return [], {}, f"requires entries must be non-empty strings for {action_id}"
            requirement = normalize_semantic_id(value)
            if not requirement:
                return [], {}, f"requires entries must be valid IDs for {action_id}"
            if requirement not in requires:
                requires.append(requirement)
        records[action_id] = (
            description, target, execution_instance, expected_outcome,
            execution_policy, requires
        )
        ordered_ids.append(action_id)

    requires_by_action_id = {
        action_id: list(records[action_id][5]) for action_id in ordered_ids
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
            execution_instance=records[action_id][2],
            expected_outcome=records[action_id][3],
            execution_policy=records[action_id][4],
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
        if set(parsed) not in ({"actions"}, {"location_id", "actions"}) or not isinstance(
            parsed.get("actions"), list
        ):
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
