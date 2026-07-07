from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.graph_explorer import GraphExplorer
from ai_web_explorer.safesym_bridge.graph_exporter import graph_to_fsm
from ai_web_explorer.safesym_bridge.models import ObservedTransition
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
from ai_web_explorer.safesym_bridge.saucedemo_adapter import SauceDemoAdapter
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def write_observed_graph(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=transitions,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


# transitions --> fsm
def write_observed_fsm(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=transitions,
    )
    fsm = graph_to_fsm(graph, terminal_pages=["checkout_complete"])
    validation = validate_fsm(fsm)
    if not validation.ok:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Observed FSM failed validation: {joined}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


async def run_saucedemo_observed_flow(
    output_path: Path,
    *,
    headless: bool = True,
) -> Path:
    from playwright.async_api import async_playwright

    from ai_web_explorer.safesym_bridge.transition_recorder import record_transition

    transitions: list[ObservedTransition] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto("https://www.saucedemo.com/")
            await page.fill("#user-name", "standard_user")
            await page.fill("#password", "secret_sauce")

            transitions.append(
                await record_transition(
                    page,
                    "Click the Login button",
                    lambda: page.click("#login-button"),
                )
            )
            transitions.append(
                await record_transition(
                    page,
                    "Click Add to cart",
                    lambda: page.click('[data-test="add-to-cart-sauce-labs-backpack"]'),
                )
            )
            transitions.append(
                await record_transition(
                    page,
                    "Click the shopping cart link",
                    lambda: page.click(".shopping_cart_link"),
                )
            )
            transitions.append(
                await record_transition(
                    page,
                    "Click Checkout",
                    lambda: page.click("#checkout"),
                )
            )

            await page.fill("#first-name", "Safe")
            await page.fill("#last-name", "Sym")
            await page.fill("#postal-code", "12345")

            transitions.append(
                await record_transition(
                    page,
                    "Click Continue on checkout information",
                    lambda: page.click("#continue"),
                )
            )
            transitions.append(
                await record_transition(
                    page,
                    "Click Finish",
                    lambda: page.click("#finish"),
                )
            )

            return write_observed_fsm(transitions, output_path)
        finally:
            await browser.close()


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
