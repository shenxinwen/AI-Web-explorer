from ai_web_explorer.safesym_bridge.web_kobe_observer import (
    observe_web_kobe_page,
)


class FakeLocator:
    def __init__(self, text="", count_value=1, *, attr=None, visible=True):
        self._text = text
        self._count = count_value
        self._attr = attr
        self._visible = visible
        self.first = self

    def count(self):
        return self._count

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        if name == "data-state":
            return self._attr
        return None

    def is_visible(self):
        return self._visible

    def nth(self, index):
        return self


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


class FakeDataStateLocator:
    def __init__(self, locators):
        self._locators = locators

    def count(self):
        return len(self._locators)

    def nth(self, index):
        return self._locators[index]


class FakeDataStatePage(FakePage):
    def locator(self, selector):
        if selector == "[data-state]":
            return FakeDataStateLocator(
                [
                    FakeLocator("1", attr="cart-count", visible=True),
                    FakeLocator("Cart contains 1 item.", attr="cart-panel", visible=False),
                ]
            )
        return super().locator(selector)


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


def test_observe_web_kobe_page_extracts_data_state_indicators():
    observation = observe_web_kobe_page(FakeDataStatePage())

    assert observation.state_indicators == {
        "cart_count": 1,
        "cart_count_visible": True,
        "cart_panel": "Cart contains 1 item.",
        "cart_panel_visible": False,
    }
