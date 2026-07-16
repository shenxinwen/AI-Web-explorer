from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

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
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionRequest,
    LlmActionSelectionResult,
    select_action_with_llm,
)
from ai_web_explorer.grounded_web.openai_action_selector import (
    create_openai_chat_selection_provider_from_env,
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
    goal: str = "Explore the web task.",
    action_selector: (
        Callable[[LlmActionSelectionRequest], LlmActionSelectionResult] | None
    ) = None,
    selector_trace_path: Path | None = None,
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
                goal=goal,
                action_selector=action_selector,
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            write_web_kobe_graph(result.graph, output_path)
            if selector_trace_path is not None:
                selector_trace_path.parent.mkdir(parents=True, exist_ok=True)
                selector_trace_path.write_text(
                    json.dumps(
                        explorer.selection_traces,
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()


async def _bootstrap_saucedemo_login(page) -> None:
    await page.goto("https://www.saucedemo.com/")
    await page.fill("#user-name", "standard_user")
    await page.fill("#password", "secret_sauce")
    await page.click("#login-button")
    await page.wait_for_url("**/inventory.html")


async def run_saucedemo_llm_selector_step(
    output_path: Path,
    *,
    selector_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 1,
    action_selector: Callable[
        [LlmActionSelectionRequest],
        LlmActionSelectionResult,
    ],
) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await _bootstrap_saucedemo_login(page)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="saucedemo",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="saucedemo"),
                goal="Complete a SauceDemo checkout order.",
                action_selector=action_selector,
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            write_web_kobe_graph(result.graph, output_path)
            if selector_trace_path is not None:
                selector_trace_path.parent.mkdir(parents=True, exist_ok=True)
                selector_trace_path.write_text(
                    json.dumps(
                        explorer.selection_traces,
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()


async def run_saucedemo_openai_selector_step(
    output_path: Path,
    *,
    selector_trace_path: Path | None = None,
    headless: bool = True,
    model: str | None = None,
    steps: int = 1,
) -> Path:
    provider = create_openai_chat_selection_provider_from_env(model=model)

    def action_selector(
        request: LlmActionSelectionRequest,
    ) -> LlmActionSelectionResult:
        return select_action_with_llm(request, provider=provider)

    return await run_saucedemo_llm_selector_step(
        output_path,
        selector_trace_path=selector_trace_path,
        headless=headless,
        steps=steps,
        action_selector=action_selector,
    )
