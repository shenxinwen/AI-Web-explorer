from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.saucedemo_resolver import (
    SauceDemoRuleResolver,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(page_id: str) -> StateSnapshot:
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title=page_id,
        signature={},
    )


def candidate(
    *,
    candidate_id: str,
    locator: str,
    name: str,
    metadata: dict[str, str],
    kind: str = "button",
) -> DomInteractableCandidate:
    return DomInteractableCandidate(
        id=candidate_id,
        kind=kind,
        locator=locator,
        locator_strategy="test",
        name=name,
        visible=True,
        enabled=True,
        metadata=metadata,
    )


async def test_resolver_matches_login_without_execution_details():
    resolver = SauceDemoRuleResolver()
    login = candidate(
        candidate_id="dom_login",
        locator="#login-button",
        name="Login",
        metadata={"id": "login-button", "data-test": "login-button"},
    )

    batch = await resolver.resolve(snapshot("login"), [login])

    assert [(match.candidate_id, match.semantic_id) for match in batch.matches] == [
        ("dom_login", "login_submit")
    ]
    assert batch.matches[0].confidence == 1.0
    assert batch.matches[0].resolver == "saucedemo_rule"
    assert batch.unmatched_candidate_ids == []


async def test_resolver_reports_unknown_candidate():
    resolver = SauceDemoRuleResolver()
    unknown = candidate(
        candidate_id="dom_unknown",
        locator="#help",
        name="Help",
        metadata={"id": "help"},
    )

    batch = await resolver.resolve(snapshot("inventory"), [unknown])

    assert batch.matches == []
    assert batch.unmatched_candidate_ids == ["dom_unknown"]


@pytest.mark.parametrize(
    ("page_id", "token", "semantic_id"),
    [
        ("inventory", "add-to-cart-sauce-labs-backpack", "product_add_to_cart"),
        ("inventory", "shopping-cart-link", "cart_open"),
        ("cart", "checkout", "cart_checkout_start"),
        ("checkout_info", "continue", "checkout_info_submit"),
        ("checkout_overview", "finish", "order_place_confirm"),
    ],
)
async def test_resolver_matches_checkout_path(page_id, token, semantic_id):
    resolver = SauceDemoRuleResolver()
    source = candidate(
        candidate_id=f"dom_{token}",
        locator=f'[data-test="{token}"]',
        name=token,
        metadata={"data-test": token},
    )

    batch = await resolver.resolve(snapshot(page_id), [source])

    assert [match.semantic_id for match in batch.matches] == [semantic_id]
    assert batch.unmatched_candidate_ids == []
