import pytest

from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeTextLocator:
    def __init__(self, text: str, count_value: int = 1):
        self.text = text
        self.count_value = count_value

    async def count(self):
        return self.count_value

    @property
    def first(self):
        return self

    async def inner_text(self):
        return self.text


class FakeActionLocator:
    def __init__(
        self,
        *,
        count_value: int = 1,
        visible: bool = True,
        enabled: bool = True,
    ):
        self.clicked = False
        self.filled = []
        self.selected = []
        self.count_value = count_value
        self.visible = visible
        self.enabled = enabled
        self.scrolled = False

    @property
    def first(self):
        return self

    async def count(self):
        return self.count_value

    async def is_visible(self):
        return self.visible

    async def is_enabled(self):
        return self.enabled

    async def scroll_into_view_if_needed(self):
        self.scrolled = True

    async def click(self):
        self.clicked = True

    async def fill(self, value):
        self.filled.append(value)

    async def select_option(self, value):
        self.selected.append(value)


class FakeBodyLocator:
    async def evaluate(self, script):
        return {
            "regions": [],
            "controls": [],
            "forms": [],
            "indicators": [
                {
                    "id": "cart-count",
                    "indicator_type": "numeric",
                    "key_hint": "cart-count",
                    "value": "1",
                    "visible": True,
                    "locator": '[data-state="cart-count"]',
                    "text": "1",
                }
            ],
            "repeated_groups": [],
        }


class FakePage:
    def __init__(self, action_locator=None):
        self.url = "https://example.test/shop"
        self.action_locator = action_locator or FakeActionLocator()
        self.waits = []
        self.load_state_waits = []

    async def title(self):
        return "Fixture Shop"

    def locator(self, selector):
        if selector == "body":
            return FakeBodyLocator()
        if selector == "[data-state]":
            return FakeTextLocator("", count_value=0)
        if selector == '[data-state="cart-count"]':
            return FakeTextLocator("1")
        if selector == "#cart-count":
            return FakeTextLocator("", count_value=0)
        return self.action_locator

    async def wait_for_timeout(self, ms):
        self.waits.append(ms)

    async def wait_for_load_state(self, state, timeout=None):
        self.load_state_waits.append((state, timeout))


@pytest.mark.anyio
async def test_observe_state_reads_title_url_and_cart_count():
    adapter = WebKobePlaywrightAdapter(
        FakePage(),
        app_name="fixture",
        page_id="fixture_shop",
    )

    snapshot = await adapter.observe_state()

    assert snapshot.page_id == "fixture_shop"
    assert snapshot.url == "https://example.test/shop"
    assert snapshot.title == "Fixture Shop"
    assert snapshot.signature == {
        "url_path": "/shop",
        "cart_count": 1,
        "cart_count_visible": True,
    }


@pytest.mark.anyio
async def test_observe_state_uses_generic_structure_pipeline(monkeypatch):
    from ai_web_explorer.grounded_web.structure import (
        IndicatorObservation,
        PageInfo,
        PageStructureObservation,
        StructureEvidence,
    )

    async def fake_observe_page_structure(page, *, page_id=None):
        evidence = [StructureEvidence(source="dom_indicator", selector="#count")]
        return PageStructureObservation(
            page=PageInfo(
                url=page.url,
                title="Fixture Shop",
                page_id=page_id or "fixture_shop",
            ),
            indicators=[
                IndicatorObservation(
                    id="cart-count",
                    indicator_type="numeric",
                    key_hint="cart-count",
                    value=1,
                    visible=True,
                    locator="#count",
                    evidence=evidence,
                )
            ],
        )

    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.playwright_backend.observe_page_structure",
        fake_observe_page_structure,
    )
    adapter = WebKobePlaywrightAdapter(FakePage(), page_id="fixture_shop")

    snapshot = await adapter.observe_state()

    assert snapshot.signature["cart_count"] == 1
    assert adapter.last_structure_observation.page.page_id == "fixture_shop"
    assert adapter.last_state_facts[0].fact_type == "navigation"


@pytest.mark.anyio
async def test_list_interactables_uses_dom_candidates(monkeypatch):
    async def fake_extract_dom_interactables(page):
        return [
            DomInteractableCandidate(
                id="dom_001",
                kind="button",
                locator='button[data-test="add-to-cart"]',
                locator_strategy="css",
                name="Add to cart",
                visible=True,
                enabled=True,
                metadata={"data-test": "add-to-cart"},
            )
        ]

    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.playwright_backend.extract_dom_interactables",
        fake_extract_dom_interactables,
    )
    adapter = WebKobePlaywrightAdapter(FakePage(), page_id="fixture_shop")
    state = await adapter.observe_state()

    interactables = await adapter.list_interactables(state)

    assert interactables == [
        {
            "semantic_id": "dom_001_button_add_to_cart",
            "description": "Add to cart",
            "locator": 'button[data-test="add-to-cart"]',
            "locator_strategy": "css",
            "action_kind": "click",
            "input_values": {},
            "metadata": {"data-test": "add-to-cart"},
            "explored": False,
        }
    ]


@pytest.mark.anyio
async def test_saucedemo_adapter_reuses_saucedemo_state_observer(monkeypatch):
    async def fake_observe_saucedemo_state(page):
        return StateSnapshot(
            page_id="inventory",
            url="https://www.saucedemo.com/inventory.html",
            title="Swag Labs",
            signature={"is_logged_in": True, "cart_count": 0},
        )

    monkeypatch.setattr(
        "ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter.observe_saucedemo_state",
        fake_observe_saucedemo_state,
    )
    adapter = WebKobePlaywrightAdapter(FakePage(), app_name="saucedemo")

    snapshot = await adapter.observe_state()

    assert snapshot.page_id == "inventory"
    assert snapshot.signature == {"is_logged_in": True, "cart_count": 0}


@pytest.mark.anyio
async def test_saucedemo_adapter_uses_static_action_profile():
    adapter = WebKobePlaywrightAdapter(FakePage(), app_name="saucedemo")
    state = StateSnapshot(
        page_id="login",
        url="https://www.saucedemo.com/",
        title="Swag Labs",
        signature={"is_logged_in": False},
    )

    interactables = await adapter.list_interactables(state)

    assert interactables == [
        {
            "semantic_id": "login_submit",
            "description": "Click the Login button",
            "locator": "#login-button",
            "locator_strategy": None,
            "action_kind": "fill_then_click",
            "input_values": {
                "#user-name": "standard_user",
                "#password": "secret_sauce",
            },
            "metadata": {},
            "explored": False,
        }
    ]


@pytest.mark.anyio
async def test_execute_click_fill_and_select_actions():
    page = FakePage()
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    assert await adapter.execute(BrowserAction("click", "#add", "add")) is True
    assert page.action_locator.clicked is True

    assert (
        await adapter.execute(
            BrowserAction("fill", "#name", "fill_name", {"value": "Alice"})
        )
        is True
    )
    assert page.action_locator.filled == ["Alice"]

    assert (
        await adapter.execute(
            BrowserAction("select", "#sort", "select_sort", {"value": "price"})
        )
        is True
    )
    assert page.action_locator.selected == ["price"]

    assert (
        await adapter.execute(
            BrowserAction(
                "fill_then_click",
                "#submit",
                "submit_form",
                {"#username": "standard_user", "#password": "secret_sauce"},
            )
        )
        is True
    )
    assert page.action_locator.filled[-2:] == ["standard_user", "secret_sauce"]


@pytest.mark.anyio
async def test_execute_scrolls_target_and_waits_for_page_settle():
    locator = FakeActionLocator()
    page = FakePage(locator)
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#add", "add"))

    assert result is True
    assert locator.scrolled is True
    assert page.load_state_waits == [("domcontentloaded", 1000)]
    assert page.waits == [100]
    assert adapter.last_execution_error is None


@pytest.mark.anyio
async def test_execute_reports_locator_not_found():
    page = FakePage(FakeActionLocator(count_value=0))
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#missing", "missing"))

    assert result is False
    assert adapter.last_execution_error == "locator_not_found"


@pytest.mark.anyio
async def test_execute_reports_locator_not_visible():
    page = FakePage(FakeActionLocator(visible=False))
    adapter = WebKobePlaywrightAdapter(page, page_id="fixture_shop")

    result = await adapter.execute(BrowserAction("click", "#hidden", "hidden"))

    assert result is False
    assert adapter.last_execution_error == "locator_not_visible"
