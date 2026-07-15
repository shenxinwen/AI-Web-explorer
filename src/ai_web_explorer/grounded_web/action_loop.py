from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.action_intent import (
    ActionExecutionResult,
    ActionIntent,
    OutcomeEvaluation,
    evaluate_outcome,
    resolve_action_intent,
)
from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.capability_graph import Evidence, ObservedDelta
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_signature import schema_delta
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)


def _schema_observed_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    evidence = [Evidence(source="grounded_action_loop_schema_diff", url=url)]
    deltas: list[ObservedDelta] = []
    for key, value in (schema_delta(before, after) or {}).items():
        deltas.append(
            ObservedDelta(
                field=key,
                before=value["before"],
                after=value["after"],
                delta_type="state_indicator_change",
                evidence=evidence,
            )
        )
    return deltas


def observed_delta_from_adapter(
    adapter: AutomationBackend,
    *,
    before_facts,
    after_facts,
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    if before_facts is not None and after_facts is not None:
        typed = typed_deltas_from_facts(before_facts, after_facts)
        return observed_deltas_from_typed(typed, url=url)
    return _schema_observed_delta(before_signature, after_signature, url)


def failed_action_result(
    *,
    intent: ActionIntent,
    before: StateSnapshot,
    action: BrowserAction | None,
    error: str,
) -> ActionExecutionResult:
    outcome = OutcomeEvaluation(
        status="failed_execution",
        reason=error,
        matched_expectation=False,
    )
    return ActionExecutionResult(
        intent=intent,
        action=action,
        before=before,
        after=None,
        observed_delta=[],
        execution_success=False,
        execution_error=error,
        outcome=outcome,
    )


async def execute_action_intent(
    adapter: AutomationBackend,
    intent: ActionIntent,
    *,
    before: StateSnapshot | None = None,
    available_actions: list[BrowserAction | dict[str, Any]] | None = None,
) -> ActionExecutionResult:
    before_state = before if before is not None else await adapter.observe_state()
    before_facts = getattr(adapter, "last_state_facts", None)
    actions = (
        available_actions
        if available_actions is not None
        else await adapter.list_interactables(before_state)
    )
    action = resolve_action_intent(intent, actions)
    if action is None:
        return failed_action_result(
            intent=intent,
            before=before_state,
            action=None,
            error="intent_target_not_found",
        )

    success = await adapter.execute(action)
    execution_error = getattr(adapter, "last_execution_error", None)
    after_state = await adapter.observe_state()
    after_facts = getattr(adapter, "last_state_facts", None)
    deltas = observed_delta_from_adapter(
        adapter,
        before_facts=before_facts,
        after_facts=after_facts,
        before_signature=before_state.signature,
        after_signature=after_state.signature,
        url=after_state.url,
    )
    outcome = evaluate_outcome(
        execution_success=success,
        execution_error=execution_error,
        deltas=deltas,
        expectation=intent.expectation,
    )
    return ActionExecutionResult(
        intent=intent,
        action=action,
        before=before_state,
        after=after_state,
        observed_delta=deltas,
        execution_success=success,
        execution_error=execution_error,
        outcome=outcome,
    )
