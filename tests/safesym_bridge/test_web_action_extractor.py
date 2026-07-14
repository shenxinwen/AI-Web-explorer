from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_action_extractor import (
    browser_actions_from_candidates,
)


def test_browser_actions_from_candidates_preserves_grounding():
    candidates = [
        DomInteractableCandidate(
            id="dom_001",
            kind="button",
            locator='button[data-test="checkout"]',
            locator_strategy="css",
            name="Checkout",
            visible=True,
            enabled=True,
            metadata={"id": "checkout"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert len(actions) == 1
    assert actions[0].action_kind == "click"
    assert actions[0].locator == 'button[data-test="checkout"]'
    assert actions[0].semantic_id == "button_checkout"
    assert actions[0].description == "Checkout"
