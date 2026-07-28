from types import SimpleNamespace

from ai_web_explorer.grounded_web.stagehand_prompt import (
    BenchmarkTaskContext,
    ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE,
    build_generic_stagehand_exploration_goal,
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

    assert "Advance the checkout task toward the experiment objective" in goal
    assert "Stop as soon as a meaningful state transition is complete" in goal
    assert "skip or merge milestones" in goal
    assert "Choose exactly one low-level browser action" not in goal
    assert "sign-in fields" in goal


def test_ecommerce_stagehand_goal_includes_site_agnostic_guided_steps():
    goal = build_ecommerce_checkout_stagehand_goal()

    assert "Milestone guidance:" in goal
    assert "Open the cart or proceed directly to checkout" in goal
    assert "Fill required checkout, contact, shipping, billing, and payment fields" in goal
    assert "Continue to order review, checkout overview" in goal
    assert "Do not use CSS selectors" in goal
    assert "#checkout" not in goal
    assert ".cart" not in goal
    assert "SauceDemo" not in goal
    assert "TestDino" not in goal


def test_ecommerce_stagehand_goal_includes_test_data_policy():
    goal = build_ecommerce_checkout_stagehand_goal()

    assert "Test data policy:" in goal
    assert "clearly fictional demo/test values" in goal
    assert "test@example.com" in goal
    assert "4111111111111111" in goal
    assert "Do not use real personal or payment information" in goal


def test_ecommerce_stagehand_goal_can_target_configured_experiment_step():
    goal = build_ecommerce_checkout_stagehand_goal(
        benchmark_context=BenchmarkTaskContext(site_label="demo shop"),
        current_step=SimpleNamespace(
            step_id="fill_payment_info",
            instruction=(
                "Fill required payment fields if the visible checkout flow "
                "requires them."
            ),
            expected_added_facts=("payment_info_complete",),
        ),
    )

    assert "Configured experiment step:" in goal
    assert "step_id: fill_payment_info" in goal
    assert "Fill required payment fields" in goal
    assert "expected_added_facts: payment_info_complete" in goal
    assert "Use this configured step as guidance" in goal
    assert "skip or merge" in goal
    assert "Execute only this configured step" not in goal


def test_ecommerce_stagehand_goal_allows_flexible_milestone_guidance():
    goal = build_ecommerce_checkout_stagehand_goal()

    assert "Milestone guidance:" in goal
    assert "guidance, not a mandatory fixed sequence" in goal
    assert "skip or merge milestones" in goal
    assert "Do not repeat a milestone that is already visibly satisfied" in goal


def test_generic_stagehand_exploration_goal_is_not_checkout_specific():
    goal = build_generic_stagehand_exploration_goal(site_purpose="demo store")

    assert "demo store" in goal
    assert "Choose one useful site-function action" in goal
    assert "Avoid low-value footer, legal, social, theme, and language actions" in goal
    assert "checkout" not in goal.lower()
    assert "payment" not in goal.lower()
