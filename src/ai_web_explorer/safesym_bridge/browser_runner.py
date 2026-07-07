from __future__ import annotations

from pathlib import Path

from ai_web_explorer.safesym_bridge.graph_explorer import GraphExplorer
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
from ai_web_explorer.safesym_bridge.saucedemo_adapter import SauceDemoAdapter


async def run_saucedemo_explored_graph(
    output_path: Path,
    *,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    adapter = SauceDemoAdapter()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(adapter.start_url)
            explorer = GraphExplorer(adapter)
            await explorer.run(page, output_path=output_path)
            return output_path
        finally:
            await browser.close()


async def run_saucedemo_explored_pddl(
    output_dir: Path,
    *,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    adapter = SauceDemoAdapter()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(adapter.start_url)
            explorer = GraphExplorer(adapter)
            result = await explorer.run(page)
            write_pddl_artifacts(result.graph, output_dir)
            return output_dir
        finally:
            await browser.close()
