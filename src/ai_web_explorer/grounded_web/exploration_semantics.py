"""Experiment-scoped semantic vocabulary and fictional benchmark data.

The generic explorer consumes this module as configuration.  Site-specific
vocabulary belongs here rather than in selectors, graph projection, or PDDL
compilation.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningFactSpec,
)
from ai_web_explorer.grounded_web.stagehand_prompt import BenchmarkTaskContext


@dataclass(frozen=True)
class FactEvidenceRule:
    """Allow-listed fact with the minimum visible evidence that supports it."""

    fact_id: str
    descriptions: tuple[str, ...]


@dataclass(frozen=True)
class SemanticExperimentProfile:
    """Vocabulary and evidence rules for one semantic exploration experiment."""

    profile_id: str
    allowed_locations: tuple[str, ...]
    completion_facts: tuple[FactEvidenceRule, ...]
    business_facts: tuple[FactEvidenceRule, ...]
    action_role_examples: Mapping[str, str]
    canonical_action_examples: tuple[str, ...]

    @property
    def completion_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.completion_facts)

    @property
    def business_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.business_facts)

    def to_prompt_context(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "allowed_locations": list(self.allowed_locations),
            "completion_facts": {
                rule.fact_id: list(rule.descriptions)
                for rule in self.completion_facts
            },
            "business_facts": {
                rule.fact_id: list(rule.descriptions)
                for rule in self.business_facts
            },
            "action_role_examples": dict(self.action_role_examples),
            "canonical_action_examples": list(self.canonical_action_examples),
        }

    def to_business_flow_profile(self) -> BusinessFlowProfile:
        """Adapt business facts to the existing generic fact verifier contract."""

        return BusinessFlowProfile(
            site_type=self.profile_id,
            stages=[],
            planning_facts=[
                PlanningFactSpec(
                    fact_id=rule.fact_id,
                    meaning=" ".join(rule.descriptions),
                )
                for rule in self.business_facts
            ],
        )


@dataclass(frozen=True)
class GeneratedCheckoutData:
    """Deterministic, fictional values safe for the controlled test site."""

    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    city: str
    postal_code: str
    country: str
    cardholder: str
    card_number: str
    expiry: str
    cvv: str

    def to_benchmark_context(self) -> BenchmarkTaskContext:
        return BenchmarkTaskContext(
            site_label="PracticeAutomatedTesting controlled test site",
            checkout_data=asdict(self),
            notes=("Use fictional data only.",),
        )


def _fact(fact_id: str, *descriptions: str) -> FactEvidenceRule:
    return FactEvidenceRule(fact_id=fact_id, descriptions=tuple(descriptions))


def practice_shopping_feasibility_profile() -> SemanticExperimentProfile:
    """Return the vocabulary approved for the Practice shopping experiment."""

    return SemanticExperimentProfile(
        profile_id="practice_shopping_feasibility",
        allowed_locations=(
            "shopping",
            "product_detail",
            "checkout",
            "confirmation",
        ),
        completion_facts=(
            _fact(
                "products_sorted",
                "The visible product ordering changed and the resulting order is stable.",
            ),
            _fact(
                "products_filtered",
                "The visible product set changed consistently with an active filter.",
            ),
            _fact(
                "products_found",
                "A matching product is visibly present in the search results.",
            ),
            _fact(
                "products_paginated",
                "The visible product page or pagination state changed successfully.",
            ),
            _fact(
                "product_details_viewed",
                "A product detail surface is visibly open for inspection.",
            ),
        ),
        business_facts=(
            _fact(
                "cart_has_items",
                "A cart count, in-cart marker, or order summary visibly shows an item.",
            ),
            _fact(
                "checkout_info_complete",
                "Required checkout contact, billing, shipping, and address information appears complete.",
            ),
            _fact(
                "payment_info_complete",
                "Required payment method or payment information appears complete.",
            ),
            _fact(
                "order_submitted",
                "A confirmation or acknowledgement visibly shows that the order was submitted.",
            ),
        ),
        action_role_examples={
            "sort_products": "presentation_capability",
            "filter_products": "presentation_capability",
            "search_products": "discovery_capability",
            "paginate_products": "pagination_capability",
            "open_product": "detail_navigation",
            "add_to_cart": "business_mutation",
            "open_empty_cart": "guarded_navigation",
            "open_checkout": "guarded_navigation",
            "close_product_detail": "surface_navigation",
            "complete_checkout_information": "form_completion",
            "complete_payment_information": "payment_completion",
            "place_order": "final_submission",
        },
        canonical_action_examples=(
            "sort_products",
            "filter_products",
            "search_products",
            "paginate_products",
            "open_product",
            "add_to_cart",
            "open_empty_cart",
            "open_checkout",
            "close_product_detail",
            "complete_checkout_information",
            "complete_payment_information",
            "place_order",
        ),
    )


def resolve_semantic_experiment_profile(
    name: str | None,
) -> SemanticExperimentProfile | None:
    """Resolve an experiment profile name, preserving generic no-profile mode."""

    if name is None or not name.strip():
        return None
    if name == "practice_shopping_feasibility":
        return practice_shopping_feasibility_profile()
    raise ValueError(f"unknown semantic experiment profile: {name}")


def validate_final_order_authorization(
    *,
    start_url: str,
    profile: SemanticExperimentProfile | str | None,
    allowed: bool,
) -> bool:
    """Validate the only supported final-order authorization boundary.

    Generated benchmark data is intentionally independent from this check. A
    caller can use it for form filling without receiving permission to submit.
    """

    if not allowed:
        return False
    profile_id = (
        profile.profile_id
        if isinstance(profile, SemanticExperimentProfile)
        else str(profile or "").strip()
    )
    if profile_id != "practice_shopping_feasibility":
        raise ValueError(
            "final order authorization requires the "
            "practice_shopping_feasibility semantic experiment profile"
        )
    parsed = urlsplit(str(start_url).strip())
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("final order authorization requires the controlled test URL") from error
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "practiceautomatedtesting.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/shopping"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("final order authorization requires the controlled test URL")
    return True


def generate_checkout_test_data(seed: str) -> GeneratedCheckoutData:
    """Generate deterministic fictional checkout data from ``seed``."""

    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return GeneratedCheckoutData(
        first_name="Test",
        last_name=f"User{suffix}",
        email=f"shop-{suffix}@example.test",
        phone="555-0100",
        address="123 Test Street",
        city="Testville",
        postal_code="12345",
        country="Netherlands",
        cardholder=f"Test User {suffix}",
        card_number="4111111111111111",
        expiry="12/30",
        cvv="123",
    )


__all__ = [
    "FactEvidenceRule",
    "GeneratedCheckoutData",
    "SemanticExperimentProfile",
    "generate_checkout_test_data",
    "practice_shopping_feasibility_profile",
    "resolve_semantic_experiment_profile",
    "validate_final_order_authorization",
]
