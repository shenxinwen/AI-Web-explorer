from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.planning_fact_verifier import (
    verify_planning_delta,
)


def test_verify_planning_delta_uses_direct_profile_fact_changes():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"checkout_info_complete": True},
        after_signature={"checkout_info_complete": False},
    )

    assert isinstance(delta, PlanningDelta)
    assert delta.verified_removed_facts == ["checkout_info_complete"]
    assert delta.candidate_removed_facts == ["checkout_info_complete"]
    assert delta.uncertainty_reason is None


def test_verify_planning_delta_maps_generic_cart_count_to_profile_facts():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"cart_count": 0},
        after_signature={"cart_count": 2},
    )

    assert delta.verified_added_facts == ["cart_nonempty"]
    assert delta.verified_removed_facts == ["cart_empty"]
    assert delta.candidate_added_facts == ["cart_nonempty"]
    assert "cart_count" in delta.evidence[0]
