from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot


@dataclass(frozen=True)
class ActionExpectation:
    kind: str
    field: str | None = None
    expected_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "field": self.field,
            "expected_value": self.expected_value,
        }


@dataclass(frozen=True)
class ActionIntent:
    action_kind: str
    target_semantic_id: str | None = None
    target_description: str | None = None
    input_values: dict[str, str] = field(default_factory=dict)
    expectation: ActionExpectation | None = None
    source: str = "rule_based"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_kind": self.action_kind,
            "target_semantic_id": self.target_semantic_id,
            "target_description": self.target_description,
            "input_values": dict(self.input_values),
            "expectation": (
                self.expectation.to_dict() if self.expectation is not None else None
            ),
            "source": self.source,
        }


@dataclass(frozen=True)
class OutcomeEvaluation:
    status: str
    reason: str
    matched_expectation: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "matched_expectation": self.matched_expectation,
        }


@dataclass(frozen=True)
class ActionExecutionResult:
    intent: ActionIntent
    action: BrowserAction | None
    before: StateSnapshot
    after: StateSnapshot | None
    observed_delta: list[ObservedDelta]
    execution_success: bool
    execution_error: str | None
    outcome: OutcomeEvaluation

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "action": self.action.to_dict() if self.action is not None else None,
            "before": {
                "page_id": self.before.page_id,
                "url": self.before.url,
                "title": self.before.title,
                "signature": dict(self.before.signature),
            },
            "after": (
                {
                    "page_id": self.after.page_id,
                    "url": self.after.url,
                    "title": self.after.title,
                    "signature": dict(self.after.signature),
                }
                if self.after is not None
                else None
            ),
            "observed_delta": [delta.to_dict() for delta in self.observed_delta],
            "execution_success": self.execution_success,
            "execution_error": self.execution_error,
            "outcome": self.outcome.to_dict(),
        }


def browser_action_from_record(action: BrowserAction | dict[str, Any]) -> BrowserAction:
    if isinstance(action, BrowserAction):
        return action
    return BrowserAction(
        action_kind=str(action.get("action_kind") or ""),
        locator=action.get("locator"),
        semantic_id=str(action.get("semantic_id") or ""),
        input_values=dict(action.get("input_values") or {}),
        description=action.get("description"),
    )


def _with_intent_inputs(action: BrowserAction, intent: ActionIntent) -> BrowserAction:
    if action.action_kind != intent.action_kind:
        action = replace(action, action_kind=intent.action_kind)
    if not intent.input_values:
        return action
    return replace(action, input_values=dict(intent.input_values))


def _action_kind_matches(intent_kind: str, action_kind: str) -> bool:
    if intent_kind == action_kind:
        return True
    return intent_kind == "fill_then_click" and action_kind == "click"


def resolve_action_intent(
    intent: ActionIntent,
    available_actions: list[BrowserAction | dict[str, Any]],
) -> BrowserAction | None:
    normalized = [browser_action_from_record(action) for action in available_actions]
    if intent.target_semantic_id is not None:
        for action in normalized:
            if (
                action.semantic_id == intent.target_semantic_id
                and _action_kind_matches(intent.action_kind, action.action_kind)
            ):
                return _with_intent_inputs(action, intent)

    description = (intent.target_description or "").strip().lower()
    if description:
        for action in normalized:
            action_description = (action.description or "").strip().lower()
            if (
                _action_kind_matches(intent.action_kind, action.action_kind)
                and description in action_description
            ):
                return _with_intent_inputs(action, intent)

    return None


def _expectation_matches(
    expectation: ActionExpectation,
    deltas: list[ObservedDelta],
) -> bool:
    if expectation.kind == "any_state_change":
        return bool(deltas)
    if expectation.kind == "field_changed":
        return any(delta.field == expectation.field for delta in deltas)
    if expectation.kind == "field_equals":
        return any(
            delta.field == expectation.field and delta.after == expectation.expected_value
            for delta in deltas
        )
    return False


def evaluate_outcome(
    *,
    execution_success: bool,
    execution_error: str | None,
    deltas: list[ObservedDelta],
    expectation: ActionExpectation | None,
) -> OutcomeEvaluation:
    if not execution_success:
        return OutcomeEvaluation(
            status="failed_execution",
            reason=execution_error or "adapter execution returned false",
            matched_expectation=False,
        )

    if not deltas:
        return OutcomeEvaluation(
            status="no_observed_change",
            reason="execution succeeded but no state delta was observed",
            matched_expectation=None if expectation is None else False,
        )

    if expectation is None:
        return OutcomeEvaluation(
            status="succeeded_with_observed_change",
            reason="execution succeeded and state changed",
            matched_expectation=None,
        )

    if _expectation_matches(expectation, deltas):
        return OutcomeEvaluation(
            status="succeeded",
            reason=f"expectation matched: {expectation.kind}",
            matched_expectation=True,
        )

    return OutcomeEvaluation(
        status="unexpected_change",
        reason=f"expectation did not match: {expectation.kind}",
        matched_expectation=False,
    )
