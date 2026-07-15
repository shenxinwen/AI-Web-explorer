import pytest

from ai_web_explorer.grounded_web.action_intent import (
    ActionExpectation,
    ActionIntent,
)
from ai_web_explorer.grounded_web.action_loop import execute_action_intent
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


@pytest.fixture
def anyio_backend():
    return "asyncio"


class LoopFakeAdapter:
    app_name = "fake"

    def __init__(self, *, fail_error: str | None = None, no_change: bool = False):
        self.executed = []
        self.last_execution_error = None
        self.fail_error = fail_error
        self.no_change = no_change
        self.fact_sets = [
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=0,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=3,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
        ]

    async def observe_state(self):
        index = min(len(self.executed), 1)
        if self.no_change:
            index = 0
        self.last_state_facts = self.fact_sets[index]
        return StateSnapshot(
            page_id="search",
            url="https://example.test/search",
            title="Search",
            signature={"result_count": self.fact_sets[index][0].value},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "submit_search",
                "description": "Search",
                "locator": "#submit",
                "action_kind": "click",
                "input_values": {},
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        if self.fail_error is not None:
            self.last_execution_error = self.fail_error
            return False
        return True


@pytest.mark.anyio
async def test_execute_action_intent_returns_typed_delta_and_success():
    adapter = LoopFakeAdapter()
    result = await execute_action_intent(
        adapter,
        ActionIntent(
            action_kind="click",
            target_semantic_id="submit_search",
            expectation=ActionExpectation(
                kind="field_changed",
                field="result_count",
            ),
        ),
    )

    assert result.execution_success is True
    assert result.action is not None
    assert result.action.semantic_id == "submit_search"
    assert result.observed_delta[0].field == "result_count"
    assert result.observed_delta[0].delta_type == "numeric_changed"
    assert result.outcome.status == "succeeded"


@pytest.mark.anyio
async def test_execute_action_intent_reports_missing_target():
    adapter = LoopFakeAdapter()
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="missing"),
    )

    assert result.execution_success is False
    assert result.execution_error == "intent_target_not_found"
    assert result.action is None
    assert result.after is None
    assert result.outcome.status == "failed_execution"


@pytest.mark.anyio
async def test_execute_action_intent_reports_backend_failure():
    adapter = LoopFakeAdapter(fail_error="locator_disabled")
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
    )

    assert result.execution_success is False
    assert result.execution_error == "locator_disabled"
    assert result.outcome.status == "failed_execution"


@pytest.mark.anyio
async def test_execute_action_intent_reports_no_observed_change():
    adapter = LoopFakeAdapter(no_change=True)
    result = await execute_action_intent(
        adapter,
        ActionIntent(action_kind="click", target_semantic_id="submit_search"),
    )

    assert result.execution_success is True
    assert result.observed_delta == []
    assert result.outcome.status == "no_observed_change"
