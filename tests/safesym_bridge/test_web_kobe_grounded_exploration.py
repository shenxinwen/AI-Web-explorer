from pathlib import Path

import pytest

from ai_web_explorer.safesym_bridge.web_kobe_controller import (
    WebKobeExplorationController,
)
from ai_web_explorer.safesym_bridge.web_kobe_explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.safesym_bridge.web_semantic_assistor import (
    DeterministicSemanticAssistor,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_grounded_exploration_tries_fixture_interactables_and_records_deltas():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_shop/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="local_shop",
                page_id="local_shop",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="local_shop"),
            )
            controller = WebKobeExplorationController(explorer)

            result = await controller.run(max_steps=3)

            assert result.summary.steps_completed == 3
            assert result.summary.stop_reason == "max_steps"
            assert result.graph.total_steps_completed == 3

            deltas = [
                (delta.field, delta.before, delta.after)
                for edge in result.graph.edges
                for delta in edge.observed_delta
            ]
            assert ("cart_panel_visible", False, True) in deltas
            assert ("cart_count", 0, 1) in deltas
        finally:
            await browser.close()
