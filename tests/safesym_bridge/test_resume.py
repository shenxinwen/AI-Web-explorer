from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
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


def _resume_node(node_id, actions=()):
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url="https://fixture.test/",
            url_pattern="https://fixture.test/",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance(action) for action in actions],
    )


def _resume_edge(source, target, action, *, status="succeeded_with_navigation", success=True):
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action,
        action=BrowserAction("click", f"#{action}", action),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click", f"#{action}", action, {}, source, target, success
        ),
        status=status,
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


def test_resume_cursor_prefers_authorized_failed_action_over_earlier_sibling_path():
    nodes = [
        _resume_node("start"),
        _resume_node("retry_source", ["retry_me"]),
        _resume_node("sibling", ["ordinary"]),
    ]
    path_to_retry = _resume_edge("start", "retry_source", "z_path")
    path_to_sibling = _resume_edge("start", "sibling", "a_path")
    failed_retry = _resume_edge(
        "retry_source",
        "retry_source",
        "retry_me",
        status="failed_execution",
        success=False,
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=nodes,
        edges=[path_to_retry, path_to_sibling, failed_retry],
        execution_events=[path_to_retry, path_to_sibling, failed_retry],
        meta={"resume_cursor_node_id": "retry_source"},
    )
    policy = ResumePolicy(
        retry_keys=frozenset({ActionAttemptKey("retry_source", "retry_me")})
    )

    target = select_resume_frontier(graph, policy=policy)

    assert target is not None
    assert target.node_id == "retry_source"
    assert target.untried_action_ids == ("retry_me",)


def test_resume_prefers_most_recent_authorized_retry_source_before_normal_frontier():
    nodes = [
        _resume_node("start"),
        _resume_node("cursor"),
        _resume_node("older_retry", ["retry_old"]),
        _resume_node("newer_retry", ["retry_new"]),
        _resume_node("ordinary", ["ordinary"]),
    ]
    stable_edges = [
        _resume_edge("start", "cursor", "cursor_path"),
        _resume_edge("start", "ordinary", "ordinary_path"),
        _resume_edge("start", "older_retry", "older_path"),
        _resume_edge("start", "newer_retry", "newer_path"),
    ]
    failed_old = _resume_edge(
        "older_retry", "older_retry", "retry_old", status="failed_execution", success=False
    )
    failed_new = _resume_edge(
        "newer_retry", "newer_retry", "retry_new", status="failed_execution", success=False
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=6,
        nodes=nodes,
        edges=stable_edges + [failed_old, failed_new],
        execution_events=stable_edges + [failed_old, failed_new],
        meta={"resume_cursor_node_id": "cursor"},
    )
    policy = ResumePolicy(
        retry_keys=frozenset(
            {
                ActionAttemptKey("older_retry", "retry_old"),
                ActionAttemptKey("newer_retry", "retry_new"),
            }
        )
    )

    target = select_resume_frontier(graph, policy=policy)

    assert target is not None
    assert target.node_id == "newer_retry"
    assert target.untried_action_ids == ("retry_new",)


def test_resume_keeps_older_eligible_action_when_newer_same_source_is_exhausted():
    nodes = [
        _resume_node("start"),
        _resume_node("retry_source", ["retry_old", "retry_new"]),
        _resume_node("sibling", ["ordinary"]),
    ]
    sibling_path = _resume_edge("start", "sibling", "a_sibling_path")
    retry_path = _resume_edge("start", "retry_source", "z_retry_path")
    failed_old = _resume_edge(
        "retry_source", "retry_source", "retry_old",
        status="failed_execution", success=False,
    )
    failed_new_1 = _resume_edge(
        "retry_source", "retry_source", "retry_new",
        status="failed_execution", success=False,
    )
    failed_new_2 = _resume_edge(
        "retry_source", "retry_source", "retry_new",
        status="failed_execution", success=False,
    )
    events = [sibling_path, retry_path, failed_old, failed_new_1, failed_new_2]
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=len(events),
        nodes=nodes,
        edges=events,
        execution_events=events,
        meta={"resume_cursor_node_id": "start"},
    )
    policy = ResumePolicy(
        retry_keys=frozenset(
            {
                ActionAttemptKey("retry_source", "retry_old"),
                ActionAttemptKey("retry_source", "retry_new"),
            }
        ),
        max_attempts=2,
    )

    target = select_resume_frontier(graph, policy=policy)

    assert target is not None
    assert target.node_id == "retry_source"
    assert "retry_old" in target.untried_action_ids
    assert target.node_id != "sibling"
