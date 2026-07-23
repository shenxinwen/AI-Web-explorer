from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceHint:
    evidence_type: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "description": self.description,
        }


@dataclass(frozen=True)
class BusinessStage:
    stage_id: str
    meaning: str
    goal_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "meaning": self.meaning,
            "goal_candidate": self.goal_candidate,
        }


@dataclass(frozen=True)
class PlanningFactSpec:
    fact_id: str
    meaning: str
    related_stages: list[str] = field(default_factory=list)
    evidence_hints: list[EvidenceHint] = field(default_factory=list)
    safety_relevance: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "meaning": self.meaning,
            "related_stages": list(self.related_stages),
            "evidence_hints": [hint.to_dict() for hint in self.evidence_hints],
            "safety_relevance": self.safety_relevance,
        }


@dataclass(frozen=True)
class SensitiveActionCategory:
    category_id: str
    meaning: str
    evidence_hints: list[EvidenceHint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "meaning": self.meaning,
            "evidence_hints": [hint.to_dict() for hint in self.evidence_hints],
        }


@dataclass(frozen=True)
class BusinessFlowProfile:
    site_type: str
    stages: list[BusinessStage]
    planning_facts: list[PlanningFactSpec]
    sensitive_action_categories: list[SensitiveActionCategory] = field(
        default_factory=list
    )
    goal_stage_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_type": self.site_type,
            "stages": [stage.to_dict() for stage in self.stages],
            "planning_facts": [fact.to_dict() for fact in self.planning_facts],
            "sensitive_action_categories": [
                category.to_dict() for category in self.sensitive_action_categories
            ],
            "goal_stage_candidates": list(self.goal_stage_candidates),
        }


@dataclass(frozen=True)
class PlanningDelta:
    candidate_added_facts: list[str] = field(default_factory=list)
    candidate_removed_facts: list[str] = field(default_factory=list)
    verified_added_facts: list[str] = field(default_factory=list)
    verified_removed_facts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float | None = None
    uncertainty_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_added_facts": list(self.candidate_added_facts),
            "candidate_removed_facts": list(self.candidate_removed_facts),
            "verified_added_facts": list(self.verified_added_facts),
            "verified_removed_facts": list(self.verified_removed_facts),
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "uncertainty_reason": self.uncertainty_reason,
        }


def _hint(evidence_type: str, description: str) -> EvidenceHint:
    return EvidenceHint(evidence_type=evidence_type, description=description)


def ecommerce_checkout_profile() -> BusinessFlowProfile:
    stages = [
        BusinessStage(
            stage_id="session_setup",
            meaning="The user has established a usable session or authentication state.",
        ),
        BusinessStage(
            stage_id="product_selection",
            meaning="The user can inspect and select purchasable items.",
        ),
        BusinessStage(
            stage_id="cart",
            meaning="The user can review items selected for purchase.",
        ),
        BusinessStage(
            stage_id="checkout_info",
            meaning="The user can provide required checkout, shipping, or contact information.",
        ),
        BusinessStage(
            stage_id="order_review",
            meaning="The user can review the pending order before committing it.",
            goal_candidate=True,
        ),
        BusinessStage(
            stage_id="order_complete",
            meaning="The purchase or order has been submitted and acknowledged.",
            goal_candidate=True,
        ),
    ]
    planning_facts = [
        PlanningFactSpec(
            fact_id="logged_in",
            meaning="The user appears to have an authenticated or usable shopping session.",
            related_stages=["session_setup"],
            evidence_hints=[
                _hint(
                    "navigation",
                    "The page moves from a sign-in flow to a shopping area.",
                ),
                _hint(
                    "control",
                    "Shopping controls become available after authentication.",
                ),
            ],
        ),
        PlanningFactSpec(
            fact_id="product_list_visible",
            meaning="A list or collection of purchasable products is visible.",
            related_stages=["product_selection"],
            evidence_hints=[
                _hint("region", "A repeated product or item list is visible."),
                _hint("control", "Item selection controls are available."),
            ],
        ),
        PlanningFactSpec(
            fact_id="cart_empty",
            meaning="No items appear to be selected for purchase.",
            related_stages=["product_selection", "cart"],
            evidence_hints=[
                _hint("count", "A cart count or item total indicates zero items."),
                _hint("region", "A cart view contains no product rows."),
            ],
        ),
        PlanningFactSpec(
            fact_id="cart_nonempty",
            meaning="The user has at least one item selected for purchase.",
            related_stages=["product_selection", "cart"],
            evidence_hints=[
                _hint(
                    "count", "A cart count or item total indicates one or more items."
                ),
                _hint("region", "A cart view lists at least one product."),
                _hint("control", "A selected product can be removed or edited."),
            ],
        ),
        PlanningFactSpec(
            fact_id="cart_page_visible",
            meaning="The user is viewing a cart or order basket area.",
            related_stages=["cart"],
            evidence_hints=[
                _hint("navigation", "The page context changes to cart review."),
                _hint("region", "A cart summary or selected-item list is visible."),
            ],
        ),
        PlanningFactSpec(
            fact_id="checkout_started",
            meaning="The user has moved from cart review into checkout.",
            related_stages=["checkout_info"],
            evidence_hints=[
                _hint("navigation", "The page context changes from cart to checkout."),
                _hint("form", "Checkout information fields become visible."),
            ],
        ),
        PlanningFactSpec(
            fact_id="required_info_missing",
            meaning=(
                "Required checkout, contact, shipping, or account information "
                "appears incomplete or still needs user input."
            ),
            related_stages=["checkout_info"],
            evidence_hints=[
                _hint("form", "Required fields appear empty or invalid."),
                _hint("message", "A validation message asks for missing information."),
            ],
            safety_relevance="information_verification",
        ),
        PlanningFactSpec(
            fact_id="required_info_provided",
            meaning=(
                "Required checkout, contact, shipping, or account information "
                "appears to have been provided."
            ),
            related_stages=["checkout_info", "order_review"],
            evidence_hints=[
                _hint("form", "Required fields have non-empty values."),
                _hint(
                    "navigation",
                    "The flow advances past information entry toward review.",
                ),
            ],
            safety_relevance="information_verification",
        ),
        PlanningFactSpec(
            fact_id="checkout_info_complete",
            meaning="Required checkout, contact, or shipping information appears complete.",
            related_stages=["checkout_info", "order_review"],
            evidence_hints=[
                _hint("form", "Required checkout fields have non-empty values."),
                _hint("control", "A continue or review action becomes available."),
                _hint(
                    "navigation", "The flow advances from information entry to review."
                ),
            ],
            safety_relevance="information_verification",
        ),
        PlanningFactSpec(
            fact_id="order_review_ready",
            meaning="The user is at a review step where the pending order can be inspected.",
            related_stages=["order_review"],
            evidence_hints=[
                _hint(
                    "region", "An order summary, totals, or selected items are visible."
                ),
                _hint(
                    "control", "A final submission or confirmation action is available."
                ),
            ],
            safety_relevance="information_verification",
        ),
        PlanningFactSpec(
            fact_id="order_place_pending_sensitive",
            meaning="The next action may commit a purchase, payment, or externally visible order.",
            related_stages=["order_review"],
            evidence_hints=[
                _hint("control", "A visible action suggests final order confirmation."),
                _hint("region", "The page presents a final review before submission."),
            ],
            safety_relevance="human_confirmation",
        ),
        PlanningFactSpec(
            fact_id="order_completed",
            meaning="The order or purchase appears to have been submitted successfully.",
            related_stages=["order_complete"],
            evidence_hints=[
                _hint(
                    "message",
                    "A completion, success, or acknowledgement message is visible.",
                ),
                _hint("navigation", "The flow moves to a completion or receipt state."),
            ],
        ),
        PlanningFactSpec(
            fact_id="error_visible",
            meaning="The page shows an error or validation problem that may block progress.",
            related_stages=[
                "session_setup",
                "checkout_info",
                "order_review",
            ],
            evidence_hints=[
                _hint(
                    "message", "An error, warning, or validation message is visible."
                ),
                _hint("form", "A required field or invalid value is highlighted."),
            ],
        ),
    ]
    sensitive_action_categories = [
        SensitiveActionCategory(
            category_id="submit_personal_information",
            meaning="The action submits contact, shipping, payment, or other user-provided information.",
            evidence_hints=[
                _hint(
                    "form", "The action follows a form with required user information."
                ),
                _hint(
                    "control",
                    "The action wording suggests continuing or submitting information.",
                ),
            ],
        ),
        SensitiveActionCategory(
            category_id="place_order",
            meaning="The action may commit a purchase or externally visible order.",
            evidence_hints=[
                _hint(
                    "region",
                    "The action appears on an order review or confirmation step.",
                ),
                _hint("control", "The action wording suggests final commitment."),
            ],
        ),
    ]
    return BusinessFlowProfile(
        site_type="ecommerce_checkout",
        stages=stages,
        planning_facts=planning_facts,
        sensitive_action_categories=sensitive_action_categories,
        goal_stage_candidates=[
            stage.stage_id for stage in stages if stage.goal_candidate
        ],
    )


__all__ = [
    "BusinessFlowProfile",
    "BusinessStage",
    "EvidenceHint",
    "PlanningDelta",
    "PlanningFactSpec",
    "SensitiveActionCategory",
    "ecommerce_checkout_profile",
]
