from __future__ import annotations

import pytest

from ai_web_explorer.safesym_bridge.dom_observer import (
    DomInteractableCandidate,
    candidate_from_element,
    extract_dom_interactables,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_candidate_from_element_prefers_id_locator():
    candidate = candidate_from_element(
        1,
        {
            "tag": "button",
            "id": "finish",
            "data_test": "finish",
            "text": "Finish",
            "role": "button",
            "visible": True,
            "enabled": True,
        },
    )

    assert candidate == DomInteractableCandidate(
        id="dom_001",
        kind="button",
        locator="#finish",
        locator_strategy="id",
        name="Finish",
        visible=True,
        enabled=True,
        metadata={
            "tag": "button",
            "role": "button",
            "id": "finish",
            "data-test": "finish",
        },
    )


def test_candidate_from_element_uses_data_test_without_id():
    candidate = candidate_from_element(
        2,
        {
            "tag": "button",
            "data_test": "add-to-cart-sauce-labs-backpack",
            "text": "Add to cart",
            "visible": True,
            "enabled": True,
        },
    )

    assert candidate.id == "dom_002"
    assert candidate.kind == "button"
    assert candidate.locator == '[data-test="add-to-cart-sauce-labs-backpack"]'
    assert candidate.locator_strategy == "data-test"
    assert candidate.name == "Add to cart"
    assert candidate.metadata["data-test"] == "add-to-cart-sauce-labs-backpack"


def test_candidate_from_element_uses_generated_candidate_id_fallback():
    candidate = candidate_from_element(
        3,
        {
            "tag": "a",
            "candidate_id": "dom_003",
            "text": "Cart",
            "href": "/cart.html",
            "visible": True,
            "enabled": True,
        },
    )

    assert candidate.kind == "link"
    assert candidate.locator == '[data-web-kobe-id="dom_003"]'
    assert candidate.locator_strategy == "generated-id"
    assert candidate.name == "Cart"
    assert candidate.metadata["href"] == "/cart.html"


def test_candidate_from_element_preserves_select_option_values():
    candidate = candidate_from_element(
        4,
        {
            "tag": "select",
            "id": "topic",
            "text": "Topic",
            "visible": True,
            "enabled": True,
            "option_values": ["", "alpha", "beta"],
        },
    )

    assert candidate.kind == "select"
    assert candidate.locator == "#topic"
    assert candidate.metadata["option-values"] == "alpha,beta"


class FakeLocator:
    async def evaluate_all(self, script):
        return [
            {
                "tag": "button",
                "id": "finish",
                "data_test": "finish",
                "text": "Finish",
                "visible": True,
                "enabled": True,
            },
            {
                "tag": "button",
                "id": "hidden",
                "text": "Hidden",
                "visible": False,
                "enabled": True,
            },
        ]


class FakePage:
    def locator(self, selector):
        assert "button" in selector
        return FakeLocator()


@pytest.mark.anyio
async def test_extract_dom_interactables_filters_hidden_candidates():
    candidates = await extract_dom_interactables(FakePage())

    assert [candidate.locator for candidate in candidates] == ["#finish"]
