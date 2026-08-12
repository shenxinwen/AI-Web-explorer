from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
)
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.semantic_model import (
    SemanticObservation,
    normalize_semantic_id,
    semantic_observation_from_dict,
)

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
    source_location_hint: str | None = None
    source_location_hint_confirmed: bool = True
    allowed_location_ids: list[str] = field(default_factory=list)
    current_location_context: str | None = None


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
    semantic_observation: SemanticObservation | None = None


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
            "none (no visible change), presentation (ordering, filtering, "
            "pagination, or view mode of the current content; no new action "
            "surface and no change to known planning boundaries), "
            "state_indicator (a visible indicator of an existing state), "
            "surface (a visible page or component surface changed), mixed "
            "(more than one kind), or unknown (insufficient visual basis). This "
            "classification is observation metadata only, not planning authority."
            " Use the same coarse location when only sorting, filtering, searching, "
            "pagination, counts, selections, or styling changed. A modal, drawer, "
            "or workspace may be a new location when it becomes the active business "
            "surface. Do not infer hidden state. Do not copy every visible fact into "
            "candidate_required_facts. The action_role must be exactly one of "
            "the following: presentation_capability (visible sorting, filtering, "
            "searching, pagination, or view-mode completion at the current "
            "surface), state_mutation (visible change to business/application "
            "state), navigation (movement to another visible surface without a "
            "guarded business prerequisite), guarded_navigation (navigation that "
            "requires a verified business fact), form_completion (visible "
            "completion of a required form), commit (a visible commit boundary "
            "such as final submission), unknown (insufficient evidence). Use "
            "source_location as the stable anchor supplied below. For ordinary "
            "sorting, filtering, searching, pagination, counts, selections, or "
            "styling, source_location and target_location must remain that same "
            "anchor. Only an active business surface change may introduce a new "
            "target_location. Do not invent a new location on every step."
        ),
        "action": action,
        "location_context": {
            "source_location_hint": request.source_location_hint,
            "source_location_hint_confirmed": request.source_location_hint_confirmed,
            "allowed_location_ids": list(request.allowed_location_ids),
            "current_location_context": request.current_location_context,
        },
        "required_json_fields": [
            "candidate_added_facts",
            "candidate_removed_facts",
            "visual_change_kind",
            "action_role",
            "source_location",
            "target_location",
            "completion_facts",
            "candidate_required_facts",
            "preserved_facts",
            "semantic_evidence",
            "semantic_confidence",
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


def _semantic_observation(
    parsed: dict[str, Any], request: VisualDeltaRequest
) -> SemanticObservation | None:
    observation = semantic_observation_from_dict(parsed)
    if observation is None:
        return None
    if (
        observation.action_role == "unknown"
        or not observation.source_location
        or not observation.target_location
    ):
        return None
    if request.source_location_hint and request.source_location_hint_confirmed:
        source_hint = normalize_semantic_id(request.source_location_hint)
        if observation.source_location != source_hint:
            return None
        if (
            observation.action_role == "presentation_capability"
            and observation.target_location != source_hint
        ):
            return None
    if observation.action_role != "presentation_capability":
        observation = SemanticObservation(
            action_role=observation.action_role,
            source_location=observation.source_location,
            target_location=observation.target_location,
            completion_facts=[],
            candidate_required_facts=observation.candidate_required_facts,
            preserved_facts=observation.preserved_facts,
            evidence=observation.evidence,
            confidence=observation.confidence,
        )
    return observation


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
        semantic_observation=_semantic_observation(parsed, request),
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
