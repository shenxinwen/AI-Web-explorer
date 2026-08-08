import json

import pytest

from ai_web_explorer.safesym_bridge import browser_runner
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_web_kobe_exploration,
)
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.graph import BusinessAffordance
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.graph import ReferenceObservation
from ai_web_explorer.grounded_web.graph import WebKobeEdge
from ai_web_explorer.grounded_web.graph import WebKobeNode
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.stagehand_prompt import BenchmarkTaskContext


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_run_web_kobe_exploration_is_async_callable():
    assert callable(run_web_kobe_exploration)


def test_browser_runner_default_adapter_is_generic_grounded_web_adapter():
    assert (
        browser_runner.WebKobePlaywrightAdapter.__module__
        == "ai_web_explorer.grounded_web.playwright_backend"
    )


def test_stagehand_ecommerce_goal_avoids_site_specific_script():
    prompt_text = " ".join(
        [
            browser_runner.ECOMMERCE_CHECKOUT_OVERVIEW_STAGEHAND_GOAL,
            browser_runner.ECOMMERCE_CHECKOUT_COMPLETE_STAGEHAND_GOAL,
        ]
    )

    forbidden_terms = [
        "SauceDemo",
        "standard_user",
        "secret_sauce",
        "Sauce Labs Backpack",
        "If the username field is empty",
    ]
    for term in forbidden_terms:
        assert term not in prompt_text


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

    data = json.loads(output_path.read_text(encoding="utf-8"))
    metrics = data["meta"]["frontier_metrics"]
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


@pytest.mark.anyio
async def test_run_web_kobe_exploration_uses_controller(tmp_path, monkeypatch):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "web_kobe_graph.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self):
            calls.append(("new_page", None))
            return FakePage()

        async def close(self):
            calls.append(("close", None))

    class FakeChromium:
        async def launch(self, *, headless=True):
            calls.append(("launch", headless))
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeController:
        def __init__(self, explorer):
            calls.append(("controller", explorer.adapter.app_name))

        async def run(self, *, max_steps=1):
            calls.append(("run", max_steps))
            graph = WebKobeGraph(
                app="fixture",
                start_node_id="fixture_shop",
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

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    result_path = await run_web_kobe_exploration(
        "https://example.test/shop",
        output_path,
        app_name="fixture",
        steps=3,
    )

    assert result_path == output_path
    assert calls == [
        ("launch", True),
        ("new_page", None),
        ("goto", "https://example.test/shop"),
        ("controller", "fixture"),
        ("run", 3),
        ("close", None),
    ]
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["total_steps_completed"] == 3


@pytest.mark.anyio
async def test_run_web_kobe_exploration_wires_screenshot_capture(tmp_path, monkeypatch):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "web_kobe_graph.json"
    screenshot_dir = tmp_path / "screenshots"
    calls = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

        async def close(self):
            pass

    class FakeChromium:
        async def launch(self, *, headless=True):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            calls.append(("adapter", app_name, page_id, screenshot_dir))
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            calls.append(("capture", explorer.capture_screenshots))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="fixture",
                    start_node_id="fixture_shop",
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
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await run_web_kobe_exploration(
        "https://example.test/shop",
        output_path,
        app_name="fixture",
        page_id="fixture_shop",
        screenshot_dir=screenshot_dir,
    )

    assert calls == [
        ("adapter", "fixture", "fixture_shop", screenshot_dir),
        ("capture", True),
    ]






@pytest.mark.anyio
async def test_run_ecommerce_stagehand_step_uses_generic_start_url_and_context(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self):
            calls.append(("new_page", None))
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

    class FakeStagehandBackend:
        def __init__(
            self,
            *,
            base_backend,
            provider,
            goal,
            execution_mode,
            goal_provider=None,
            business_step_metadata_provider=None,
        ):
            calls.append(("stagehand_goal", goal))
            calls.append(("stagehand_execution_mode", execution_mode))
            self.app_name = base_backend.app_name

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            calls.append(("adapter", app_name, screenshot_dir))
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            calls.append(("controller", explorer.adapter.app_name, explorer.goal))

        async def run(self, *, max_steps=1):
            assert max_steps == 4
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo_shop",
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
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(
        browser_runner,
        "StagehandAutomationBackend",
        FakeStagehandBackend,
        raising=False,
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    result_path = await browser_runner.run_ecommerce_stagehand_step(
        output_path,
        start_url="https://example.test/shop",
        app_name="demo_shop",
        provider=object(),
        steps=4,
        benchmark_context=BenchmarkTaskContext(
            site_label="demo shop",
            test_credentials={"username": "demo_user"},
            checkout_data={"postal_code": "42424"},
        ),
    )

    assert result_path == output_path
    assert ("goto", "https://example.test/shop") in calls
    assert ("adapter", "demo_shop", None) in calls
    stagehand_goal = next(call[1] for call in calls if call[0] == "stagehand_goal")
    assert "site_label: demo shop" in stagehand_goal
    assert "username=demo_user" in stagehand_goal
    assert "postal_code=42424" in stagehand_goal
    assert ("stagehand_execution_mode", "business_milestone") in calls


@pytest.mark.anyio
async def test_run_ecommerce_stagehand_step_wires_default_experiment_steps(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    captured = {}

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

        async def close(self):
            pass

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

    class FakeStagehandBackend:
        def __init__(
            self,
            *,
            base_backend,
            provider,
            goal,
            execution_mode,
            goal_provider=None,
            business_step_metadata_provider=None,
        ):
            captured["goal_provider"] = goal_provider
            captured["metadata_provider"] = business_step_metadata_provider
            self.app_name = base_backend.app_name

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            pass

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo_shop",
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
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(
        browser_runner,
        "StagehandAutomationBackend",
        FakeStagehandBackend,
        raising=False,
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_ecommerce_stagehand_step(
        output_path,
        start_url="https://example.test/shop",
        app_name="demo_shop",
        provider=object(),
        steps=2,
    )

    first_goal = captured["goal_provider"](1)
    second_goal = captured["goal_provider"](2)
    second_metadata = captured["metadata_provider"](2)
    assert "Configured experiment step:" in first_goal
    assert "Milestone guidance:" in first_goal
    assert "guidance, not a mandatory fixed sequence" in first_goal
    assert first_goal == second_goal
    assert second_metadata["experiment_step_id"] == "add_product_to_cart"
    assert second_metadata["expected_added_facts"] == ["cart_has_items"]


@pytest.mark.anyio
async def test_run_ecommerce_stagehand_step_wires_terminal_condition(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    controllers = []

    class FakePage:
        async def goto(self, url):
            pass

    class FakeBrowser:
        async def new_page(self):
            return FakePage()

        async def close(self):
            pass

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

    class FakeStagehandBackend:
        def __init__(
            self,
            *,
            base_backend,
            provider,
            goal,
            execution_mode,
            goal_provider=None,
            business_step_metadata_provider=None,
        ):
            self.app_name = base_backend.app_name

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            self.terminal_condition = None
            controllers.append(self)

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo_shop",
                    start_node_id="start",
                    total_steps_completed=1,
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=max_steps,
                    steps_completed=1,
                    stop_reason="terminal_condition",
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
    monkeypatch.setattr(
        browser_runner,
        "StagehandAutomationBackend",
        FakeStagehandBackend,
        raising=False,
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_ecommerce_stagehand_step(
        output_path,
        start_url="https://example.test/shop",
        app_name="demo_shop",
        provider=object(),
        allow_final_order=True,
    )

    terminal_graph = WebKobeGraph(
        app="demo_shop",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="start",
                page_description="start",
                page_frame=PageFrame(
                    page_id="demo:start",
                    page_type="start",
                    url="https://example.test/",
                    url_pattern="https://example.test/",
                    title="Start",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
            WebKobeNode(
                node_id="complete",
                page_description="complete",
                page_frame=PageFrame(
                    page_id="demo:complete",
                    page_type="complete",
                    url="https://example.test/checkout-complete.html",
                    url_pattern="https://example.test/checkout-complete.html",
                    title="Complete",
                ),
                state_schema={},
                last_state_snapshot={},
                reference_observation=ReferenceObservation(
                    url="https://example.test/checkout-complete.html",
                    title="Complete",
                ),
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="start",
                target_node_id="complete",
                instruction="finish order",
                action=BrowserAction("business_intent", None, "finish_order"),
                capability=None,
                target_observation="complete",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "finish_order",
                    {},
                    "start",
                    "complete",
                    True,
                ),
                status="succeeded_with_navigation",
            )
        ],
    )

    assert controllers[0].terminal_condition is not None
    assert controllers[0].terminal_condition(terminal_graph) is True


@pytest.mark.anyio
async def test_run_stagehand_exploration_wires_generic_stagehand_backend(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "graph.json"
    embedding_path = tmp_path / "state_embeddings.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    class FakeBrowser:
        async def new_page(self):
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
        def __init__(self, explorer):
            assert explorer.enable_exploration_memory is True
            assert explorer.max_candidates == 2
            assert explorer.state_embedding_provider("x") == [1.0, 0.0]
            assert explorer.action_embedding_provider("x") == [1.0, 0.0]
            assert explorer.business_profile is not None
            assert explorer.business_profile.site_type == "ecommerce_checkout"
            assert explorer.visual_delta_provider("prompt") == '{"visible_change_summary":"changed","candidate_added_facts":[],"candidate_removed_facts":[],"evidence":[],"confidence":0.5}'

        async def run(self, *, max_steps):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="demo",
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
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "StagehandAutomationBackend", FakeStagehandBackend)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    result = await browser_runner.run_stagehand_exploration(
        output_path,
        start_url="https://shop.test/",
        app_name="demo",
        provider=object(),
        steps=3,
        state_embedding_provider=lambda text: [1.0, 0.0],
        embedding_path=embedding_path,
        screenshot_dir=tmp_path / "screenshots",
        site_purpose="demo store",
        business_profile="ecommerce_checkout",
        max_candidates=2,
        visual_delta_provider=lambda prompt, **kwargs: '{"visible_change_summary":"changed","candidate_added_facts":[],"candidate_removed_facts":[],"evidence":[],"confidence":0.5}',
    )

    assert result == output_path
    assert ("goto", "https://shop.test/") in calls
    assert any(
        call[0] == "stagehand" and call[2] == "observed_action"
        for call in calls
    )
    assert output_path.exists()
    assert embedding_path.exists()


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
