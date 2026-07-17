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
from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_run_web_kobe_exploration_is_async_callable():
    assert callable(run_web_kobe_exploration)


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
async def test_run_web_kobe_exploration_writes_selector_trace(
    tmp_path, monkeypatch
):
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
    assert json.loads(trace_path.read_text(encoding="utf-8"))[0]["llm_response"][
        "selected_action_id"
    ] == "product_add_to_cart"


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

    result_path = await browser_runner.run_saucedemo_stagehand_step(
        output_path,
        stagehand_trace_path=trace_path,
        provider=FakeProvider(),
        steps=6,
    )

    assert result_path == output_path
    assert calls == [
        ("launch", True),
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
