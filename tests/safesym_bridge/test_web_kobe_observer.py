from ai_web_explorer.safesym_bridge.web_kobe_observer import (
    observe_web_kobe_page,
)


class FakeLocator:
    def __init__(self, text="", count_value=1):
        self._text = text
        self._count = count_value
        self.first = self

    def count(self):
        return self._count

    def inner_text(self):
        return self._text


class FakePage:
    url = "https://example.test/products?utm_source=x"

    def title(self):
        return "Example Products"

    def locator(self, selector):
        if selector == "h1":
            return FakeLocator("Products")
        if selector == ".shopping_cart_badge":
            return FakeLocator("", count_value=0)
        return FakeLocator("", count_value=0)


def test_observe_web_kobe_page_extracts_basic_page_frame():
    observation = observe_web_kobe_page(
        FakePage(),
        web_state_id="ws-123",
        llm_title="Product listing",
    )

    assert observation.url == "https://example.test/products?utm_source=x"
    assert observation.url_pattern == "https://example.test/products"
    assert observation.browser_title == "Example Products"
    assert observation.heading == "Products"
    assert observation.web_state_id == "ws-123"
    assert observation.llm_title == "Product listing"
    assert observation.state_indicators == {}
    assert observation.evidence[0].source == "browser"
