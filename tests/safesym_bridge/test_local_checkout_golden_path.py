from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.controller import WebKobeExplorationController
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionResult,
    LlmActionSelectionTrace,
)
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _node_with_state(graph, key: str, value: object):
    for node in graph.nodes:
        if node.last_state_snapshot.get(key) == value:
            return node
    return None


def _local_checkout_selector(request):
    state = request.state.signature
    target_locator_fragment = None
    if state.get("cart_count") == 0:
        target_locator_fragment = "add-to-cart"
    elif state.get("checkout_step") == 1:
        target_locator_fragment = "begin-checkout"
    elif state.get("name_filled") == 0:
        target_locator_fragment = "customer-name"
    elif state.get("email_filled") == 0:
        target_locator_fragment = "customer-email"
    elif state.get("address_filled") == 0:
        target_locator_fragment = "shipping-address"
    elif state.get("checkout_info_complete") == 1:
        target_locator_fragment = "place-order"

    selected = next(
        (
            action
            for action in request.candidate_actions
            if target_locator_fragment
            and target_locator_fragment in str(action.locator)
        ),
        request.candidate_actions[0],
    )
    return LlmActionSelectionResult(
        selected_action=selected,
        trace=LlmActionSelectionTrace(
            goal=request.goal,
            state={"page_id": request.state.page_id},
            candidate_actions=[
                {"id": action.semantic_id}
                for action in request.candidate_actions
            ],
            prompt="deterministic local_checkout selector",
            raw_response=f'{{"selected_action_id":"{selected.semantic_id}"}}',
            llm_response={"selected_action_id": selected.semantic_id},
            status="selected",
        ),
    )


@pytest.mark.anyio
async def test_local_checkout_explores_order_flow_and_writes_planning_smoke(
    tmp_path,
):
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_checkout/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="local_checkout",
                page_id="local_checkout",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(
                    app="local_checkout"
                ),
                goal="Complete the local checkout flow.",
                action_selector=_local_checkout_selector,
            )
            controller = WebKobeExplorationController(explorer)

            result = await controller.run(max_steps=6)
            graph = result.graph

            assert graph.total_steps_completed == 6
            assert len(graph.nodes) >= 4
            assert len(graph.edges) >= 4
            assert graph.start_node_id == graph.edges[0].source_node_id

            start = _node_with_state(graph, "cart_count", 0)
            assert start is not None
            assert graph.start_node_id == start.node_id

            delta_fields = {
                delta.field
                for edge in graph.edges
                for delta in edge.observed_delta
            }
            assert "cart_count" in delta_fields
            assert "checkout_step" in delta_fields
            assert "order_created" in delta_fields

            goal = _node_with_state(graph, "order_created", 1)
            assert goal is not None

            smoke = write_web_kobe_pddl_smoke(
                graph,
                tmp_path / "pddl_smoke",
                goal_node_id=goal.node_id,
            )

            assert smoke.report.planning_ready is True
            assert smoke.report.goal_reachable_in_graph is True
            assert smoke.report.projected_action_count >= 4
            assert "(:action" in smoke.artifacts.domain
            assert "(:goal" in smoke.artifacts.problem
        finally:
            await browser.close()
