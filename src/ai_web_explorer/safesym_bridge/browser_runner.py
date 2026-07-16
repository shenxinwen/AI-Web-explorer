from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import (
    ReferenceObservation,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)


def build_debug_web_kobe_graph() -> WebKobeGraph:
    evidence = [Evidence(source="debug_builder")]
    start_node = WebKobeNode(
        node_id="start",
        page_description="debug start page",
        page_frame=PageFrame(
            page_id="debug:start",
            page_type="start",
            url="about:blank",
            url_pattern="about:blank",
            title="Debug",
            evidence=evidence,
        ),
        state_schema={},
        last_state_snapshot={},
        reference_observation=ReferenceObservation(url="about:blank", title="Debug"),
        visit_count=1,
        evidence=evidence,
    )
    return WebKobeGraph(
        app="debug",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[start_node],
        edges=[],
        meta={"source": "debug_builder"},
    )


def write_web_kobe_graph(graph: WebKobeGraph, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


async def run_web_kobe_exploration(
    url: str,
    output_path: Path,
    *,
    app_name: str = "web",
    page_id: str | None = None,
    steps: int = 1,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                page_id=page_id,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            write_web_kobe_graph(result.graph, output_path)
            return output_path
        finally:
            await browser.close()
