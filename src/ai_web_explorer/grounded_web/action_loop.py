from __future__ import annotations

import asyncio
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ObservationWaitPolicy:
    timeout_ms: int = 1200
    interval_ms: int = 200


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


@dataclass(frozen=True)
class _ObservedStateDelta:
    state: StateSnapshot
    facts: Any
    deltas: list[ObservedDelta]


async def _observe_state_delta(
    adapter: AutomationBackend,
    *,
    before_facts,
    before_signature: dict[str, Any],
) -> _ObservedStateDelta:
    state = await adapter.observe_state()
    facts = getattr(adapter, "last_state_facts", None)
    deltas = observed_delta_from_adapter(
        adapter,
        before_facts=before_facts,
        after_facts=facts,
        before_signature=before_signature,
        after_signature=state.signature,
        url=state.url,
    )
    return _ObservedStateDelta(state=state, facts=facts, deltas=deltas)


async def _wait_for_observed_delta(
    adapter: AutomationBackend,
    *,
    before_facts,
    before_signature: dict[str, Any],
    initial: _ObservedStateDelta,
    policy: ObservationWaitPolicy,
) -> _ObservedStateDelta:
    if initial.deltas:
        return initial
    timeout_s = max(policy.timeout_ms, 0) / 1000
    interval_s = max(policy.interval_ms, 1) / 1000
    if timeout_s <= 0:
        return initial

    deadline = asyncio.get_running_loop().time() + timeout_s
    current = initial
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return current
        await asyncio.sleep(min(interval_s, remaining))
        current = await _observe_state_delta(
            adapter,
            before_facts=before_facts,
            before_signature=before_signature,
        )
        if current.deltas:
            return current


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
    wait_policy: ObservationWaitPolicy | None = None,
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
    policy = wait_policy or ObservationWaitPolicy()
    observed = await _observe_state_delta(
        adapter,
        before_facts=before_facts,
        before_signature=before_state.signature,
    )
    if success and not observed.deltas:
        observed = await _wait_for_observed_delta(
            adapter,
            before_facts=before_facts,
            before_signature=before_state.signature,
            initial=observed,
            policy=policy,
        )
    after_state = observed.state
    deltas = observed.deltas
    outcome = evaluate_outcome(
        execution_success=success,
        execution_error=execution_error,
        deltas=deltas,
        expectation=intent.expectation,
    )
    if success and not deltas and outcome.status == "no_observed_change":
        outcome = OutcomeEvaluation(
            status=outcome.status,
            reason=(
                "execution succeeded but no state delta was observed "
                f"after {policy.timeout_ms}ms"
            ),
            matched_expectation=outcome.matched_expectation,
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
