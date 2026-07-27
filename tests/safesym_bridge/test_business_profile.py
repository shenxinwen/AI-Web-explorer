import json

from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    ecommerce_checkout_profile,
)


def test_ecommerce_checkout_profile_defines_planning_facts_without_site_selectors():
    profile = ecommerce_checkout_profile()

    fact_ids = {fact.fact_id for fact in profile.planning_facts}

    assert profile.site_type == "ecommerce_checkout"
    assert "cart_has_items" in fact_ids
    assert "cart_empty" not in fact_ids
    assert "cart_nonempty" not in fact_ids
    assert "checkout_info_complete" in fact_ids
    assert "checkout_user_info_complete" in fact_ids
    assert "payment_info_complete" in fact_ids
    assert "required_info_missing" in fact_ids
    assert "required_info_provided" not in fact_ids
    assert "order_place_pending_sensitive" in fact_ids
    assert "order_review" in [stage.stage_id for stage in profile.stages]

    serialized = json.dumps(profile.to_dict()).lower()
    forbidden_site_specific_terms = [
        "saucedemo",
        "sauce labs",
        "shopping_cart_badge",
        "checkout-step-one",
        "data-test",
        "#finish",
        ".inventory_item",
    ]
    for term in forbidden_site_specific_terms:
        assert term not in serialized


def test_ecommerce_checkout_profile_distinguishes_user_and_payment_info():
    profile = ecommerce_checkout_profile()
    facts = {fact.fact_id: fact for fact in profile.planning_facts}

    user_info = facts["checkout_user_info_complete"]
    payment_info = facts["payment_info_complete"]
    checkout_info = facts["checkout_info_complete"]

    assert "non-payment" in user_info.meaning
    assert "payment" in payment_info.meaning
    assert "payment" in checkout_info.meaning
    assert "order review" in checkout_info.meaning
    assert checkout_info.safety_relevance == "information_verification"


def test_planning_delta_separates_candidate_and_verified_facts():
    delta = PlanningDelta(
        candidate_added_facts=["cart_has_items"],
        candidate_removed_facts=[],
        verified_added_facts=[],
        verified_removed_facts=[],
        evidence=["VLM saw a cart-count change"],
        confidence=0.42,
        uncertainty_reason="structured cart evidence did not confirm the claim",
    )

    data = delta.to_dict()

    assert data["candidate_added_facts"] == ["cart_has_items"]
    assert data["verified_added_facts"] == []
    assert data["uncertainty_reason"] == (
        "structured cart evidence did not confirm the claim"
    )
