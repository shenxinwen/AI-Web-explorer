import os
import json
import subprocess
from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.controller import WebKobeExplorationController
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import FrontierReplayRunner
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.safesym_bridge.browser_runner import run_web_kobe_exploration
from ai_web_explorer.safesym_bridge.surface_pddl import (
    compile_surface_domain,
    compile_surface_problem,
)
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import (
    analyze_web_kobe_safesym_smoke,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


FIXTURE_HTML = """
<!doctype html>
<html>
  <head><title>Fixture Shop</title></head>
  <body>
    <main>
      <h1>Fixture Shop</h1>
      <p>Cart: <span id="cart-count" data-state="cart-count">0</span></p>
      <section class="product-card">
        <h2>Example Product</h2>
        <button id="add-to-cart" data-test="add-to-cart">Add to cart</button>
      </section>
    </main>
    <script>
      document.querySelector("#add-to-cart").addEventListener("click", () => {
        document.querySelector("#cart-count").textContent = "1";
      });
    </script>
  </body>
</html>
"""


FRONTIER_REPLAY_FIXTURE_HTML = """
<!doctype html>
<html><head><title>Frontier Fixture</title></head>
<body data-surface="shopping" data-filtered="false">
  <main>
    <h1>Frontier Fixture</h1>
    <p data-state="surface">shopping</p>
    <button id="open-product">Open product</button>
    <button id="sort">Sort</button>
    <button id="filter">Filter</button>
    <button id="inspect-product">Inspect product</button>
  </main>
  <script>
    const surface = value => {
      document.body.dataset.surface = value;
      document.querySelector('[data-state="surface"]').textContent = value;
    };
    document.querySelector('#open-product').onclick = () => surface('product');
    document.querySelector('#inspect-product').onclick = () => surface('product');
    document.querySelector('#sort').onclick = () => surface('checkout');
    document.querySelector('#filter').onclick = () => {
      document.body.dataset.filtered = 'true';
      surface('shopping');
    };
  </script>
</body></html>
"""


class _FrontierFixtureAdapter(WebKobePlaywrightAdapter):
    def __init__(self, page, *, screenshot_dir):
        async def state_observer(current_page):
            return StateSnapshot(
                page_id=await current_page.locator("body").get_attribute("data-surface"),
                url="http://fixture.test/shop",
                title="Frontier Fixture",
                signature={
                    "surface": await current_page.locator("body").get_attribute(
                        "data-surface"
                    ),
                    "filtered": (
                        await current_page.locator("body").get_attribute("data-filtered")
                    )
                    == "true",
                },
            )

        def action_provider(state):
            actions = {
                "shopping": [
                    BrowserAction("click", "#open-product", "open_product"),
                    BrowserAction("click", "#sort", "sort"),
                    BrowserAction("click", "#filter", "filter"),
                ],
                "product": [
                    BrowserAction("click", "#inspect-product", "inspect_product"),
                ],
                "checkout": [],
            }
            return actions.get(state.signature.get("surface"), [])

        super().__init__(
            page,
            app_name="fixture",
            state_observer=state_observer,
            action_provider=action_provider,
            screenshot_dir=screenshot_dir,
        )

    async def reset_to(self, url: str) -> bool:
        await self.page.set_content(FRONTIER_REPLAY_FIXTURE_HTML)
        await self.page.wait_for_timeout(100)
        return True

    async def execute(self, action):
        locators = {
            "open_product": "#open-product",
            "inspect_product": "#inspect-product",
            "sort": "#sort",
            "filter": "#filter",
        }
        return await super().execute(replace(action, locator=locators[action.semantic_id]))


class _FrontierFixtureSemanticAssistor(DeterministicSemanticAssistor):
    def describe_state(self, *, snapshot, interactables):
        draft = super().describe_state(
            snapshot=snapshot,
            interactables=interactables,
        )
        label = str(snapshot.signature.get("surface"))
        return replace(
            draft,
            page_description=f"{label} surface",
            node_label=label,
            state_summary=f"{label} surface",
        )


class _FixtureSafeSymRunner:
    def __init__(self, task_dir):
        self.task_dir = task_dir

    def __call__(self, command, **kwargs):
        command = [str(item) for item in command]
        if command[-1] == "parse":
            return subprocess.CompletedProcess(command, 0, "parse ok", "")
        if "inject_safety" in command:
            (self.task_dir / "safe_domain.pddl").write_text(
                (self.task_dir / "domain.pddl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (self.task_dir / "safe_problem.pddl").write_text(
                (self.task_dir / "problem.pddl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "injected", "")
        if "safeww.cli.solve" in command:
            plan_name = "safe_sas_plan" if "--safe" in command else "sas_plan"
            (self.task_dir / plan_name).write_text(
                "(go_goal )\n; cost = 1 (unit cost)\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "solved", "")
        raise AssertionError(command)


@pytest.mark.skipif(
    os.getenv("RUN_WEB_KOBE_BROWSER_TEST") != "1",
    reason="Set RUN_WEB_KOBE_BROWSER_TEST=1 to run the real Web-KOBE browser test.",
)
@pytest.mark.anyio
async def test_playwright_web_kobe_explorer_records_real_self_loop_delta():
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_content(FIXTURE_HTML)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="fixture",
                page_id="fixture_shop",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app="fixture"),
            )

            graph = await explorer.explore_one_step()

            assert graph.start_node_id.startswith("fixture_shop__")
            assert len(graph.edges) == 1
            edge = graph.edges[0]
            assert edge.source_node_id.startswith("fixture_shop__")
            assert edge.target_node_id.startswith("fixture_shop__")
            assert edge.source_node_id != edge.target_node_id
            assert edge.schema_delta == {
                "cart_count": {"before": 0, "after": 1},
                "cart_has_items": {"before": False, "after": True},
            }
            assert {
                delta.field: (delta.before, delta.after)
                for delta in edge.observed_delta
            } == {
                "cart_count": (0, 1),
                "cart_has_items": (False, True),
            }
        finally:
            await browser.close()


@pytest.mark.skipif(
    os.getenv("RUN_WEB_KOBE_BROWSER_TEST") != "1",
    reason="Set RUN_WEB_KOBE_BROWSER_TEST=1 to run the local browser fixture.",
)
@pytest.mark.anyio
async def test_frontier_replay_surface_pddl_local_fixture(tmp_path):
    from playwright.async_api import async_playwright

    candidates_seen = 0

    def visual_provider(prompt, *, current_screenshot_path=None, **kwargs):
        nonlocal candidates_seen
        if current_screenshot_path is None:
            return (
                '{"visible_change_summary":"observed",'
                '"candidate_added_facts":[],"candidate_removed_facts":[],'
                '"evidence":[],"confidence":0.5}'
            )
        candidates_seen += 1
        candidates = {
            1: ["open_product", "sort", "filter"],
            2: ["inspect_product"],
        }.get(candidates_seen, [])
        return json.dumps(
            {
                "business_affordances": [
                    {
                        "action_name": action,
                        "label": action,
                        "relevance_hint": "core",
                        "confidence": 0.9,
                    }
                    for action in candidates
                ],
                "state_summary": "fixture surface",
            }
        )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_content(FRONTIER_REPLAY_FIXTURE_HTML)
            adapter = _FrontierFixtureAdapter(
                page,
                screenshot_dir=tmp_path / "screenshots",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=_FrontierFixtureSemanticAssistor(app="fixture"),
                visual_delta_provider=visual_provider,
                capture_screenshots=True,
                business_profile=None,
                max_candidates=5,
            )
            replay_target_ids = []
            replay_paths = []
            replay_runner = FrontierReplayRunner(explorer)

            class RecordingReplayRunner:
                async def replay(self, target, *, start_url):
                    replay_target_ids.append(target.node_id)
                    replay_paths.append(tuple(target.path))
                    return await replay_runner.replay(target, start_url=start_url)

            controller = WebKobeExplorationController(
                explorer,
                max_consecutive_unproductive_steps=None,
                frontier_replay_runner=RecordingReplayRunner(),
                start_url="http://fixture.test/shop",
            )
            result = await controller.run(max_steps=4)

            assert explorer.max_candidates == 5
            assert result.graph.meta["replay_success_count"] >= 1
            assert replay_target_ids[0] == result.graph.start_node_id
            assert replay_paths[0] == ()
            assert any(
                edge.target_node_id
                and next(
                    node.page_frame.page_type
                    for node in result.graph.nodes
                    if node.node_id == edge.target_node_id
                )
                == "checkout"
                for edge in result.graph.edges
            )
            sibling_sources = {
                edge.source_node_id
                for edge in result.graph.edges
                if edge.action.semantic_id in {"filter", "sort"}
            }
            assert len(sibling_sources) == 1
            assert {
                edge.action.semantic_id
                for edge in result.graph.edges
                if edge.action.semantic_id in {"filter", "sort"}
            } == {"filter", "sort"}

            checkout_id = next(
                node.node_id
                for node in result.graph.nodes
                if node.page_frame.page_type == "checkout"
            )
            surface_domain = compile_surface_domain(result.graph)
            surface_problem = compile_surface_problem(
                result.graph,
                goal_node_id=checkout_id,
            )
            task_dir = tmp_path / "surface_pddl"
            task_dir.mkdir()
            (task_dir / "domain.pddl").write_text(
                surface_domain.domain,
                encoding="utf-8",
            )
            (task_dir / "problem.pddl").write_text(
                surface_problem.problem,
                encoding="utf-8",
            )
            rules = tmp_path / "rules.json"
            rules.write_text("[]", encoding="utf-8")
            fast_downward = tmp_path / "fast-downward.py"
            fast_downward.write_text("# fixture", encoding="utf-8")
            safesym_result = analyze_web_kobe_safesym_smoke(
                task_dir,
                safesym_root=tmp_path / "SafeSym",
                rules=rules,
                fast_downward=fast_downward,
                runner=_FixtureSafeSymRunner(task_dir),
                python_executable="python",
            )
            assert safesym_result.safe_plan_ready is True
            assert "checkpoint" not in surface_domain.domain
        finally:
            await browser.close()


@pytest.mark.skipif(
    os.getenv("RUN_WEB_KOBE_SAUCEDEMO_TEST") != "1",
    reason=(
        "Set RUN_WEB_KOBE_SAUCEDEMO_TEST=1 to run the real SauceDemo "
        "Web-KOBE browser test."
    ),
)
@pytest.mark.anyio
async def test_saucedemo_web_kobe_runner_records_real_checkout_prefix(tmp_path):
    output_path = tmp_path / "saucedemo_web_kobe_graph.json"

    result_path = await run_web_kobe_exploration(
        "https://www.saucedemo.com/",
        output_path,
        app_name="saucedemo",
        steps=4,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"

    node_ids = {node["node_id"] for node in data["nodes"]}
    action_ids = {edge["action"]["semantic_id"] for edge in data["edges"]}

    assert {"login", "inventory", "cart", "checkout_info"}.issubset(node_ids)
    assert {
        "login_submit",
        "product_add_to_cart",
        "cart_open",
        "cart_checkout_start",
    }.issubset(action_ids)
    assert any(
        edge["schema_delta"]
        and edge["schema_delta"].get("cart_count") == {"before": 0, "after": 1}
        for edge in data["edges"]
    )
