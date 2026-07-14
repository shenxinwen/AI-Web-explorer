import os

import pytest

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

            assert graph.start_node_id == "fixture_shop"
            assert len(graph.edges) == 1
            edge = graph.edges[0]
            assert edge.source_node_id == "fixture_shop"
            assert edge.target_node_id == "fixture_shop"
            assert edge.schema_delta == {
                "cart_count": {"before": 0, "after": 1},
                "cart_nonempty": {"before": False, "after": True},
            }
            assert {
                delta.field: (delta.before, delta.after)
                for delta in edge.observed_delta
            } == {
                "cart_count": (0, 1),
                "cart_nonempty": (False, True),
            }
        finally:
            await browser.close()
