from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.simple_agent import (
    SimpleGroundedWebAgent,
)
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _delta_tuples(result):
    return [
        (delta.field, delta.before, delta.after)
        for edge in result.graph.edges
        for delta in edge.observed_delta
    ]


@pytest.mark.anyio
async def test_simple_grounded_agent_runs_local_shop_browser_smoke():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_shop/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            backend = WebKobePlaywrightAdapter(
                page,
                app_name="local_shop",
                page_id="local_shop",
            )
            agent = SimpleGroundedWebAgent(backend)

            result = await agent.run(max_steps=3)

            assert result.summary.steps_completed == 3
            assert result.summary.stop_reason == "max_steps"
            deltas = _delta_tuples(result)
            assert ("cart_panel_visible", False, True) in deltas
            assert ("cart_count", 0, 1) in deltas
            assert ("cart_count", 1, 2) in deltas
        finally:
            await browser.close()


@pytest.mark.anyio
async def test_simple_grounded_agent_runs_local_form_browser_smoke():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_form/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            backend = WebKobePlaywrightAdapter(
                page,
                app_name="local_form",
                page_id="local_form",
            )
            agent = SimpleGroundedWebAgent(backend)

            result = await agent.run(max_steps=3)

            assert result.summary.steps_completed == 3
            assert result.summary.stop_reason == "max_steps"
            deltas = _delta_tuples(result)
            assert ("name_value", "empty", "test") in deltas
            assert ("topic_value", "empty", "alpha") in deltas
            assert ("submitted", False, True) in deltas
        finally:
            await browser.close()
