from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.exploration_semantics import (
    practice_shopping_feasibility_profile,
)
from ai_web_explorer.grounded_web.planning_fact_verifier import (
    verify_planning_delta,
    verify_experiment_planning_delta,
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

    assert delta.verified_added_facts == ["cart_has_items"]
    assert delta.verified_removed_facts == []
    assert delta.candidate_added_facts == ["cart_has_items"]
    assert "cart_count" in delta.evidence[0]


def test_verify_planning_delta_removes_cart_has_items_when_cart_count_reaches_zero():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"cart_count": 2},
        after_signature={"cart_count": 0},
    )

    assert delta.verified_added_facts == []
    assert delta.verified_removed_facts == ["cart_has_items"]
    assert delta.candidate_removed_facts == ["cart_has_items"]
    assert "cart_count" in delta.evidence[0]


def test_verify_planning_delta_preserves_profile_fact_across_positive_cart_count_change():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"cart_count": 1},
        after_signature={"cart_count": 2},
    )

    assert delta.preserved_profile_facts == ["cart_has_items"]
    assert delta.verified_added_facts == []
    assert delta.verified_removed_facts == []


def test_verify_planning_delta_does_not_preserve_profile_fact_across_zero_boundary():
    delta = verify_planning_delta(
        profile=ecommerce_checkout_profile(),
        before_signature={"cart_count": 0},
        after_signature={"cart_count": 1},
    )

    assert delta.preserved_profile_facts == []


def test_experiment_verifier_promotes_only_evidenced_allowed_business_fact():
    result = verify_experiment_planning_delta(
        profile=practice_shopping_feasibility_profile(),
        observable_change=True,
        candidate_added_facts=["cart_has_items", "invented_fact"],
        candidate_removed_facts=[],
        evidence=["The cart count changed from 0 to 1."],
        structured_delta=PlanningDelta(),
    )

    assert result.verified_added_facts == ["cart_has_items"]
    assert "invented_fact" not in result.profile_fact_ids


def test_action_change_without_fact_evidence_does_not_promote_business_fact():
    result = verify_experiment_planning_delta(
        profile=practice_shopping_feasibility_profile(),
        observable_change=True,
        candidate_added_facts=["cart_has_items"],
        candidate_removed_facts=[],
        evidence=[],
        structured_delta=PlanningDelta(),
    )

    assert result.verified_added_facts == []


def test_experiment_verifier_rejects_invented_and_unevidenced_business_facts():
    result = verify_experiment_planning_delta(
        profile=practice_shopping_feasibility_profile(),
        observable_change=True,
        candidate_added_facts=[
            "checkout_info_complete",
            "invented_fact",
            "payment_info_complete",
        ],
        candidate_removed_facts=[],
        evidence=["Checkout fields visibly became complete."],
        structured_delta=PlanningDelta(),
    )

    assert result.verified_added_facts == [
        "checkout_info_complete",
        "payment_info_complete",
    ]
    assert "invented_fact" not in result.candidate_added_facts
    assert "invented_fact" not in result.profile_fact_ids
