from ai_web_explorer.grounded_web import (
    AutomationBackend,
    BrowserAction,
    BusinessFlowProfile,
    OpenAIVisualDeltaProvider,
    PlanningDelta,
    VisualDeltaProvider,
    VisualDeltaRequest,
    WebKobeExplorationController,
    WebKobeExplorer,
    WebKobeGraph,
    WebKobePlaywrightAdapter,
    create_openai_visual_delta_provider_from_env,
    ecommerce_checkout_profile,
    summarize_visual_delta,
    verify_planning_delta,
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
    assert BusinessFlowProfile.__name__ == "BusinessFlowProfile"
    assert OpenAIVisualDeltaProvider.__name__ == "OpenAIVisualDeltaProvider"
    assert PlanningDelta.__name__ == "PlanningDelta"
    assert VisualDeltaProvider is not None
    assert VisualDeltaRequest.__name__ == "VisualDeltaRequest"
    assert WebKobeExplorationController.__name__ == "WebKobeExplorationController"
    assert WebKobeExplorer.__name__ == "WebKobeExplorer"
    assert WebKobeGraph.__name__ == "WebKobeGraph"
    assert WebKobePlaywrightAdapter.__name__ == "WebKobePlaywrightAdapter"
    assert PlaywrightBackend is WebKobePlaywrightAdapter
    assert callable(create_openai_visual_delta_provider_from_env)
    assert ecommerce_checkout_profile().site_type == "ecommerce_checkout"
    assert callable(summarize_visual_delta)
    assert callable(verify_planning_delta)


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
