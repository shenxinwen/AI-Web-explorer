from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.controller import WebKobeExplorationController
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_form_search_records_typed_numeric_and_group_deltas():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_form_search/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="local_form_search",
                page_id="local_form_search",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(
                    app="local_form_search"
                ),
            )
            controller = WebKobeExplorationController(explorer)

            result = await controller.run(max_steps=2)

            delta_types = {
                delta.delta_type
                for edge in result.graph.edges
                for delta in edge.observed_delta
            }
            fields = {
                delta.field
                for edge in result.graph.edges
                for delta in edge.observed_delta
            }
            assert "numeric_changed" in delta_types
            assert "repeated_entity_count_changed" in delta_types
            assert "result_count" in fields
            assert "result_row_count" in fields
        finally:
            await browser.close()
