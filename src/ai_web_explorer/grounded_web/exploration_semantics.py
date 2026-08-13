"""Experiment-scoped semantic vocabulary and fictional benchmark data.

The generic explorer consumes this module as configuration.  Site-specific
vocabulary belongs here rather than in selectors, graph projection, or PDDL
compilation.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping
from urllib.parse import urlsplit

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningFactSpec,
)
from ai_web_explorer.grounded_web.stagehand_prompt import BenchmarkTaskContext
from ai_web_explorer.grounded_web.semantic_model import (
    SEMANTIC_ACTION_ROLES,
    SemanticObservation,
    normalize_semantic_id,
)


@dataclass(frozen=True)
class FactEvidenceRule:
    """Allow-listed fact with the minimum visible evidence that supports it."""

    fact_id: str
    descriptions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_id", normalize_semantic_id(self.fact_id))


@dataclass(frozen=True)
class ActionContract:
    """Profile-scoped preconditions and observable business effects."""

    required_facts: tuple[str, ...] = ()
    added_facts: tuple[str, ...] = ()
    removed_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("required_facts", "added_facts", "removed_facts"):
            values = tuple(
                dict.fromkeys(
                    normalized
                    for value in getattr(self, field_name)
                    if (normalized := normalize_semantic_id(value))
                )
            )
            object.__setattr__(self, field_name, values)

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ActionContract":
        def values(field_name: str) -> tuple[object, ...]:
            raw = value.get(field_name, ())
            if isinstance(raw, (list, tuple)):
                return tuple(raw)
            return (raw,) if isinstance(raw, str) else ()

        return cls(
            required_facts=values("required_facts"),
            added_facts=values("added_facts"),
            removed_facts=values("removed_facts"),
        )

    def restricted_to(self, allowed_facts: frozenset[str]) -> "ActionContract":
        return ActionContract(
            required_facts=tuple(
                fact for fact in self.required_facts if fact in allowed_facts
            ),
            added_facts=tuple(
                fact for fact in self.added_facts if fact in allowed_facts
            ),
            removed_facts=tuple(
                fact for fact in self.removed_facts if fact in allowed_facts
            ),
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "required_facts": list(self.required_facts),
            "added_facts": list(self.added_facts),
            "removed_facts": list(self.removed_facts),
        }


@dataclass(frozen=True)
class SemanticExperimentProfile:
    """Vocabulary and evidence rules for one semantic exploration experiment."""

    profile_id: str
    allowed_locations: tuple[str, ...]
    completion_facts: tuple[FactEvidenceRule, ...]
    business_facts: tuple[FactEvidenceRule, ...]
    action_role_examples: Mapping[str, str]
    canonical_action_examples: tuple[str, ...]
    action_contracts: Mapping[str, ActionContract] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allowed_facts = self.business_fact_ids
        normalized_contracts: dict[str, ActionContract] = {}
        for action_id, contract in self.action_contracts.items():
            normalized_action_id = normalize_semantic_id(action_id)
            if not normalized_action_id:
                continue
            if not isinstance(contract, ActionContract):
                contract = ActionContract.from_dict(contract)
            normalized_contracts[normalized_action_id] = contract.restricted_to(
                allowed_facts
            )
        object.__setattr__(
            self,
            "action_contracts",
            {
                action_id: normalized_contracts[action_id]
                for action_id in sorted(normalized_contracts)
            },
        )

    @property
    def completion_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.completion_facts)

    @property
    def business_fact_ids(self) -> frozenset[str]:
        return frozenset(rule.fact_id for rule in self.business_facts)

    def action_contract_for(self, action_id: object) -> ActionContract | None:
        return self.action_contracts.get(normalize_semantic_id(action_id))

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
            "action_contracts": {
                action_id: self.action_contracts[action_id].to_dict()
                for action_id in sorted(self.action_contracts)
            },
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
class SemanticObservationValidation:
    observation: SemanticObservation | None
    rejection_reasons: tuple[str, ...] = ()


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
            "search_products": "presentation_capability",
            "paginate_products": "presentation_capability",
            "open_product": "navigation",
            "add_to_cart": "state_mutation",
            "open_empty_cart": "guarded_navigation",
            "open_checkout": "guarded_navigation",
            "close_product_detail": "navigation",
            "complete_checkout_information": "form_completion",
            "complete_payment_information": "form_completion",
            "place_order": "commit",
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
        action_contracts={
            "add_to_cart": ActionContract(added_facts=("cart_has_items",)),
            "view_cart": ActionContract(required_facts=("cart_has_items",)),
            "complete_checkout_information": ActionContract(
                added_facts=("checkout_info_complete",)
            ),
            "complete_payment_information": ActionContract(
                added_facts=("payment_info_complete",)
            ),
            "place_order": ActionContract(
                required_facts=(
                    "cart_has_items",
                    "checkout_info_complete",
                    "payment_info_complete",
                ),
                added_facts=("order_submitted",),
            ),
        },
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


def action_contracts_from_prompt_context(
    context: Mapping[str, object] | None,
) -> dict[str, ActionContract]:
    """Read normalized, business-fact-bounded contracts from graph context."""

    if not isinstance(context, Mapping):
        return {}
    raw_contracts = context.get("action_contracts")
    raw_business_facts = context.get("business_facts")
    if not isinstance(raw_contracts, Mapping) or not isinstance(
        raw_business_facts, Mapping
    ):
        return {}
    allowed_facts = frozenset(
        normalize_semantic_id(fact_id)
        for fact_id in raw_business_facts
        if normalize_semantic_id(fact_id)
    )
    contracts: dict[str, ActionContract] = {}
    for action_id, raw_contract in raw_contracts.items():
        normalized_action_id = normalize_semantic_id(action_id)
        if not normalized_action_id or not isinstance(raw_contract, Mapping):
            continue
        contracts[normalized_action_id] = ActionContract.from_dict(
            raw_contract
        ).restricted_to(allowed_facts)
    return {action_id: contracts[action_id] for action_id in sorted(contracts)}


def validate_profile_semantic_observation(
    observation: SemanticObservation | None,
    *,
    profile: SemanticExperimentProfile,
    source_location_hint: str | None = None,
    source_location_hint_confirmed: bool = False,
    source_location_anchor_unresolved: bool = False,
) -> SemanticObservationValidation:
    """Filter VLM semantics against the experiment's closed vocabulary."""

    if observation is None:
        return SemanticObservationValidation(None)
    reasons: list[str] = []
    allowed_locations = set(profile.allowed_locations)
    source_location = normalize_semantic_id(observation.source_location)
    target_location = normalize_semantic_id(observation.target_location)
    if source_location not in allowed_locations:
        reasons.append(f"source_location_not_allowed:{source_location}")
    if target_location not in allowed_locations:
        reasons.append(f"target_location_not_allowed:{target_location}")
    if observation.action_role not in SEMANTIC_ACTION_ROLES or observation.action_role == "unknown":
        reasons.append(f"action_role_not_allowed:{observation.action_role}")
    if source_location_anchor_unresolved:
        reasons.append("source_location_anchor_unresolved")
    if source_location_hint_confirmed and source_location_hint:
        normalized_hint = normalize_semantic_id(source_location_hint)
        if source_location != normalized_hint:
            reasons.append(f"source_location_mismatch:{normalized_hint}")

    completion_facts: list[str] = []
    for fact_id in observation.completion_facts:
        normalized = normalize_semantic_id(fact_id)
        if normalized in profile.completion_fact_ids:
            if normalized not in completion_facts:
                completion_facts.append(normalized)
        else:
            reasons.append(f"completion_fact_not_allowed:{normalized}")

    def filter_business_facts(values: list[str]) -> list[str]:
        accepted: list[str] = []
        for fact_id in values:
            normalized = normalize_semantic_id(fact_id)
            if normalized in profile.business_fact_ids:
                if normalized not in accepted:
                    accepted.append(normalized)
            else:
                reasons.append(f"business_fact_not_allowed:{normalized}")
        return accepted

    required_facts = filter_business_facts(observation.candidate_required_facts)
    preserved_facts = filter_business_facts(observation.preserved_facts)
    if (
        observation.action_role == "presentation_capability"
        and source_location != target_location
    ):
        reasons.append("presentation_location_drift")

    fatal_reasons = {
        reason
        for reason in reasons
        if reason.startswith(
            (
                "source_location_not_allowed",
                "target_location_not_allowed",
                "action_role_not_allowed",
                "source_location_mismatch",
                "source_location_anchor_unresolved",
                "presentation_location_drift",
            )
        )
    }
    if fatal_reasons:
        return SemanticObservationValidation(None, tuple(dict.fromkeys(reasons)))
    return SemanticObservationValidation(
        replace(
            observation,
            source_location=source_location,
            target_location=target_location,
            completion_facts=completion_facts,
            candidate_required_facts=required_facts,
            preserved_facts=preserved_facts,
        ),
        tuple(dict.fromkeys(reasons)),
    )


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
    "ActionContract",
    "action_contracts_from_prompt_context",
    "FactEvidenceRule",
    "GeneratedCheckoutData",
    "SemanticExperimentProfile",
    "SemanticObservationValidation",
    "generate_checkout_test_data",
    "practice_shopping_feasibility_profile",
    "resolve_semantic_experiment_profile",
    "validate_profile_semantic_observation",
    "validate_final_order_authorization",
]
