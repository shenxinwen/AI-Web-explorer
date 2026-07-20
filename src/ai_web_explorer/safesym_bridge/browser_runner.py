from __future__ import annotations

import json
import socket
import time
import urllib.request
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
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
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
from ai_web_explorer.grounded_web.openai_visual_delta import (
    create_openai_visual_delta_provider_from_env,
)
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)
from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    create_async_stagehand_provider_from_env,
)


SAUCEDEMO_CHECKOUT_OVERVIEW_STAGEHAND_GOAL = (
    "Choose exactly one next low-level browser action for the SauceDemo "
    "checkout task. If the username field is empty, fill it with standard_user. "
    "If the username is filled and the password field is empty, fill it with "
    "secret_sauce. If both login fields are filled, click Login. After login, "
    "add one item to the cart, open the cart, start checkout, fill checkout "
    "information, and stop on checkout overview. Do not click Finish."
)
SAUCEDEMO_CHECKOUT_COMPLETE_STAGEHAND_GOAL = (
    "Choose exactly one next low-level browser action for the SauceDemo "
    "checkout task. If the username field is empty, fill it with standard_user. "
    "If the username is filled and the password field is empty, fill it with "
    "secret_sauce. If both login fields are filled, click Login. After login, "
    "add one item to the cart, open the cart, start checkout, fill checkout "
    "information, continue to checkout overview, click Finish, and stop when "
    "the checkout complete confirmation page is visible."
)
SAUCEDEMO_CHECKOUT_OVERVIEW_EXPLORER_GOAL = (
    "Reach SauceDemo checkout overview without placing the order."
)
SAUCEDEMO_CHECKOUT_COMPLETE_EXPLORER_GOAL = (
    "Complete the SauceDemo checkout flow through the confirmation page."
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


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_cdp_websocket_url(port: int, *, timeout_seconds: float = 5.0) -> str:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                data = json.loads(response.read().decode("utf-8"))
            websocket_url = data.get("webSocketDebuggerUrl")
            if websocket_url:
                return str(websocket_url)
        except Exception as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError(
        f"Chromium CDP websocket URL was not available at {url}."
    ) from last_error


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
    screenshot_dir: Path | None = None,
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
                screenshot_dir=screenshot_dir,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal=goal,
                action_selector=action_selector,
                capture_screenshots=screenshot_dir is not None,
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


async def run_saucedemo_stagehand_step(
    output_path: Path,
    *,
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 8,
    provider=None,
    model: str | None = None,
    screenshot_dir: Path | None = None,
    visual_delta_provider=None,
    use_openai_visual_delta: bool = False,
    visual_delta_model: str | None = None,
    allow_final_order: bool = False,
) -> Path:
    from playwright.async_api import async_playwright

    if (visual_delta_provider is not None or use_openai_visual_delta) and (
        screenshot_dir is None
    ):
        raise ValueError("screenshot_dir is required for visual delta analysis.")
    resolved_visual_delta_provider = visual_delta_provider
    if resolved_visual_delta_provider is None and use_openai_visual_delta:
        resolved_visual_delta_provider = create_openai_visual_delta_provider_from_env(
            model=visual_delta_model,
        )

    cdp_port = _pick_free_port() if provider is None else None
    launch_args = (
        [f"--remote-debugging-port={cdp_port}"] if cdp_port is not None else None
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=launch_args,
        )
        local_cdp_url = (
            _read_cdp_websocket_url(cdp_port) if cdp_port is not None else None
        )
        page = await browser.new_page()
        try:
            await page.goto("https://www.saucedemo.com/")
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                    page=page,
                    local_cdp_url=local_cdp_url,
                )
            base_adapter = WebKobePlaywrightAdapter(
                page,
                app_name="saucedemo",
                screenshot_dir=screenshot_dir,
            )
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=(
                    SAUCEDEMO_CHECKOUT_COMPLETE_STAGEHAND_GOAL
                    if allow_final_order
                    else SAUCEDEMO_CHECKOUT_OVERVIEW_STAGEHAND_GOAL
                ),
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="saucedemo"),
                goal=(
                    SAUCEDEMO_CHECKOUT_COMPLETE_EXPLORER_GOAL
                    if allow_final_order
                    else SAUCEDEMO_CHECKOUT_OVERVIEW_EXPLORER_GOAL
                ),
                capture_screenshots=screenshot_dir is not None,
                business_profile=(
                    ecommerce_checkout_profile()
                    if resolved_visual_delta_provider is not None
                    else None
                ),
                visual_delta_provider=resolved_visual_delta_provider,
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            graph = result.graph
            write_web_kobe_graph(graph, output_path)
            if stagehand_trace_path is not None:
                traces = graph.meta.get("stagehand_traces")
                if traces is None:
                    traces = [
                        edge.execution_trace.metadata
                        for edge in graph.edges
                        if edge.execution_trace.metadata.get("action_source")
                        == "stagehand"
                    ]
                stagehand_trace_path.parent.mkdir(parents=True, exist_ok=True)
                stagehand_trace_path.write_text(
                    json.dumps(traces, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()
