from ai_web_explorer.grounded_web.experiment_plan import (
    ecommerce_checkout_experiment_plan,
)


def test_default_ecommerce_checkout_plan_stops_before_final_order():
    plan = ecommerce_checkout_experiment_plan()

    step_ids = [step.step_id for step in plan.steps]

    assert plan.plan_id == "ecommerce_checkout_stop_before_final_order"
    assert step_ids == [
        "establish_session_or_product_listing",
        "add_product_to_cart",
        "open_cart",
        "start_checkout",
        "fill_checkout_user_info",
        "fill_payment_info_if_required",
        "continue_to_order_review",
        "stop_before_final_order",
    ]
    assert plan.steps[4].expected_added_facts == ("checkout_user_info_complete",)
    assert plan.steps[5].expected_added_facts == ("payment_info_complete",)
    assert plan.steps[-1].stop_after_step is True


def test_ecommerce_checkout_plan_can_allow_final_order():
    plan = ecommerce_checkout_experiment_plan(allow_final_order=True)

    final_step = plan.steps[-1]

    assert plan.plan_id == "ecommerce_checkout_allow_final_order"
    assert final_step.step_id == "place_final_order"
    assert final_step.expected_added_facts == ("order_completed",)
    assert final_step.stop_after_step is True
