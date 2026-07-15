from playwright.sync_api import sync_playwright

from ai_web_explorer import html


def test_js_helpers_are_available_after_init_script():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.add_init_script(html.JS_FUNCTIONS)
            page.goto("data:text/html,<input value='demo'>")

            result = html.get_full_html(page, minified=True)

            assert 'data-current-value="demo"' in result
        finally:
            browser.close()
