from __future__ import annotations

from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate
from ai_web_explorer.safesym_bridge.web_observation import (
    ObservedFact,
    ObservationEvidence,
    PageIdentity,
    WebObservation,
)


def test_web_observation_exports_signature_values() -> None:
    observation = WebObservation(
        identity=PageIdentity(
            page_id="cart",
            url="https://www.saucedemo.com/cart.html",
            title="Swag Labs",
        ),
        facts={
            "cart_count": ObservedFact(
                path="cart_count",
                value=1,
                evidence=[
                    ObservationEvidence(
                        source="dom",
                        selector=".shopping_cart_badge",
                        text="1",
                    )
                ],
            ),
            "order_created": ObservedFact(
                path="order_created",
                value=False,
                evidence=[
                    ObservationEvidence(
                        source="url",
                        url="https://www.saucedemo.com/cart.html",
                    )
                ],
                derived=True,
            ),
        },
        observer="saucedemo",
    )

    assert observation.to_signature() == {
        "cart_count": 1,
        "order_created": False,
    }
    assert (
        observation.facts["cart_count"].evidence[0].selector
        == ".shopping_cart_badge"
    )
    assert observation.facts["order_created"].derived is True


def test_web_observation_can_carry_interactable_candidates() -> None:
    candidate = DomInteractableCandidate(
        id="dom_001",
        kind="button",
        locator="#checkout",
        locator_strategy="id",
        name="Checkout",
        visible=True,
        enabled=True,
        metadata={"id": "checkout"},
    )

    observation = WebObservation(
        identity=PageIdentity(page_id="cart", url="https://example.test/cart"),
        facts={},
        interactables=[candidate],
        observer="test",
    )

    assert observation.interactables == [candidate]
