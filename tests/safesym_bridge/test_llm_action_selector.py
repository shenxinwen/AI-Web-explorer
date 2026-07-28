import pytest

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionRequest,
    select_action_with_llm,
)
from ai_web_explorer.grounded_web.models import StateSnapshot


def _inventory_state(cart_count=0):
    return StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={
            "is_logged_in": True,
            "cart_count": cart_count,
            "order_created": False,
        },
    )


def _candidate_actions():
    return [
        BrowserAction(
            action_kind="click",
            locator='[data-test="add-to-cart-sauce-labs-backpack"]',
            semantic_id="product_add_to_cart",
            description="Click Add to cart",
        ),
        BrowserAction(
            action_kind="click",
            locator=".shopping_cart_link",
            semantic_id="cart_open",
            description="Click the shopping cart link",
        ),
    ]


def test_select_action_with_llm_accepts_valid_candidate_json():
    def provider(prompt):
        assert "product_add_to_cart" in prompt
        assert "cart_open" in prompt
        return (
            '{"selected_action_id":"product_add_to_cart",'
            '"confidence":0.91,'
            '"reason":"Cart is empty, so add a product first."}'
        )

    result = select_action_with_llm(
        LlmActionSelectionRequest(
            goal="Complete a checkout order.",
            state=_inventory_state(cart_count=0),
            candidate_actions=_candidate_actions(),
        ),
        provider=provider,
    )

    assert result.selected_action.semantic_id == "product_add_to_cart"
    assert result.trace.status == "selected"
    assert result.trace.error_type is None
    assert result.trace.llm_response["reason"] == (
        "Cart is empty, so add a product first."
    )


def test_select_action_with_llm_rejects_action_not_in_candidates():
    result = select_action_with_llm(
        LlmActionSelectionRequest(
            goal="Complete a checkout order.",
            state=_inventory_state(),
            candidate_actions=_candidate_actions(),
        ),
        provider=lambda prompt: (
            '{"selected_action_id":"checkout_submit",'
            '"confidence":0.5,'
            '"reason":"Move forward."}'
        ),
    )

    assert result.selected_action is None
    assert result.trace.status == "failed"
    assert result.trace.error_type == "invalid_action"
    assert result.trace.llm_response["selected_action_id"] == "checkout_submit"


def test_select_action_with_llm_records_malformed_json():
    result = select_action_with_llm(
        LlmActionSelectionRequest(
            goal="Complete a checkout order.",
            state=_inventory_state(),
            candidate_actions=_candidate_actions(),
        ),
        provider=lambda prompt: "choose add to cart",
    )

    assert result.selected_action is None
    assert result.trace.status == "failed"
    assert result.trace.error_type == "parse_error"
    assert result.trace.raw_response == "choose add to cart"


def test_select_action_with_llm_returns_no_candidates_failure():
    result = select_action_with_llm(
        LlmActionSelectionRequest(
            goal="Complete a checkout order.",
            state=_inventory_state(),
            candidate_actions=[],
        ),
        provider=lambda prompt: pytest.fail("provider should not be called"),
    )

    assert result.selected_action is None
    assert result.trace.status == "failed"
    assert result.trace.error_type == "no_candidates"


def test_select_action_prompt_includes_exploration_context():
    prompts = []

    def provider(prompt: str) -> str:
        prompts.append(prompt)
        return '{"selected_action_id":"open_search"}'

    request = LlmActionSelectionRequest(
        goal="Explore useful website functionality.",
        state=StateSnapshot("home", "https://shop.test/", "Home", {}),
        candidate_actions=[
            BrowserAction("click", "#search", "open_search", description="Open search")
        ],
        exploration_context={
            "prompt_block": "Avoid repeating actions: theme_toggle",
            "avoid_action_ids": ["theme_toggle"],
        },
    )

    result = select_action_with_llm(request, provider=provider)

    assert result.selected_action.semantic_id == "open_search"
    assert "Avoid repeating actions: theme_toggle" in prompts[0]
    assert result.trace.exploration_context == {
        "prompt_block": "Avoid repeating actions: theme_toggle",
        "avoid_action_ids": ["theme_toggle"],
    }
