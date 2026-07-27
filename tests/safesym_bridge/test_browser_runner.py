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
async def test_run_web_kobe_exploration_writes_selector_trace(tmp_path, monkeypatch):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "web_kobe_graph.json"
    trace_path = tmp_path / "selector_trace.json"
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
        async def launch(self, *, headless=True):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    def fake_selector(request):
        raise AssertionError("controller fake should not call selector directly")

    class FakeController:
        def __init__(self, explorer):
            assert explorer.action_selector is fake_selector
            explorer.selection_traces.append(
                {
                    "status": "selected",
                    "llm_response": {
                        "selected_action_id": "product_add_to_cart",
                    },
                }
            )
            self.explorer = explorer

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
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    await run_web_kobe_exploration(
        "https://example.test/shop",
        output_path,
        app_name="fixture",
        steps=1,
        action_selector=fake_selector,
        selector_trace_path=trace_path,
    )

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace == [
        {
            "status": "selected",
            "llm_response": {
                "selected_action_id": "product_add_to_cart",
            },
        }
    ]


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
        def __init__(self, *, base_backend, provider, goal, execution_mode):
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
        def __init__(self, *, base_backend, provider, goal, execution_mode):
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
