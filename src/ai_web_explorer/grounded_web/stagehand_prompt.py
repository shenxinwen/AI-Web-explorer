from __future__ import annotations

from dataclasses import dataclass, field


ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE = (
    "Operate one step in a generic e-commerce checkout exploration task. "
    "Useful affordances may include sign-in fields, product listings, search, "
    "cart controls, checkout controls, shipping or contact forms, order review, "
    "and final confirmation controls when the configured experiment allows "
    "completion. Choose actions from visible page evidence."
)

ECOMMERCE_CHECKOUT_ACTION_POLICY = (
    "Advance the website by exactly one meaningful business milestone toward "
    "the checkout goal. A meaningful milestone is a visible or "
    "business-relevant state transition, such as logging in, reaching a "
    "product listing, adding an item to the cart, opening the cart, starting "
    "checkout, submitting required checkout information, reaching order review, "
    "or placing the order when the configured experiment allows completion. "
    "You may perform multiple low-level browser interactions if needed. Do not "
    "execute multiple milestones in one call. Stop as soon as one milestone is "
    "complete and report what milestone was completed with visible evidence."
)


@dataclass(frozen=True)
class BenchmarkTaskContext:
    site_label: str | None = None
    test_credentials: dict[str, str] = field(default_factory=dict)
    checkout_data: dict[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def _render_key_values(values: dict[str, str]) -> str:
    if not values:
        return "none provided"
    return ", ".join(f"{key}={value}" for key, value in sorted(values.items()))


def _render_benchmark_context(context: BenchmarkTaskContext | None) -> str:
    if context is None:
        return (
            "No benchmark-specific test data is provided. Use only values that "
            "are visible on the page or supplied by the task environment."
        )
    lines = [
        f"site_label: {context.site_label or 'unspecified test site'}",
        f"test_credentials: {_render_key_values(context.test_credentials)}",
        f"checkout_data: {_render_key_values(context.checkout_data)}",
    ]
    if context.notes:
        lines.append("notes: " + " ".join(context.notes))
    return "\n".join(lines)


def build_ecommerce_checkout_stagehand_goal(
    *,
    allow_final_order: bool = False,
    benchmark_context: BenchmarkTaskContext | None = None,
) -> str:
    safety_boundary = (
        "This is an explicit test-site completion run; final confirmation is "
        "allowed for the final order when visible and relevant."
        if allow_final_order
        else "Do not place the final order. Stop at order review or checkout overview."
    )
    return "\n\n".join(
        [
            f"Domain guidance:\n{ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE}",
            f"Benchmark context:\n{_render_benchmark_context(benchmark_context)}",
            f"Action policy:\n{ECOMMERCE_CHECKOUT_ACTION_POLICY}",
            f"Safety boundary:\n{safety_boundary}",
        ]
    )
