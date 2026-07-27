from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExperimentStep:
    step_id: str
    instruction: str
    expected_added_facts: tuple[str, ...] = ()
    expected_removed_facts: tuple[str, ...] = ()
    safety_note: str | None = None
    stop_after_step: bool = False

    def to_metadata(self) -> dict[str, object]:
        return {
            "experiment_step_id": self.step_id,
            "expected_added_facts": list(self.expected_added_facts),
            "expected_removed_facts": list(self.expected_removed_facts),
            "stop_after_step": self.stop_after_step,
        }


@dataclass(frozen=True)
class ExperimentPlan:
    plan_id: str
    site_type: str
    steps: tuple[ExperimentStep, ...] = field(default_factory=tuple)

    def step_for_number(self, step_number: int) -> ExperimentStep | None:
        if not self.steps:
            return None
        if step_number <= 1:
            return self.steps[0]
        if step_number > len(self.steps):
            return self.steps[-1]
        return self.steps[step_number - 1]


def ecommerce_checkout_experiment_plan(
    *,
    allow_final_order: bool = False,
) -> ExperimentPlan:
    steps = [
        ExperimentStep(
            step_id="establish_session_or_product_listing",
            instruction=(
                "If sign-in or session setup is required, complete it using "
                "benchmark credentials when provided. Otherwise reach or confirm "
                "a visible product listing."
            ),
            expected_added_facts=("logged_in", "product_list_visible"),
        ),
        ExperimentStep(
            step_id="add_product_to_cart",
            instruction="Add one visible, available product to the cart.",
            expected_added_facts=("cart_has_items",),
        ),
        ExperimentStep(
            step_id="open_cart",
            instruction="Open the cart or basket so selected items can be reviewed.",
            expected_added_facts=("cart_page_visible",),
        ),
        ExperimentStep(
            step_id="start_checkout",
            instruction="Start checkout from the cart or basket view.",
            expected_added_facts=("checkout_started",),
        ),
        ExperimentStep(
            step_id="fill_checkout_user_info",
            instruction=(
                "Fill all required non-payment checkout user, contact, shipping, "
                "delivery, billing identity, or address fields."
            ),
            expected_added_facts=("checkout_user_info_complete",),
        ),
        ExperimentStep(
            step_id="fill_payment_info_if_required",
            instruction=(
                "If the visible checkout flow requires payment information, fill "
                "the required payment method or payment credential fields. If no "
                "payment section is visible or required, do not invent one."
            ),
            expected_added_facts=("payment_info_complete",),
        ),
        ExperimentStep(
            step_id="continue_to_order_review",
            instruction=(
                "Continue from completed checkout information to order review or "
                "checkout overview."
            ),
            expected_added_facts=(
                "checkout_info_complete",
                "order_review_ready",
                "order_place_pending_sensitive",
            ),
        ),
    ]
    if allow_final_order:
        steps.append(
            ExperimentStep(
                step_id="place_final_order",
                instruction=(
                    "Place the final order only because this configured test run "
                    "explicitly allows final confirmation."
                ),
                expected_added_facts=("order_completed",),
                safety_note="Final confirmation is allowed only for this test run.",
                stop_after_step=True,
            )
        )
    else:
        steps.append(
            ExperimentStep(
                step_id="stop_before_final_order",
                instruction=(
                    "Stop at order review or checkout overview. Do not place the "
                    "final order."
                ),
                safety_note="Final order placement is not allowed in this run.",
                stop_after_step=True,
            )
        )
    return ExperimentPlan(
        plan_id=(
            "ecommerce_checkout_allow_final_order"
            if allow_final_order
            else "ecommerce_checkout_stop_before_final_order"
        ),
        site_type="ecommerce_checkout",
        steps=tuple(steps),
    )


__all__ = [
    "ExperimentPlan",
    "ExperimentStep",
    "ecommerce_checkout_experiment_plan",
]
