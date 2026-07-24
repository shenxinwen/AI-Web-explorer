import json

import pytest

from ai_web_explorer.safesym_bridge import browser_runner
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_web_kobe_exploration,
    run_saucedemo_openai_selector_step,
    run_saucedemo_llm_selector_step,
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
async def test_run_saucedemo_llm_selector_step_bootstraps_login_and_writes_trace(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "saucedemo_step_graph.json"
    trace_path = tmp_path / "saucedemo_step_trace.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

        async def fill(self, selector, value):
            calls.append(("fill", selector, value))

        async def click(self, selector):
            calls.append(("click", selector))

        async def wait_for_url(self, pattern):
            calls.append(("wait_for_url", pattern))

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

    def fake_selector(request):
        raise AssertionError("controller fake should not call selector directly")

    class FakeController:
        def __init__(self, explorer):
            assert explorer.adapter.app_name == "saucedemo"
            assert explorer.goal == "Complete a SauceDemo checkout order."
            assert explorer.action_selector is fake_selector
            explorer.selection_traces.append(
                {
                    "status": "selected",
                    "llm_response": {
                        "selected_action_id": "product_add_to_cart",
                    },
                }
            )

        async def run(self, *, max_steps=1):
            assert max_steps == 3
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="inventory",
                    total_steps_completed=3,
                ),
                summary=WebKobeExplorationSummary(
                    requested_steps=3,
                    steps_completed=3,
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

    result_path = await run_saucedemo_llm_selector_step(
        output_path,
        selector_trace_path=trace_path,
        action_selector=fake_selector,
        steps=3,
    )

    assert result_path == output_path
    assert calls == [
        ("launch", True),
        ("new_page", None),
        ("goto", "https://www.saucedemo.com/"),
        ("fill", "#user-name", "standard_user"),
        ("fill", "#password", "secret_sauce"),
        ("click", "#login-button"),
        ("wait_for_url", "**/inventory.html"),
        ("close", None),
    ]
    assert json.loads(output_path.read_text(encoding="utf-8"))["meta"]["app"] == (
        "saucedemo"
    )
    assert (
        json.loads(trace_path.read_text(encoding="utf-8"))[0]["llm_response"][
            "selected_action_id"
        ]
        == "product_add_to_cart"
    )


@pytest.mark.anyio
async def test_run_saucedemo_openai_selector_step_wraps_provider(
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "graph.json"
    trace_path = tmp_path / "trace.json"
    calls = []

    def fake_provider(prompt):
        return (
            '{"selected_action_id":"product_add_to_cart",'
            '"confidence":0.9,'
            '"reason":"Cart is empty."}'
        )

    async def fake_run_step(output_path_arg, **kwargs):
        calls.append((output_path_arg, kwargs))
        assert kwargs["selector_trace_path"] == trace_path
        assert kwargs["headless"] is False
        assert kwargs["steps"] == 3
        selector_result = kwargs["action_selector"](
            browser_runner.LlmActionSelectionRequest(
                goal="Complete a SauceDemo checkout order.",
                state=StateSnapshot(
                    page_id="inventory",
                    url="https://www.saucedemo.com/inventory.html",
                    title="Swag Labs",
                    signature={"cart_count": 0},
                ),
                candidate_actions=[
                    BrowserAction(
                        "click",
                        '[data-test="add-to-cart-sauce-labs-backpack"]',
                        "product_add_to_cart",
                    )
                ],
            )
        )
        assert selector_result.selected_action.semantic_id == "product_add_to_cart"
        output_path_arg.write_text(
            '{"meta": {"app": "saucedemo"}}',
            encoding="utf-8",
        )
        return output_path_arg

    monkeypatch.setattr(
        browser_runner,
        "create_openai_chat_selection_provider_from_env",
        lambda model=None: fake_provider,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "run_saucedemo_llm_selector_step",
        fake_run_step,
        raising=False,
    )

    result_path = await run_saucedemo_openai_selector_step(
        output_path,
        selector_trace_path=trace_path,
        model="gpt-test",
        headless=False,
        steps=3,
    )

    assert result_path == output_path
    assert calls[0][0] == output_path


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


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_wires_stagehand_backend(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    trace_path = tmp_path / "stagehand_trace.json"
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

    class FakeProvider:
        pass

    class FakeController:
        def __init__(self, explorer):
            calls.append(("controller", explorer.adapter.app_name))

        async def run(self, *, max_steps=1):
            assert max_steps == 6
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
                    total_steps_completed=max_steps,
                    meta={
                        "stagehand_traces": [
                            {
                                "action_source": "stagehand",
                                "stagehand_selector": "#login-button",
                            }
                        ]
                    },
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
    monkeypatch.setattr(browser_runner, "_pick_free_port", lambda: 9444, raising=False)

    result_path = await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        stagehand_trace_path=trace_path,
        provider=FakeProvider(),
        steps=6,
    )

    assert result_path == output_path
    assert calls == [
        ("launch", True, None),
        ("new_page", None),
        ("goto", "https://www.saucedemo.com/"),
        ("controller", "saucedemo"),
        ("close", None),
    ]
    assert json.loads(output_path.read_text(encoding="utf-8"))["meta"]["app"] == (
        "saucedemo"
    )
    assert json.loads(trace_path.read_text(encoding="utf-8")) == [
        {
            "action_source": "stagehand",
            "stagehand_selector": "#login-button",
        }
    ]


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_can_allow_final_order(
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
            calls.append(("stagehand_goal", goal))
            self.app_name = base_backend.app_name

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            calls.append(("explorer_goal", explorer.goal))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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
    monkeypatch.setattr(
        browser_runner,
        "WebKobePlaywrightAdapter",
        FakeBaseAdapter,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        allow_final_order=True,
    )

    assert "final order" in next(
        call[1] for call in calls if call[0] == "stagehand_goal"
    )
    assert (
        next(call[1] for call in calls if call[0] == "explorer_goal")
        == browser_runner.ECOMMERCE_CHECKOUT_COMPLETE_EXPLORER_GOAL
    )


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_uses_configurable_benchmark_context(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
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
            calls.append(("stagehand_goal", goal))
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
                    app="saucedemo",
                    start_node_id="login",
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

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        test_username="fixture_user",
        test_password="fixture_password",
        checkout_first_name="Ada",
        checkout_last_name="Lovelace",
        checkout_postal_code="42424",
    )

    stagehand_goal = next(call[1] for call in calls if call[0] == "stagehand_goal")
    assert "fixture_user" in stagehand_goal
    assert "fixture_password" in stagehand_goal
    assert "first_name=Ada" in stagehand_goal
    assert "last_name=Lovelace" in stagehand_goal
    assert "postal_code=42424" in stagehand_goal


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_passes_cdp_url_to_provider(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    calls = []

    class FakePage:
        async def goto(self, url):
            calls.append(("goto", url))

    fake_page = FakePage()

    class FakeBrowser:
        async def new_page(self):
            calls.append(("new_page", None))
            return fake_page

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

    async def fake_create_provider(**kwargs):
        calls.append(("provider", kwargs))
        return object()

    class FakeBaseAdapter:
        def __init__(self, page, *, app_name, page_id=None, screenshot_dir=None):
            calls.append(("adapter", page, app_name))
            self.app_name = app_name

        async def observe_state(self):
            return StateSnapshot(
                page_id="login",
                url="https://www.saucedemo.com/",
                title="Swag Labs",
                signature={},
            )

    class FakeController:
        def __init__(self, explorer):
            calls.append(("controller", explorer.adapter.app_name))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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
    monkeypatch.setattr(browser_runner, "_pick_free_port", lambda: 9333, raising=False)
    monkeypatch.setattr(
        browser_runner,
        "_read_cdp_websocket_url",
        lambda port: "ws://127.0.0.1:9333/devtools/browser/test",
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "create_async_stagehand_provider_from_env",
        fake_create_provider,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobePlaywrightAdapter",
        FakeBaseAdapter,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        steps=1,
        model="deepseek/test",
    )

    assert calls[0] == (
        "launch",
        True,
        ["--remote-debugging-port=9333"],
    )
    assert ("goto", "https://www.saucedemo.com/") in calls
    provider_call = next(call for call in calls if call[0] == "provider")
    assert provider_call[1]["model_name"] == "deepseek/test"
    assert provider_call[1]["page"] is fake_page
    assert (
        provider_call[1]["local_cdp_url"] == "ws://127.0.0.1:9333/devtools/browser/test"
    )


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_wires_screenshot_capture(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    screenshot_dir = tmp_path / "stagehand_screenshots"
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
            calls.append(("adapter", screenshot_dir))
            self.app_name = app_name

    class FakeController:
        def __init__(self, explorer):
            calls.append(("capture", explorer.capture_screenshots))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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
        "WebKobePlaywrightAdapter",
        FakeBaseAdapter,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "WebKobeExplorationController",
        FakeController,
        raising=False,
    )

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        screenshot_dir=screenshot_dir,
    )

    assert calls == [
        ("adapter", screenshot_dir),
        ("capture", True),
    ]


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_wires_visual_delta_provider(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    screenshot_dir = tmp_path / "stagehand_screenshots"
    visual_provider = object()
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

    class FakeController:
        def __init__(self, explorer):
            calls.append(("visual_provider", explorer.visual_delta_provider))
            calls.append(("profile", explorer.business_profile.site_type))
            calls.append(("capture", explorer.capture_screenshots))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        screenshot_dir=screenshot_dir,
        visual_delta_provider=visual_provider,
    )

    assert calls == [
        ("visual_provider", visual_provider),
        ("profile", "ecommerce_checkout"),
        ("capture", True),
    ]


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_creates_openai_visual_delta_provider(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    screenshot_dir = tmp_path / "stagehand_screenshots"
    created_provider = object()
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

    class FakeController:
        def __init__(self, explorer):
            calls.append(("visual_provider", explorer.visual_delta_provider))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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

    def fake_create_openai_visual_delta_provider_from_env(*, model=None):
        calls.append(("create_openai_visual_delta", model))
        return created_provider

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)
    monkeypatch.setattr(
        browser_runner,
        "create_openai_visual_delta_provider_from_env",
        fake_create_openai_visual_delta_provider_from_env,
        raising=False,
    )

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        screenshot_dir=screenshot_dir,
        use_openai_visual_delta=True,
        visual_delta_model="gpt-4o-mini",
    )

    assert calls == [
        ("create_openai_visual_delta", "gpt-4o-mini"),
        ("visual_provider", created_provider),
    ]


@pytest.mark.anyio
async def test_run_saucedemo_stagehand_step_creates_deepseek_semantic_naming_provider(
    tmp_path,
    monkeypatch,
):
    import playwright.async_api as playwright_async_api

    output_path = tmp_path / "stagehand_graph.json"
    created_text_provider = object()
    created_request_provider = object()
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

    class FakeController:
        def __init__(self, explorer):
            calls.append(("semantic_provider", explorer.semantic_naming_provider))

        async def run(self, *, max_steps=1):
            return WebKobeExplorationResult(
                graph=WebKobeGraph(
                    app="saucedemo",
                    start_node_id="login",
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

    def fake_create_deepseek_semantic_naming_provider_from_env(*, model=None):
        calls.append(("create_deepseek_semantic_naming", model))
        return created_text_provider

    def fake_semantic_naming_provider_from_text_provider(text_provider):
        calls.append(("wrap_semantic_naming_provider", text_provider))
        return created_request_provider

    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )
    monkeypatch.setattr(browser_runner, "WebKobePlaywrightAdapter", FakeBaseAdapter)
    monkeypatch.setattr(browser_runner, "WebKobeExplorationController", FakeController)
    monkeypatch.setattr(
        browser_runner,
        "create_deepseek_semantic_naming_provider_from_env",
        fake_create_deepseek_semantic_naming_provider_from_env,
        raising=False,
    )
    monkeypatch.setattr(
        browser_runner,
        "semantic_naming_provider_from_text_provider",
        fake_semantic_naming_provider_from_text_provider,
        raising=False,
    )

    await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        provider=object(),
        use_deepseek_semantic_naming=True,
        semantic_naming_model="deepseek-chat",
    )

    assert calls == [
        ("create_deepseek_semantic_naming", "deepseek-chat"),
        ("wrap_semantic_naming_provider", created_text_provider),
        ("semantic_provider", created_request_provider),
    ]
