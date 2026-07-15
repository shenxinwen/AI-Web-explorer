from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate
from ai_web_explorer.grounded_web.action_extractor import (
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
    assert actions[0].semantic_id == "dom_001_button_checkout"
    assert actions[0].description == "Checkout"


def test_browser_actions_from_email_input_uses_stable_email_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_002",
            kind="input",
            locator="#email",
            locator_strategy="id",
            name="Email",
            visible=True,
            enabled=True,
            metadata={"type": "email", "placeholder": "Email address"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].action_kind == "fill"
    assert actions[0].input_values == {"#email": "test@example.com"}


def test_browser_actions_from_password_input_uses_stable_password_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_003",
            kind="input",
            locator="#password",
            locator_strategy="id",
            name="Password",
            visible=True,
            enabled=True,
            metadata={"type": "password"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].input_values == {"#password": "secret_sauce"}


def test_browser_actions_from_search_input_uses_search_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_004",
            kind="input",
            locator="#query",
            locator_strategy="id",
            name="Search",
            visible=True,
            enabled=True,
            metadata={"type": "search", "placeholder": "Search products"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].input_values == {"#query": "sample"}


def test_browser_actions_from_select_candidate_uses_first_option_value():
    candidates = [
        DomInteractableCandidate(
            id="dom_003",
            kind="select",
            locator="#topic",
            locator_strategy="id",
            name="Topic",
            visible=True,
            enabled=True,
            metadata={"option-values": "alpha,beta"},
        )
    ]

    actions = browser_actions_from_candidates(candidates)

    assert actions[0].action_kind == "select"
    assert actions[0].input_values == {"#topic": "alpha"}
