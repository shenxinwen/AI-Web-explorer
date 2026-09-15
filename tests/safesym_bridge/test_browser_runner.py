import json
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from ai_web_explorer.safesym_bridge import browser_runner
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.graph import BusinessAffordance
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.graph import ReferenceObservation
from ai_web_explorer.grounded_web.graph import WebKobeEdge
from ai_web_explorer.grounded_web.graph import WebKobeNode
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_embedding import StateEmbeddingRecord
from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits
from ai_web_explorer.grounded_web.resume import ResumePolicy


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_run_stagehand_exploration_removes_semantic_experiment_profile_argument():
    assert (
        "semantic_experiment_profile"
        not in inspect.signature(browser_runner.run_stagehand_exploration).parameters
    )


def test_browser_runner_default_adapter_is_generic_grounded_web_adapter():
    assert (
        browser_runner.WebKobePlaywrightAdapter.__module__
        == "ai_web_explorer.grounded_web.playwright_backend"
    )


def test_write_web_kobe_graph_adds_frontier_metrics(tmp_path):
    output_path = tmp_path / "graph.json"
    graph = WebKobeGraph(
        app="demo",
        start_node_id="product_list",
        total_steps_completed=2,
        nodes=[
            WebKobeNode(
                node_id="product_list",
                page_description="Product list",
                page_frame=PageFrame(
                    page_id="demo:product_list",
                    page_type="product_list",
                    url="https://example.test/shop",
                    url_pattern="https://example.test/shop",
                    title="Shop",
                ),
                state_schema={},
                last_state_snapshot={},
                business_affordances=[
                    BusinessAffordance(action_name="view_product_details"),
                    BusinessAffordance(action_name="open_cart"),
                    BusinessAffordance(action_name="sort_products"),
                ],
            ),
            WebKobeNode(
                node_id="cart",
                page_description="Cart",
                page_frame=PageFrame(
                    page_id="demo:cart",
                    page_type="cart",
                    url="https://example.test/cart",
                    url_pattern="https://example.test/cart",
                    title="Cart",
                ),
                state_schema={},
                last_state_snapshot={},
                business_affordances=[
                    BusinessAffordance(action_name="checkout"),
                ],
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="product_list",
                target_node_id="product_list",
                instruction="view details",
                action=BrowserAction(
                    action_kind="business_intent",
                    locator=None,
                    semantic_id="view_product_details",
                    canonical_action_name="view_product_details",
                ),
                capability=None,
                target_observation="Product details modal",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "view_product_details",
                    {},
                    "product_list",
                    "product_list",
                    True,
                ),
                status="succeeded_with_observed_change",
            ),
            WebKobeEdge(
                source_node_id="product_list",
                target_node_id="product_list",
                instruction="sort",
                action=BrowserAction(
                    action_kind="business_intent",
                    locator=None,
                    semantic_id="sort_products",
                    canonical_action_name="sort_products",
                ),
                capability=None,
                target_observation="Product list",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "sort_products",
                    {},
                    "product_list",
                    "product_list",
                    True,
                ),
                status="no_observed_change",
            ),
        ],
    )

    browser_runner.write_web_kobe_graph(graph, output_path)

    evidence_path = output_path.with_name("graph_evidence.json")
    assert output_path.exists()
    assert evidence_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    metrics = data["meta"]["frontier_metrics"]
    assert evidence["schema_version"] == "web-kobe-graph-evidence-v1"
    assert metrics["frontier_node_count"] == 2
    assert metrics["exhausted_node_count"] == 0
    assert metrics["repeated_target_hit_count"] == 2
    assert metrics["backtrack_count"] == 0
    product_list = metrics["nodes"]["product_list"]
    assert product_list["candidate_count"] == 3
    assert product_list["tried_action_ids"] == [
        "view_product_details",
        "sort_products",
    ]
    assert product_list["untried_action_ids"] == ["open_cart"]
    assert product_list["no_op_action_ids"] == ["sort_products"]
    assert product_list["failed_action_ids"] == []


def test_stagehand_checkpoint_writes_embedding_trace_then_graph(tmp_path, monkeypatch):
    graph = _transactional_graph("stagehand_action")
    graph.edges[0].execution_trace.metadata["action_source"] = "stagehand"
    calls = []
    embedding_path = tmp_path / "state_embeddings.json"
    trace_path = tmp_path / "stagehand_trace.json"
    output_path = tmp_path / "graph.json"

    monkeypatch.setattr(
        browser_runner,
        "write_state_embedding_records",
        lambda path, records: calls.append("embedding") or path,
    )
    monkeypatch.setattr(
        browser_runner,
        "_write_text_atomically",
        lambda path, text: calls.append("trace") or path,
    )
    monkeypatch.setattr(
        browser_runner,
        "write_web_kobe_graph",
        lambda graph, path: calls.append("graph") or path,
    )

    result = browser_runner._write_stagehand_checkpoint(
        graph,
        output_path=output_path,
        embedding_path=embedding_path,
        embedding_records=[StateEmbeddingRecord("source", "source", [1.0, 0.0])],
        stagehand_trace_path=trace_path,
    )

    assert result == output_path
    assert calls == ["embedding", "trace", "graph"]


def test_stagehand_checkpoint_trace_uses_ordered_execution_events(
    tmp_path, monkeypatch
):
    graph = _transactional_graph("duplicate_action")
    failed = replace(
        graph.edges[0],
        status="failed_execution",
        execution_trace=replace(
            graph.edges[0].execution_trace,
            success=False,
            error="failed",
            metadata={"action_source": "stagehand", "attempt_id": "a1"},
        ),
    )
    succeeded = replace(
        graph.edges[0],
        execution_trace=replace(
            graph.edges[0].execution_trace,
            metadata={"action_source": "stagehand", "attempt_id": "a2"},
        ),
    )
    graph = replace(graph, edges=[succeeded], execution_events=[failed, succeeded])
    captured = []
    monkeypatch.setattr(
        browser_runner,
        "_write_text_atomically",
        lambda path, text: captured.append(json.loads(text)) or path,
    )
    monkeypatch.setattr(
        browser_runner,
        "write_web_kobe_graph",
        lambda graph, path: path,
    )

    browser_runner._write_stagehand_checkpoint(
        graph,
        output_path=tmp_path / "graph.json",
        embedding_path=None,
        embedding_records=[],
        stagehand_trace_path=tmp_path / "trace.json",
    )

    assert [item["attempt_id"] for item in captured[0]] == ["a1", "a2"]


def test_stagehand_checkpoint_writes_graph_without_optional_artifacts(
    tmp_path, monkeypatch
):
    calls = []
    output_path = tmp_path / "graph.json"
    monkeypatch.setattr(
        browser_runner,
        "write_web_kobe_graph",
        lambda graph, path: calls.append("graph") or path,
    )

    result = browser_runner._write_stagehand_checkpoint(
        browser_runner.build_debug_web_kobe_graph(),
        output_path=output_path,
        embedding_path=None,
        embedding_records=[],
        stagehand_trace_path=None,
    )

    assert result == output_path
    assert calls == ["graph"]


def test_write_web_kobe_graph_does_not_write_graph_if_sidecar_fails(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "graph.json"
    evidence_path = tmp_path / "graph_evidence.json"
    original_write_temp = browser_runner._write_json_temp

    def fail_sidecar(path, data):
        if path == evidence_path:
            raise OSError("sidecar write failed")
        return original_write_temp(path, data)

    monkeypatch.setattr(browser_runner, "_write_json_temp", fail_sidecar)

    with pytest.raises(OSError, match="sidecar write failed"):
        browser_runner.write_web_kobe_graph(
            browser_runner.build_debug_web_kobe_graph(), output_path
        )

    assert not output_path.exists()


def _transactional_graph(action_name: str) -> WebKobeGraph:
    evidence = Evidence(
        source="transactional-test",
        selector="#action",
        text_sample=f"{action_name} control",
        url="https://example.test/shop",
    )
    source = WebKobeNode(
        node_id="source",
        page_description="Source page",
        page_frame=PageFrame(
            page_id="example:source",
            page_type="source",
            url="https://example.test/shop",
            url_pattern="https://example.test/shop",
            title="Shop",
            evidence=[evidence],
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance(action_name=action_name)],
        evidence=[evidence],
    )
    target = WebKobeNode(
        node_id="target",
        page_description="Target page",
        page_frame=PageFrame(
            page_id="example:target",
            page_type="target",
            url="https://example.test/target",
            url_pattern="https://example.test/target",
            title="Target",
        ),
        state_schema={},
        last_state_snapshot={},
    )
    edge = WebKobeEdge(
        source_node_id="source",
        target_node_id="target",
        instruction=f"Execute {action_name}",
        action=BrowserAction(
            action_kind="business_intent",
            locator="#action",
            semantic_id=action_name,
            canonical_action_name=action_name,
        ),
        capability=None,
        target_observation="Target page",
        observed_delta=[
            ObservedDelta(
                field=f"{action_name}_visible",
                before=False,
                after=True,
                delta_type="added",
                evidence=[evidence],
            )
        ],
        schema_delta={"action": {"before": False, "after": True}},
        execution_trace=ExecutionTrace(
            "business_intent",
            "#action",
            action_name,
            {},
            "source",
            "target",
            True,
            metadata={
                "visual_delta_trace": {
                    "candidate_added_facts": [f"{action_name}_visible"],
                    "candidate_removed_facts": [],
                }
            },
        ),
        status="succeeded_with_observed_change",
        evidence=[evidence],
    )
    return WebKobeGraph(
        app="transactional-test",
        start_node_id="source",
        total_steps_completed=1,
        nodes=[source, target],
        edges=[edge],
    )


def _assert_graph_evidence_refs_resolve(graph_path: Path, evidence_path: Path):
    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    for item_type in ("nodes", "edges"):
        for item in graph_data[item_type]:
            if "evidence_ref" in item:
                assert item["evidence_ref"] in evidence_data[item_type]


def test_write_web_kobe_graph_first_graph_commit_failure_leaves_no_artifacts(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "graph.json"
    evidence_path = tmp_path / "graph_evidence.json"
    original_replace = Path.replace

    def fail_graph_replace(path, target):
        if Path(target) == output_path:
            raise OSError("graph commit failed")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_graph_replace)

    with pytest.raises(OSError, match="graph commit failed"):
        browser_runner.write_web_kobe_graph(
            _transactional_graph("action_a"), output_path
        )

    assert not output_path.exists()
    assert not evidence_path.exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_write_web_kobe_graph_failed_overwrite_preserves_old_pair(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "graph.json"
    evidence_path = tmp_path / "graph_evidence.json"
    browser_runner.write_web_kobe_graph(_transactional_graph("action_a"), output_path)
    old_graph = output_path.read_bytes()
    old_evidence = evidence_path.read_bytes()
    _assert_graph_evidence_refs_resolve(output_path, evidence_path)

    original_replace = Path.replace

    def fail_graph_replace(path, target):
        if Path(target) == output_path:
            raise OSError("graph overwrite failed")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_graph_replace)

    with pytest.raises(OSError, match="graph overwrite failed"):
        browser_runner.write_web_kobe_graph(
            _transactional_graph("action_b"), output_path
        )

    assert output_path.read_bytes() == old_graph
    assert evidence_path.read_bytes() == old_evidence
    _assert_graph_evidence_refs_resolve(output_path, evidence_path)
    assert list(tmp_path.glob(".*.tmp")) == []


def test_write_web_kobe_graph_retries_transient_permission_error(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "graph.json"
    original_replace = Path.replace
    graph_replace_attempts = 0

    def transient_graph_replace(path, target):
        nonlocal graph_replace_attempts
        if Path(target) == output_path:
            graph_replace_attempts += 1
            if graph_replace_attempts == 1:
                raise PermissionError("graph temporarily locked")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", transient_graph_replace)
    monkeypatch.setattr(browser_runner.time, "sleep", lambda _seconds: None)

    browser_runner.write_web_kobe_graph(
        _transactional_graph("action_a"), output_path
    )

    assert graph_replace_attempts == 2
    assert output_path.exists()
    assert (tmp_path / "graph_evidence.json").exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_write_text_atomically_retries_transient_permission_error(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "stagehand_trace.json"
    original_replace = Path.replace
    replace_attempts = 0

    def transient_replace(path, target):
        nonlocal replace_attempts
        if Path(target) == output_path:
            replace_attempts += 1
            if replace_attempts == 1:
                raise PermissionError("trace temporarily locked")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", transient_replace)
    monkeypatch.setattr(browser_runner.time, "sleep", lambda _seconds: None)

    browser_runner._write_text_atomically(output_path, '[{"ok": true}]')

    assert replace_attempts == 2
    assert output_path.read_text(encoding="utf-8") == '[{"ok": true}]'
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.anyio
async def test_run_stagehand_exploration_wires_generic_stagehand_backend(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    embedding_path = tmp_path / "state_embeddings.json"
    trace_path = tmp_path / "stagehand_trace.json"
    calls = []
    captured = {}
    candidate_provider = lambda prompt, **kwargs: (
        '{"visible_change_summary":"changed","candidate_added_facts":[],'
        '"candidate_removed_facts":[],"evidence":[],"confidence":0.5}'
    )
    outcome_provider = object()

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self, *, viewport=None):
            calls.append(("new_page", viewport))
            return FakePage()

        async def close(self):
            calls.append(("close", None))

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            calls.append(("launch", headless, args))
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            calls.append(("stagehand", goal, execution_mode))
            self.app_name = base_backend.app_name

    class FakeController:
        def __init__(
            self,
            explorer,
            *,
            max_consecutive_unproductive_steps=3,
            step_checkpoint=None,
            limits=None,
        ):
            assert explorer.enable_exploration_memory is True
            assert explorer.max_candidates == 2
            assert explorer.state_embedding_provider("x") == [1.0, 0.0]
            assert explorer.action_embedding_provider("x") == [1.0, 0.0]
            assert explorer.business_profile is not None
            assert explorer.business_profile.site_type == "ecommerce_checkout"
            assert (
                explorer.visual_delta_provider("prompt")
                == '{"visible_change_summary":"changed","candidate_added_facts":[],"candidate_removed_facts":[],"evidence":[],"confidence":0.5}'
            )
            assert explorer.action_outcome_provider is outcome_provider
            assert isinstance(limits, ExplorationLimits)
            captured["limit"] = max_consecutive_unproductive_steps
            captured["checkpoint"] = step_checkpoint

        async def run(self, *, max_steps):
            graph = WebKobeGraph(
                app="demo",
                start_node_id="start",
                total_steps_completed=max_steps,
            )
            captured["checkpoint"](graph)
            return WebKobeExplorationResult(
                graph=graph,
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=max_steps,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    result = await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://shop.test/",
        app_name="demo",
        provider=object(),
        steps=3,
        state_embedding_provider=lambda text: [1.0, 0.0],
        embedding_path=embedding_path,
        stagehand_trace_path=trace_path,
        screenshot_dir=tmp_path / "screenshots",
        site_purpose="demo store",
        business_profile="ecommerce_checkout",
        max_candidates=2,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=outcome_provider,
    )

    assert result == output_path
    assert captured["limit"] is None
    assert captured["checkpoint"] is not None
    assert ("new_page", {"width": 1440, "height": 1000}) in calls
    assert ("goto", "https://shop.test/") in calls
    assert any(
        call[0] == "stagehand" and call[2] == "observed_action" for call in calls
    )
    assert output_path.exists()
    assert output_path.with_name("graph_evidence.json").exists()
    assert embedding_path.exists()
    assert trace_path.exists()
    graph_data = json.loads(output_path.read_text(encoding="utf-8"))
    summary = graph_data["meta"]["exploration_summary"]
    assert summary["requested_steps"] == 3
    assert summary["steps_completed"] == 3
    assert summary["stop_reason"] == "max_steps"
    assert summary["limits"]["max_candidates_per_location"] == 2


@pytest.mark.anyio
async def test_run_stagehand_exploration_wires_limits_and_allows_final_order_by_default(
    tmp_path, monkeypatch
):
    import playwright.async_api as playwright_async_api
    from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits

    output_path = tmp_path / "graph.json"
    captured = {}

    class FakePage:
        async def goto(self, url):
            captured["url"] = url

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            captured["goal"] = goal
            captured["stagehand_timeout"] = kwargs["action_timeout_seconds"]
            self.app_name = base_backend.app_name

    class FakeExplorer:
        def __init__(self, **kwargs):
            captured["explorer_limits"] = kwargs["exploration_limits"]
            self.state_embedding_records = []

    class FakeController:
        def __init__(self, explorer, **kwargs):
            captured["controller_limits"] = kwargs["limits"]
            captured["max_consecutive_unproductive_steps"] = kwargs[
                "max_consecutive_unproductive_steps"
            ]
            self.checkpoint = kwargs["step_checkpoint"]

        async def run(self, *, max_steps):
            captured["max_steps"] = max_steps
            graph = WebKobeGraph(
                app="demo",
                start_node_id="start",
                total_steps_completed=0,
                meta={"frontier_replay_attempts": {}},
            )
            result = WebKobeExplorationResult(
                graph=graph,
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=0,
                    stop_reason="frontier_exhausted",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )
            self.checkpoint(graph)
            return result

    limits = ExplorationLimits()
    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://fixture.test/shop",
        app_name="demo",
        provider=object(),
        max_candidates=8,
        limits=limits,
        stagehand_action_timeout_seconds=240,
    )

    assert captured["max_steps"] == 20
    assert captured["controller_limits"] == limits
    assert captured["max_consecutive_unproductive_steps"] is None
    assert captured["explorer_limits"] == limits
    assert captured["stagehand_timeout"] == 240
    assert "final confirmation is allowed" in captured["goal"]
    summary = json.loads(output_path.read_text(encoding="utf-8"))["meta"][
        "exploration_summary"
    ]
    assert summary == {
        "requested_steps": 20,
        "steps_completed": 0,
        "stop_reason": "frontier_exhausted",
        "formal_action_attempts": 0,
        "semantic_progress_count": 0,
        "consecutive_no_progress": 0,
        "replay_attempt_count": 0,
        "frontier_replay_attempts": {},
        "limits": limits.to_dict(),
    }


@pytest.mark.anyio
async def test_run_stagehand_exploration_resolves_separate_openai_observation_providers(
    tmp_path, monkeypatch
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    captured = {}
    factory_calls = []
    candidate_provider = object()
    outcome_provider = object()

    def fake_candidate_factory(**kwargs):
        factory_calls.append(("candidate", kwargs))
        return candidate_provider

    def fake_outcome_factory(**kwargs):
        factory_calls.append(("outcome", kwargs))
        return outcome_provider

    class FakePage:
        async def goto(self, url):
            captured["url"] = url

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            self.app_name = base_backend.app_name

    class FakeExplorer:
        def __init__(self, **kwargs):
            captured["visual_delta_provider"] = kwargs["visual_delta_provider"]
            captured["action_outcome_provider"] = kwargs["action_outcome_provider"]
            self.state_embedding_records = []

    class FakeController:
        def __init__(self, explorer, **kwargs):
            pass

        async def run(self, *, max_steps):
            graph = WebKobeGraph(
                app="demo",
                start_node_id="start",
                total_steps_completed=max_steps,
            )
            return WebKobeExplorationResult(
                graph=graph,
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=max_steps,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)
    monkeypatch.setattr(
        browser_runner,
        "create_openai_visual_delta_provider_from_env",
        fake_candidate_factory,
    )
    monkeypatch.setattr(
        browser_runner,
        "create_openai_action_outcome_provider_from_env",
        fake_outcome_factory,
    )

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://shop.test/",
        app_name="demo",
        provider=object(),
        steps=1,
        screenshot_dir=tmp_path / "screenshots",
        use_openai_visual_delta=True,
        visual_delta_model="candidate-model",
        action_outcome_model="outcome-model",
        vlm_request_timeout_seconds=12.5,
    )

    assert captured["visual_delta_provider"] is candidate_provider
    assert captured["action_outcome_provider"] is outcome_provider
    assert factory_calls == [
        (
            "candidate",
            {"model": "candidate-model", "request_timeout_seconds": 12.5},
        ),
        (
            "outcome",
            {"model": "outcome-model", "request_timeout_seconds": 12.5},
        ),
    ]


@pytest.mark.anyio
async def test_runner_preserves_cumulative_runtime_state(tmp_path, monkeypatch):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    runtime_state = {
        "formal_action_attempts": 20,
        "consecutive_no_progress": 1,
        "semantic_progress_count": 7,
        "replay_attempt_count": 2,
        "replay_success_count": 1,
        "replay_failure_count": 1,
        "replay_mismatch_count": 0,
        "frontier_replay_attempts": {"checkout": 1},
        "blocked_replay_node_ids": [],
    }

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            self.app_name = base_backend.app_name

    class FakeExplorer:
        def __init__(self, **kwargs):
            self.state_embedding_records = []

    class FakeController:
        def __init__(self, explorer, **kwargs):
            pass

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo",
                    start_node_id="start",
                    total_steps_completed=1,
                    meta={"exploration_runtime_state": dict(runtime_state)},
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=1,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                    semantic_progress_count=7,
                    replay_attempt_count=2,
                    total_steps_completed=1,
                ),
            )

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://practiceautomatedtesting.com/shopping",
        app_name="demo",
        provider=object(),
        steps=1,
        limits=ExplorationLimits(),
        allow_test_site_final_order=True,
    )

    meta = json.loads(output_path.read_text(encoding="utf-8"))["meta"]
    assert meta["exploration_runtime_state"]["formal_action_attempts"] == 20
    assert meta["formal_action_attempts"] == 20
    assert meta["exploration_summary"]["steps_completed"] == 1
    assert meta["exploration_summary"]["formal_action_attempts"] == 20


@pytest.mark.anyio
async def test_runner_resume_uses_cumulative_runtime_state_for_zero_formal_actions(
    tmp_path, monkeypatch
):
    import playwright.async_api as playwright_async_api
    from types import SimpleNamespace

    checkpoint_path = tmp_path / "checkpoint.json"
    output_path = tmp_path / "resumed.json"
    runtime_state = {
        "formal_action_attempts": 20,
        "consecutive_no_progress": 1,
        "semantic_progress_count": 7,
        "replay_attempt_count": 2,
        "replay_success_count": 1,
        "replay_failure_count": 1,
        "replay_mismatch_count": 0,
        "frontier_replay_attempts": {"checkout": 1},
        "blocked_replay_node_ids": [],
    }
    resume_graph = replace(
        browser_runner.build_debug_web_kobe_graph(),
        app="demo",
        meta={"exploration_runtime_state": dict(runtime_state)},
    )
    browser_runner.write_web_kobe_graph(resume_graph, checkpoint_path)
    from ai_web_explorer.safesym_bridge.graph_loader import (
        load_web_kobe_graph_json,
    )

    reloaded_graph = load_web_kobe_graph_json(checkpoint_path)
    controller_calls = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            self.app_name = base_backend.app_name

    class FakeExplorer:
        def __init__(self, **kwargs):
            self.state_embedding_records = []
            self._graph = reloaded_graph
            self.start_node_id = reloaded_graph.start_node_id
            self.manager = SimpleNamespace(
                to_graph=lambda start_node_id=None: self._graph
            )

        def restore_graph(self, graph):
            self._graph = graph

    class FakeController:
        def __init__(self, explorer, **kwargs):
            controller_calls.append(kwargs)

        async def run(self, *, max_steps):
            raise AssertionError("controller must not execute after cumulative limit")

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://practiceautomatedtesting.com/shopping",
        app_name="demo",
        provider=object(),
        steps=1,
        resume_graph=reloaded_graph,
        resume_policy=ResumePolicy(),
        limits=ExplorationLimits(),
        allow_test_site_final_order=True,
    )

    meta = json.loads(output_path.read_text(encoding="utf-8"))["meta"]
    assert controller_calls == []
    assert meta["exploration_runtime_state"]["formal_action_attempts"] == 20
    assert meta["formal_action_attempts"] == 20
    assert meta["exploration_summary"]["steps_completed"] == 0
    assert meta["exploration_summary"]["formal_action_attempts"] == 20
    for key, expected in {
        "replay_attempt_count": 2,
        "replay_success_count": 1,
        "replay_failure_count": 1,
        "replay_mismatch_count": 0,
    }.items():
        assert meta["exploration_runtime_state"][key] == expected
        assert meta[key] == expected


@pytest.mark.anyio
async def test_run_stagehand_exploration_opt_in_wires_frontier_replay(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            self.app_name = base_backend.app_name

    class FakeReplayRunner:
        def __init__(self, explorer):
            self.explorer = explorer
            calls.append(("replay_runner", self))

    class FakeController:
        def __init__(self, explorer, **kwargs):
            calls.append(("controller", kwargs))

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="fixture",
                    start_node_id="start",
                    total_steps_completed=max_steps,
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=max_steps,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                ),
            )

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakeContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "FrontierReplayRunner", FakeReplayRunner)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://fixture.test/shop",
        provider=object(),
        frontier_replay=True,
    )

    assert calls[0][0] == "replay_runner"
    assert calls[1][0] == "controller"
    assert calls[1][1]["frontier_replay_runner"] is calls[0][1]
    assert calls[1][1]["start_url"] == "https://fixture.test/shop"


@pytest.mark.anyio
async def test_e004_conditions_reject_confounded_or_unseeded_configuration(tmp_path):
    with pytest.raises(ValueError, match="linear cannot enable frontier replay"):
        await browser_runner.run_stagehand_exploration(
            tmp_path / "linear.json",
            start_url="https://fixture.test/shop",
            exploration_condition="linear",
            frontier_replay=True,
        )
    with pytest.raises(ValueError, match="random requires a random seed"):
        await browser_runner.run_stagehand_exploration(
            tmp_path / "random.json",
            start_url="https://fixture.test/shop",
            exploration_condition="random",
        )


@pytest.mark.anyio
async def test_run_stagehand_exploration_bootstraps_resume_without_spending_new_step(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api
    from types import SimpleNamespace

    output_path = tmp_path / "graph.json"
    resume_graph = browser_runner.build_debug_web_kobe_graph()
    resume_graph = replace(
        resume_graph,
        total_steps_completed=4,
        nodes=[
            replace(
                resume_graph.nodes[0],
                business_affordances=[BusinessAffordance("inspect_start")],
            )
        ],
    )
    calls = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            pass

    class FakeExplorer:
        def __init__(self, **kwargs):
            self.state_embedding_records = []
            self.restored = None
            self.preferred = None
            self.start_node_id = "start"
            self.manager = SimpleNamespace(
                to_graph=lambda start_node_id=None: resume_graph
            )

        def restore_graph(self, graph):
            self.restored = graph

        def prefer_resume_action(self, key):
            self.preferred = key

    class FakeReplayRunner:
        def __init__(self, explorer):
            self.explorer = explorer
            calls.append("replay_runner")

        async def replay(self, target, *, start_url):
            calls.append(
                ("replay", target.node_id, target.path, target.untried_action_ids)
            )
            from ai_web_explorer.grounded_web.frontier_replay import ReplayResult

            return ReplayResult(True, target.node_id, None, "replay_succeeded", 0)

    class FakeController:
        def __init__(self, explorer, **kwargs):
            calls.append(("controller", kwargs))

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="debug",
                    start_node_id="start",
                    total_steps_completed=5,
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=1,
                    stop_reason="max_steps",
                    node_count=0,
                    edge_count=0,
                    failed_edge_count=0,
                    historical_steps=4,
                    total_steps_completed=5,
                ),
            )

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "FrontierReplayRunner", FakeReplayRunner)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="about:blank",
        app_name="debug",
        provider=object(),
        steps=1,
        resume_graph=resume_graph,
        resume_policy=ResumePolicy(),
    )

    assert calls[0] == "replay_runner"
    assert calls[1][0] == "replay"
    assert calls[1][1] == "start"
    assert calls[1][2] == ()
    assert calls[2] == "replay_runner", calls
    assert calls[3][0] == "controller", calls
    assert isinstance(calls[3][1], dict), calls
    controller_kwargs = calls[3][1]
    assert controller_kwargs["historical_steps"] == 4
    assert controller_kwargs["replay_metric_baseline"]["replay_attempt_count"] == 1
    assert controller_kwargs["replay_metric_baseline"]["replay_success_count"] == 1


@pytest.mark.anyio
async def test_resume_bootstrap_replays_fallback_frontier_after_action_failure(
    tmp_path, monkeypatch
):
    import playwright.async_api as playwright_async_api
    from types import SimpleNamespace
    from ai_web_explorer.grounded_web.frontier_replay import ReplayResult

    output_path = tmp_path / "graph.json"
    resume_graph = browser_runner.build_debug_web_kobe_graph()
    targets = [
        SimpleNamespace(node_id="first", path=(), untried_action_ids=("first_action",)),
        SimpleNamespace(
            node_id="second", path=(), untried_action_ids=("second_action",)
        ),
    ]
    selected = []
    replayed = []
    captured_checkpoints = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            pass

    class FakeExplorer:
        def __init__(self, **kwargs):
            self.state_embedding_records = []
            self.start_node_id = "start"
            self.manager = SimpleNamespace(
                to_graph=lambda start_node_id=None: resume_graph
            )

        def restore_graph(self, graph):
            self.restored = graph

        def prefer_resume_action(self, key):
            raise AssertionError("failed target must not leave retry preference")

    class FakeReplayRunner:
        def __init__(self, explorer):
            self.explorer = explorer

        async def replay(self, target, *, start_url):
            replayed.append(target.node_id)
            if target.node_id == "first":
                return ReplayResult(
                    False,
                    None,
                    "first-edge",
                    "action_execution_failed",
                    0,
                )
            return ReplayResult(True, "second", None, "replay_succeeded", 0)

    class FakeController:
        def __init__(self, explorer, **kwargs):
            self.kwargs = kwargs

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=resume_graph,
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=1,
                    stop_reason="max_steps",
                    node_count=1,
                    edge_count=0,
                    failed_edge_count=0,
                    historical_steps=0,
                    total_steps_completed=1,
                ),
            )

    def fake_select(graph, *, policy, blocked_node_ids=()):
        selected.append(tuple(blocked_node_ids))
        return targets[len(selected) - 1] if len(selected) <= len(targets) else None

    monkeypatch.setattr(playwright_async_api, "async_playwright", lambda: FakeContext())
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorer", FakeExplorer)
    monkeypatch.setattr(browser_runner, "FrontierReplayRunner", FakeReplayRunner)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)
    monkeypatch.setattr(browser_runner, "select_resume_frontier", fake_select)
    monkeypatch.setattr(
        browser_runner,
        "_write_stagehand_checkpoint",
        lambda graph, **kwargs: captured_checkpoints.append(graph),
    )

    await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="about:blank",
        app_name="debug",
        provider=object(),
        steps=1,
        resume_graph=resume_graph,
        resume_policy=ResumePolicy(),
    )

    assert replayed == ["first", "second"]
    assert selected == [(), ()]
    assert len(captured_checkpoints) == 1
    assert captured_checkpoints[0].meta["blocked_replay_node_ids"] == []
    assert captured_checkpoints[0].meta["replay_mismatch_count"] == 0
    assert (
        captured_checkpoints[0].meta["exploration_runtime_state"][
            "replay_mismatch_count"
        ]
        == 0
    )


@pytest.mark.anyio
async def test_run_stagehand_exploration_preserves_checkpoint_when_step_raises(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    embedding_path = tmp_path / "state_embeddings.json"
    trace_path = tmp_path / "stagehand_trace.json"
    closed = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self, **kwargs):
            return FakePage()

        async def close(self):
            closed.append(True)

    class FakeChromium:
        async def launch(self, *, headless=True, args=None):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeStagehandBackend:
        def __init__(self, *, base_backend, provider, goal, execution_mode, **kwargs):
            self.app_name = base_backend.app_name

    class FakeController:
        def __init__(self, explorer, *, step_checkpoint=None, **kwargs):
            self.step_checkpoint = step_checkpoint

        async def run(self, *, max_steps):
            self.step_checkpoint(
                WebKobeGraph(
                    app="demo",
                    start_node_id="start",
                    total_steps_completed=1,
                )
            )
            raise RuntimeError("experiment interrupted")

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(
        browser_runner, "StagehandAutomationBackend", FakeStagehandBackend
    )
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    with pytest.raises(RuntimeError, match="experiment interrupted"):
        await browser_runner.run_stagehand_exploration(
            output_path,
            start_url="https://shop.test/",
            app_name="demo",
            provider=object(),
            steps=3,
            state_embedding_provider=lambda text: [1.0, 0.0],
            embedding_path=embedding_path,
            stagehand_trace_path=trace_path,
            screenshot_dir=tmp_path / "screenshots",
        )

    assert closed == [True]
    assert output_path.exists()
    assert output_path.with_name("graph_evidence.json").exists()
    assert embedding_path.exists()
    assert trace_path.exists()
    json.loads(output_path.read_text(encoding="utf-8"))
    json.loads(output_path.with_name("graph_evidence.json").read_text(encoding="utf-8"))
    json.loads(embedding_path.read_text(encoding="utf-8"))
    json.loads(trace_path.read_text(encoding="utf-8"))


@pytest.mark.anyio
async def test_run_stagehand_exploration_requires_screenshots_for_visual_delta(
    tmp_path,
):
    with pytest.raises(ValueError, match="screenshot_dir"):
        await browser_runner.run_stagehand_exploration(
            tmp_path / "graph.json",
            start_url="https://shop.test/",
            provider=object(),
            visual_delta_provider=lambda prompt, **kwargs: "{}",
        )


@pytest.mark.anyio
async def test_run_stagehand_exploration_requires_screenshots_for_risk_detection(
    tmp_path,
):
    with pytest.raises(ValueError, match="screenshot_dir"):
        await browser_runner.run_stagehand_exploration(
            tmp_path / "graph.json",
            start_url="https://shop.test/",
            provider=object(),
            use_openai_risk_detection=True,
        )
