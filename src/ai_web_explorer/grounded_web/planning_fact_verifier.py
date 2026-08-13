from __future__ import annotations

from typing import Any

from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
)
from ai_web_explorer.grounded_web.exploration_semantics import (
    SemanticExperimentProfile,
)


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _is_zero_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value <= 0


def _is_cart_count_key(key: str) -> bool:
    normalized = key.lower()
    return "cart" in normalized and (
        "count" in normalized or "item" in normalized or "quantity" in normalized
    )


def _add_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _profile_fact_ids(profile: BusinessFlowProfile) -> set[str]:
    return {fact.fact_id for fact in profile.planning_facts}


def verify_planning_delta(
    *,
    profile: BusinessFlowProfile,
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
) -> PlanningDelta:
    profile_fact_ids = _profile_fact_ids(profile)
    candidate_added: list[str] = []
    candidate_removed: list[str] = []
    verified_added: list[str] = []
    verified_removed: list[str] = []
    preserved_profile_facts: list[str] = []
    evidence: list[str] = []

    for fact_id in sorted(profile_fact_ids):
        before = before_signature.get(fact_id)
        after = after_signature.get(fact_id)
        if before == after:
            continue
        if after is True:
            _add_unique(candidate_added, fact_id)
            _add_unique(verified_added, fact_id)
            evidence.append(f"structured fact {fact_id} changed from {before} to true")
        elif before is True and after is False:
            _add_unique(candidate_removed, fact_id)
            _add_unique(verified_removed, fact_id)
            evidence.append(f"structured fact {fact_id} changed from true to false")

    for key in sorted(set(before_signature) | set(after_signature)):
        if not _is_cart_count_key(key):
            continue
        before = before_signature.get(key)
        after = after_signature.get(key)
        if before == after:
            continue
        if _is_zero_number(before) and _is_positive_number(after):
            if "cart_has_items" in profile_fact_ids:
                _add_unique(candidate_added, "cart_has_items")
                _add_unique(verified_added, "cart_has_items")
            evidence.append(f"structured count {key} changed from {before} to {after}")
        elif _is_positive_number(before) and _is_zero_number(after):
            if "cart_has_items" in profile_fact_ids:
                _add_unique(candidate_removed, "cart_has_items")
                _add_unique(verified_removed, "cart_has_items")
            evidence.append(f"structured count {key} changed from {before} to {after}")
        elif _is_positive_number(before) and _is_positive_number(after):
            if "cart_has_items" in profile_fact_ids:
                _add_unique(preserved_profile_facts, "cart_has_items")

    return PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=verified_added,
        verified_removed_facts=verified_removed,
        preserved_profile_facts=preserved_profile_facts,
        profile_fact_ids=sorted(set(candidate_added + candidate_removed)),
        evidence=evidence,
        confidence=1.0 if verified_added or verified_removed else None,
        uncertainty_reason=None,
    )


def verify_experiment_planning_delta(
    *,
    profile: SemanticExperimentProfile,
    observable_change: bool,
    candidate_added_facts: list[str],
    candidate_removed_facts: list[str],
    evidence: list[str],
    structured_delta: PlanningDelta,
) -> PlanningDelta:
    """Merge structured facts and conservatively verify profile-scoped VLM facts."""

    allowed = profile.business_fact_ids
    verified_added = list(structured_delta.verified_added_facts)
    verified_removed = list(structured_delta.verified_removed_facts)
    candidate_added = list(structured_delta.candidate_added_facts)
    candidate_removed = list(structured_delta.candidate_removed_facts)
    evidence_items = list(structured_delta.evidence)
    evidence_items.extend(item for item in evidence if isinstance(item, str) and item.strip())
    has_evidence = any(item.strip() for item in evidence if isinstance(item, str))

    for fact_id in candidate_added_facts:
        if fact_id not in allowed:
            continue
        _add_unique(candidate_added, fact_id)
        if observable_change and has_evidence:
            _add_unique(verified_added, fact_id)
    for fact_id in candidate_removed_facts:
        if fact_id not in allowed:
            continue
        _add_unique(candidate_removed, fact_id)
        if observable_change and has_evidence:
            _add_unique(verified_removed, fact_id)

    profile_fact_ids = sorted(
        set(fact_id for fact_id in verified_added + verified_removed if fact_id in allowed)
    )
    return PlanningDelta(
        candidate_added_facts=candidate_added,
        candidate_removed_facts=candidate_removed,
        verified_added_facts=verified_added,
        verified_removed_facts=verified_removed,
        preserved_profile_facts=list(structured_delta.preserved_profile_facts),
        profile_fact_ids=profile_fact_ids,
        generated_fact_ids=list(structured_delta.generated_fact_ids),
        evidence=evidence_items,
        confidence=1.0 if verified_added or verified_removed else structured_delta.confidence,
        uncertainty_reason=structured_delta.uncertainty_reason,
    )


__all__ = ["verify_experiment_planning_delta", "verify_planning_delta"]
