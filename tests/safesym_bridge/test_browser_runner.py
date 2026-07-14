import json
import os

import pytest

from ai_web_explorer.safesym_bridge import browser_runner
from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
    run_web_kobe_exploration,
    write_observed_graph,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.web_kobe_controller import (
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_write_observed_graph_writes_graph_json(tmp_path):
    output_path = tmp_path / "saucedemo_observed_graph.json"

    result_path = write_observed_graph(
        transitions=build_saucedemo_mvp_transitions(),
        output_path=output_path,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert any(node["id"] == "inventory" for node in data["nodes"])
    assert any(
        edge["semantic_action"] == "order_place_confirm" for edge in data["edges"]
    )


def test_run_saucedemo_explored_graph_is_async_callable():
    assert callable(run_saucedemo_explored_graph)


def test_run_saucedemo_explored_pddl_is_async_callable():
    assert callable(run_saucedemo_explored_pddl)


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


@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDEMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDEMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.anyio
async def test_run_saucedemo_explored_graph_smoke(tmp_path):
    output_path = tmp_path / "saucedemo_explored_graph.json"

    result_path = await run_saucedemo_explored_graph(output_path)

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    node_ids = {node["id"] for node in data["nodes"]}
    action_ids = {edge["semantic_action"] for edge in data["edges"]}
    assert {
        "login",
        "inventory",
        "cart",
        "checkout_info",
        "checkout_overview",
        "checkout_complete",
    }.issubset(node_ids)
    assert {
        "login_submit",
        "product_add_to_cart",
        "cart_open",
        "cart_checkout_start",
        "checkout_info_submit",
        "order_place_confirm",
    }.issubset(action_ids)


@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDEMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDEMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.anyio
async def test_run_saucedemo_explored_pddl_smoke(tmp_path):
    output_dir = tmp_path / "explored_graph_pddl"

    result_dir = await run_saucedemo_explored_pddl(output_dir)

    assert result_dir == output_dir
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    problem = (output_dir / "problem.pddl").read_text(encoding="utf-8")
    assert "(:action login_fill_credentials" in domain
    assert "(:action checkout_info_fill" in domain
    assert "(:action order_place_confirm" in domain
    assert "(state_order_created)" in problem
