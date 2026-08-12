from ai_web_explorer.grounded_web.exploration_semantics import (
    generate_checkout_test_data,
    practice_shopping_feasibility_profile,
    resolve_semantic_experiment_profile,
)


def test_practice_profile_separates_locations_capabilities_and_business_facts():
    profile = practice_shopping_feasibility_profile()

    assert profile.allowed_locations == (
        "shopping",
        "product_detail",
        "checkout",
        "confirmation",
    )
    assert profile.completion_fact_ids == {
        "products_sorted",
        "products_filtered",
        "products_found",
        "products_paginated",
        "product_details_viewed",
    }
    assert profile.business_fact_ids == {
        "cart_has_items",
        "checkout_info_complete",
        "payment_info_complete",
        "order_submitted",
    }
    assert {
        "sort_products",
        "filter_products",
        "search_products",
        "add_to_cart",
        "open_checkout",
        "complete_checkout_information",
        "complete_payment_information",
        "place_order",
    }.issubset(set(profile.canonical_action_examples))
    assert resolve_semantic_experiment_profile(profile.profile_id) == profile


def test_generated_checkout_data_is_deterministic_and_fictional():
    first = generate_checkout_test_data("practice-v1")
    second = generate_checkout_test_data("practice-v1")

    assert first == second
    assert first.email.endswith("@example.test")
    assert first.card_number == "4111111111111111"
    assert first.to_benchmark_context().test_credentials == {}
