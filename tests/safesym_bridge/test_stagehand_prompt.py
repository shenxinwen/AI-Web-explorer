from ai_web_explorer.grounded_web.stagehand_prompt import (
    BenchmarkTaskContext,
    ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE,
    build_ecommerce_checkout_stagehand_goal,
)


def test_ecommerce_domain_guidance_avoids_site_specific_terms():
    forbidden_terms = [
        "SauceDemo",
        "standard_user",
        "secret_sauce",
        "Sauce Labs Backpack",
        "Finish",
        "checkout-step-one",
    ]

    for term in forbidden_terms:
        assert term not in ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE


def test_ecommerce_stagehand_goal_separates_benchmark_context():
    goal = build_ecommerce_checkout_stagehand_goal(
        allow_final_order=True,
        benchmark_context=BenchmarkTaskContext(
            site_label="public demo e-commerce site",
            test_credentials={
                "username": "standard_user",
                "password": "secret_sauce",
            },
            checkout_data={
                "first_name": "Test",
                "last_name": "User",
                "postal_code": "12345",
            },
        ),
    )

    assert "Domain guidance:" in goal
    assert "Benchmark context:" in goal
    assert "Action policy:" in goal
    assert "Safety boundary:" in goal
    assert goal.index("Domain guidance:") < goal.index("Benchmark context:")
    assert "standard_user" in goal
    assert "secret_sauce" in goal
    assert "Sauce Labs Backpack" not in goal


def test_ecommerce_stagehand_goal_switches_final_order_boundary():
    overview_goal = build_ecommerce_checkout_stagehand_goal(
        allow_final_order=False,
    )
    completion_goal = build_ecommerce_checkout_stagehand_goal(
        allow_final_order=True,
    )

    assert "Do not place the final order" in overview_goal
    assert "final confirmation is allowed" in completion_goal


def test_ecommerce_stagehand_goal_uses_business_milestone_boundary_by_default():
    goal = build_ecommerce_checkout_stagehand_goal()

    assert "Advance the website by exactly one meaningful business milestone" in goal
    assert "Do not execute multiple milestones in one call" in goal
    assert "Choose exactly one low-level browser action" not in goal
    assert "logging in" in goal


def test_ecommerce_stagehand_goal_includes_site_agnostic_guided_steps():
    goal = build_ecommerce_checkout_stagehand_goal()

    assert "Guided checkout steps:" in goal
    assert "Open the cart or basket" in goal
    assert "Start checkout" in goal
    assert "Fill required checkout, contact, or shipping fields" in goal
    assert "Continue to order review or checkout overview" in goal
    assert "Do not use CSS selectors" in goal
    assert "#checkout" not in goal
    assert ".cart" not in goal
    assert "SauceDemo" not in goal
    assert "TestDino" not in goal
