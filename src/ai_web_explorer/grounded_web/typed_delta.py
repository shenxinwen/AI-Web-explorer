from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import Evidence, ObservedDelta
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


@dataclass(frozen=True)
class TypedStateDelta:
    fact_id: str
    fact_type: str
    delta_type: str
    before: Any
    after: Any
    source_ref: str
    identity_relevant: bool
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "delta_type": self.delta_type,
            "before": self.before,
            "after": self.after,
            "source_ref": self.source_ref,
            "identity_relevant": self.identity_relevant,
            "evidence": [item.to_dict() for item in self.evidence],
        }


def _delta_type_for(fact_type: str) -> str:
    return {
        "navigation": "navigation_changed",
        "visibility": "visibility_changed",
        "numeric": "numeric_changed",
        "form_value": "form_value_changed",
        "control_availability": "control_availability_changed",
        "selection": "selection_changed",
        "repeated_entity_count": "repeated_entity_count_changed",
    }.get(fact_type, "state_fact_changed")


def typed_deltas_from_facts(
    before: list[AbstractStateFact],
    after: list[AbstractStateFact],
) -> list[TypedStateDelta]:
    before_by_id = {fact.fact_id: fact for fact in before}
    after_by_id = {fact.fact_id: fact for fact in after}
    deltas: list[TypedStateDelta] = []
    for fact_id in sorted(set(before_by_id) | set(after_by_id)):
        before_fact = before_by_id.get(fact_id)
        after_fact = after_by_id.get(fact_id)
        before_value = before_fact.value if before_fact is not None else None
        after_value = after_fact.value if after_fact is not None else None
        if before_value == after_value:
            continue
        representative = after_fact or before_fact
        if representative is None:
            continue
        deltas.append(
            TypedStateDelta(
                fact_id=fact_id,
                fact_type=representative.fact_type,
                delta_type=_delta_type_for(representative.fact_type),
                before=before_value,
                after=after_value,
                source_ref=representative.source_ref,
                identity_relevant=representative.identity_role == "identity",
                evidence=representative.evidence,
            )
        )
    return deltas


def _evidence_to_graph(
    evidence: list[StructureEvidence],
    *,
    url: str,
) -> list[Evidence]:
    if not evidence:
        return [Evidence(source="typed_state_delta", url=url)]
    return [
        Evidence(
            source=item.source,
            selector=item.selector,
            text_sample=item.text_sample,
            url=item.url or url,
            confidence=item.confidence,
        )
        for item in evidence
    ]


def observed_deltas_from_typed(
    deltas: list[TypedStateDelta],
    *,
    url: str,
) -> list[ObservedDelta]:
    return [
        ObservedDelta(
            field=delta.fact_id,
            before=delta.before,
            after=delta.after,
            delta_type=delta.delta_type,
            evidence=_evidence_to_graph(delta.evidence, url=url),
        )
        for delta in deltas
    ]
