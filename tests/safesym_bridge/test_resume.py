from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.resume import (
    ActionAttemptKey,
    ResumePolicy,
    derive_resume_cursor,
    is_action_eligible,
    select_resume_frontier,
)


def _graph_with_events(statuses, *, inflight=None):
    node = WebKobeNode(
        node_id="source",
        page_description="source",
        page_frame=PageFrame(
            page_id="source",
            page_type="source",
            url="https://fixture.test/",
            url_pattern="https://fixture.test/",
            title="source",
        ),
        state_schema={},
        last_state_snapshot={},
    )
    events = [
        WebKobeEdge(
            source_node_id="source",
            target_node_id="source",
            instruction="retry me",
            action=BrowserAction("click", "#retry", "retry_me"),
            capability=None,
            target_observation="source",
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click", "#retry", "retry_me", {}, "source", "source", status != "failed_execution"
            ),
            status=status,
        )
        for status in statuses
    ]
    return WebKobeGraph(
        app="fixture",
        start_node_id="source",
        total_steps_completed=len(events),
        nodes=[node],
        edges=events[-1:] if events else [],
        execution_events=events,
        meta=(
            {"inflight_action": {"attempt_id": "inflight", "source_node_id": "source", "action_id": "retry_me"}}
            if inflight
            else {}
        ),
    )


@pytest.mark.parametrize(
    ("events", "inflight", "authorized", "expected"),
    [
        ([], None, False, True),
        (["failed_execution"], None, False, False),
        (["failed_execution"], None, True, True),
        (["failed_execution", "failed_execution"], None, True, False),
        (["succeeded_with_observed_change"], None, True, False),
        (["no_observed_change"], None, True, False),
        ([], "matching", False, False),
        ([], "matching", True, True),
    ],
)
def test_resume_action_eligibility(events, inflight, authorized, expected):
    graph = _graph_with_events(events, inflight=inflight)
    policy = ResumePolicy(
        retry_keys=(
            frozenset({ActionAttemptKey("source", "retry_me")})
            if authorized
            else frozenset()
        ),
        max_attempts=2,
    )
    assert (
        is_action_eligible(
            graph,
            source_node_id="source",
            action_id="retry_me",
            policy=policy,
        )
        is expected
    )


def test_resume_cursor_prefers_explicit_meta_and_selects_reachable_cursor():
    start = _graph_with_events([])
    target = WebKobeNode(
        node_id="target",
        page_description="target",
        page_frame=start.nodes[0].page_frame,
        state_schema={},
        last_state_snapshot={},
        business_affordances=[],
    )
    start.nodes[0] = replace(start.nodes[0], business_affordances=[])
    start.nodes.append(target)
    start.meta["resume_cursor_node_id"] = "target"
    assert derive_resume_cursor(start) == "target"
    assert select_resume_frontier(start, policy=ResumePolicy()) is None
