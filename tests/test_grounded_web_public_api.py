from ai_web_explorer.grounded_web import (
    AutomationBackend,
    BrowserAction,
    WebKobeExplorationController,
    WebKobeExplorer,
    WebKobeGraph,
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.grounded_web.action_extractor import (
    browser_actions_from_candidates,
)
from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate
from ai_web_explorer.grounded_web.playwright_backend import PlaywrightBackend
from ai_web_explorer.grounded_web.state_signature import schema_delta


def test_grounded_web_package_exposes_mainline_api():
    assert AutomationBackend.__name__ == "AutomationBackend"
    assert BrowserAction.__name__ == "BrowserAction"
    assert WebKobeExplorationController.__name__ == "WebKobeExplorationController"
    assert WebKobeExplorer.__name__ == "WebKobeExplorer"
    assert WebKobeGraph.__name__ == "WebKobeGraph"
    assert WebKobePlaywrightAdapter.__name__ == "WebKobePlaywrightAdapter"
    assert PlaywrightBackend is WebKobePlaywrightAdapter


def test_grounded_web_imports_can_build_grounded_action():
    candidate = DomInteractableCandidate(
        id="dom_001",
        kind="button",
        locator="#add",
        locator_strategy="id",
        name="Add to cart",
        visible=True,
        enabled=True,
    )

    actions = browser_actions_from_candidates([candidate])

    assert actions == [
        BrowserAction(
            action_kind="click",
            locator="#add",
            semantic_id="dom_001_button_add_to_cart",
            description="Add to cart",
        )
    ]


def test_grounded_web_state_signature_is_available_from_mainline_package():
    assert schema_delta({"cart_count": 0}, {"cart_count": 1}) == {
        "cart_count": {"before": 0, "after": 1}
    }
