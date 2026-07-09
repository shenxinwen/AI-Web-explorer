from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.action_catalog import (
    ActionDefinition,
    DomainActionCatalog,
)
from ai_web_explorer.safesym_bridge.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.semantic_resolver import SemanticMatch


def snapshot(page_id: str) -> StateSnapshot:
    return StateSnapshot(page_id, "", page_id, {})


def candidate(candidate_id: str, locator: str) -> DomInteractableCandidate:
    return DomInteractableCandidate(
        id=candidate_id,
        kind="button",
        locator=locator,
        locator_strategy="test",
        name="",
        visible=True,
        enabled=True,
        metadata={},
    )


def test_catalog_builds_action_from_match_and_candidate():
    catalog = DomainActionCatalog(
        {
            ("login", "login_submit"): ActionDefinition(
                raw_description="Click Login",
                execution_kind="fill_then_click",
                values={"#user": "standard_user"},
                position="login form",
                priority=0,
            )
        }
    )

    actions = catalog.build_actions(
        snapshot("login"),
        [SemanticMatch("dom_login", "login_submit", 1.0, "rule")],
        [candidate("dom_login", "#login-button")],
    )

    assert actions[0].semantic_id == "login_submit"
    assert actions[0].selector == "#login-button"
    assert actions[0].values == {"#user": "standard_user"}


def test_catalog_rejects_missing_candidate():
    catalog = DomainActionCatalog({})

    with pytest.raises(ValueError, match="Missing candidate: missing"):
        catalog.build_actions(
            snapshot("login"),
            [SemanticMatch("missing", "login_submit", 1.0, "rule")],
            [],
        )


def test_catalog_rejects_missing_definition():
    catalog = DomainActionCatalog({})

    with pytest.raises(
        ValueError,
        match="Missing action definition: login/login_submit",
    ):
        catalog.build_actions(
            snapshot("login"),
            [SemanticMatch("dom_login", "login_submit", 1.0, "rule")],
            [candidate("dom_login", "#login-button")],
        )


def test_catalog_skips_low_confidence_match():
    catalog = DomainActionCatalog(
        {
            ("login", "login_submit"): ActionDefinition(
                raw_description="Click Login",
                execution_kind="click",
            )
        }
    )

    actions = catalog.build_actions(
        snapshot("login"),
        [SemanticMatch("dom_login", "login_submit", 0.9, "llm")],
        [candidate("dom_login", "#login-button")],
    )

    assert actions == []


def test_catalog_sorts_by_definition_priority():
    catalog = DomainActionCatalog(
        {
            ("inventory", "open_cart"): ActionDefinition(
                raw_description="Open cart",
                execution_kind="click",
                priority=1,
            ),
            ("inventory", "add_product"): ActionDefinition(
                raw_description="Add product",
                execution_kind="click",
                priority=0,
            ),
        }
    )

    actions = catalog.build_actions(
        snapshot("inventory"),
        [
            SemanticMatch("cart", "open_cart", 1.0, "rule"),
            SemanticMatch("add", "add_product", 1.0, "rule"),
        ],
        [candidate("cart", "#cart"), candidate("add", "#add")],
    )

    assert [action.semantic_id for action in actions] == [
        "add_product",
        "open_cart",
    ]
