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
    "Advance the checkout task toward the experiment objective. Prefer useful "
    "milestones from the guidance list, but skip or merge milestones when the "
    "page flow naturally makes a separate step unnecessary. Do not repeat a "
    "milestone that is already visibly satisfied. You may perform multiple "
    "low-level browser interactions if needed to complete a useful milestone. "
    "Stop as soon as a meaningful state transition is complete and report what "
    "changed with visible evidence."
)

ECOMMERCE_CHECKOUT_GUIDED_STEPS = (
    "These milestones are guidance, not a mandatory fixed sequence. Open a "
    "product listing if needed. Add one available product to the cart. Open the "
    "cart or proceed directly to checkout if the site combines those steps. "
    "Fill required checkout, contact, shipping, billing, and payment fields "
    "when the visible flow requires them. Continue to order review, checkout "
    "overview, or final confirmation when the safety boundary allows it. Skip "
    "or merge milestones that are already satisfied by the current page. Do not "
    "use CSS selectors, XPath, or site-specific button scripts; choose from "
    "visible page evidence."
)

ECOMMERCE_CHECKOUT_TEST_DATA_POLICY = (
    "Use benchmark-provided values when available. If a required checkout field "
    "has no provided value, use clearly fictional demo/test values. Suggested "
    "fictional user values include name=Test User, email=test@example.com, "
    "phone=555-123-4567, address=123 Main Street, city=Springfield, "
    "postal_code=12345, and country=United States. Suggested non-real payment "
    "values, when the visible test checkout requires them, include "
    "cardholder=Test User, card_number=4111111111111111, expiry=12/30, and "
    "cvv=123. Do not use real personal or payment information. These values "
    "are only for test/demo form completion and do not imply final order "
    "placement is allowed."
)

GENERIC_EXPLORATION_ACTION_POLICY = (
    "Execute exactly one selected business action from visible page evidence. "
    "If Web-KOBE has already selected an action, complete only that action and "
    "stop after the first visible completion or clear failure. If no selected "
    "action is supplied, use this only as fallback: choose one obvious business "
    "action and execute it once. Avoid low-value footer, legal, social, theme, "
    "and language actions unless they are central to the site. Report visible "
    "evidence."
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


def _render_current_step(current_step: object | None) -> str:
    if current_step is None:
        return (
            "none configured. Choose the next useful business milestone from "
            "visible page evidence."
        )
    step_id = str(getattr(current_step, "step_id", "unspecified_step"))
    instruction = str(getattr(current_step, "instruction", ""))
    expected_added = tuple(getattr(current_step, "expected_added_facts", ()) or ())
    expected_removed = tuple(getattr(current_step, "expected_removed_facts", ()) or ())
    lines = [
        f"step_id: {step_id}",
        f"instruction: {instruction}",
    ]
    if expected_added:
        lines.append("expected_added_facts: " + ", ".join(expected_added))
    if expected_removed:
        lines.append("expected_removed_facts: " + ", ".join(expected_removed))
    safety_note = getattr(current_step, "safety_note", None)
    if safety_note:
        lines.append(f"safety_note: {safety_note}")
    lines.append(
        "Use this configured step as guidance for the current graph transition; "
        "skip or merge it if the page already satisfies it or naturally moves "
        "to the next useful milestone."
    )
    return "\n".join(lines)


def _render_milestone_guidance(experiment_plan: object | None) -> str:
    if experiment_plan is None:
        return ECOMMERCE_CHECKOUT_GUIDED_STEPS
    steps = tuple(getattr(experiment_plan, "steps", ()) or ())
    if not steps:
        return ECOMMERCE_CHECKOUT_GUIDED_STEPS
    lines = [ECOMMERCE_CHECKOUT_GUIDED_STEPS, "Configured milestone hints:"]
    for step in steps:
        step_id = str(getattr(step, "step_id", "unspecified_step"))
        instruction = str(getattr(step, "instruction", ""))
        lines.append(f"- {step_id}: {instruction}")
    return "\n".join(lines)


def build_ecommerce_checkout_stagehand_goal(
    *,
    allow_final_order: bool = False,
    benchmark_context: BenchmarkTaskContext | None = None,
    current_step: object | None = None,
    experiment_plan: object | None = None,
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
            f"Test data policy:\n{ECOMMERCE_CHECKOUT_TEST_DATA_POLICY}",
            f"Configured experiment step:\n{_render_current_step(current_step)}",
            f"Milestone guidance:\n{_render_milestone_guidance(experiment_plan)}",
            f"Action policy:\n{ECOMMERCE_CHECKOUT_ACTION_POLICY}",
            f"Safety boundary:\n{safety_boundary}",
        ]
    )


def build_generic_stagehand_exploration_goal(
    *,
    site_purpose: str | None = None,
    benchmark_context: BenchmarkTaskContext | None = None,
    allow_final_order: bool = False,
) -> str:
    purpose = site_purpose or "the current website"
    sections = [
        f"Site purpose:\n{purpose}",
        f"Action policy:\n{GENERIC_EXPLORATION_ACTION_POLICY}",
        (
            "Memory policy:\nWeb-KOBE may append exploration memory below. "
            "Use it only as context for the already selected action, and do "
            "not choose a different business goal from memory text."
        ),
    ]
    if benchmark_context is not None:
        sections.append(
            f"Benchmark context:\n{_render_benchmark_context(benchmark_context)}"
        )
    if allow_final_order:
        sections.append(
            "Test boundary:\nThis is an explicit controlled test-site run; "
            "final confirmation is allowed when visible and relevant. Use only "
            "the fictional benchmark values provided above."
        )
    return "\n\n".join(sections)
