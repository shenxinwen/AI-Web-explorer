from pathlib import Path

from playwright.sync_api import sync_playwright


FIXTURE_PATH = Path("tests/fixtures/local_shop/index.html")


def test_local_shop_fixture_supports_cart_state_changes():
    assert FIXTURE_PATH.exists()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(FIXTURE_PATH.resolve().as_uri())

            assert page.locator("[data-state='cart-count']").inner_text() == "0"
            assert page.locator("[data-state='cart-panel']").is_hidden()

            page.locator("[data-action='add-to-cart']").first.click()
            assert page.locator("[data-state='cart-count']").inner_text() == "1"

            page.locator("[data-action='open-cart']").click()
            assert page.locator("[data-state='cart-panel']").is_visible()
            assert page.locator("[data-state='cart-panel']").inner_text() == (
                "Cart contains 1 item."
            )
        finally:
            browser.close()
