from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from vera.grounded_web.state_signature import slug_identifier
from vera.grounded_web.structure import (
    PageStructureObservation,
    StructureEvidence,
)


@dataclass(frozen=True)
class AbstractStateFact:
    fact_id: str
    fact_type: str
    value: str | bool | int
    identity_role: str
    source_ref: str
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "value": self.value,
            "identity_role": self.identity_role,
            "source_ref": self.source_ref,
            "evidence": [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in self.evidence
            ],
        }


def _fact_key(prefix: str, value: str) -> str:
    return f"{prefix}_{slug_identifier(value, fallback='unknown')}"


def facts_from_structure(
    observation: PageStructureObservation,
) -> list[AbstractStateFact]:
    facts: list[AbstractStateFact] = []
    path = urlparse(observation.page.url).path or "/"
    facts.append(
        AbstractStateFact(
            fact_id="url_path",
            fact_type="navigation",
            value=path,
            identity_role="identity",
            source_ref="page.url",
            evidence=[
                StructureEvidence(
                    source="browser_location",
                    url=observation.page.url,
                    text_sample=path,
                )
            ],
        )
    )

    for region in observation.regions:
        facts.append(
            AbstractStateFact(
                fact_id=slug_identifier(
                    f"{region.id}_visible",
                    fallback="region_visible",
                ),
                fact_type="visibility",
                value=region.visible,
                identity_role="identity",
                source_ref=region.id,
                evidence=region.evidence,
            )
        )

    for indicator in observation.indicators:
        key = slug_identifier(indicator.key_hint or indicator.id, fallback=indicator.id)
        facts.append(
            AbstractStateFact(
                fact_id=key,
                fact_type="numeric" if isinstance(indicator.value, int) else "visibility",
                value=indicator.value,
                identity_role="identity",
                source_ref=indicator.id,
                evidence=indicator.evidence,
            )
        )
        facts.append(
            AbstractStateFact(
                fact_id=f"{key}_visible",
                fact_type="visibility",
                value=indicator.visible,
                identity_role="identity",
                source_ref=indicator.id,
                evidence=indicator.evidence,
            )
        )

    for group in observation.repeated_groups:
        facts.append(
            AbstractStateFact(
                fact_id=_fact_key("", f"{group.pattern_hint}_count").strip("_"),
                fact_type="repeated_entity_count",
                value=group.count,
                identity_role="identity",
                source_ref=group.id,
                evidence=group.evidence,
            )
        )

    for control in observation.controls:
        if control.visible:
            facts.append(
                AbstractStateFact(
                    fact_id=_fact_key("control", f"{control.id}_enabled"),
                    fact_type="control_availability",
                    value=control.enabled,
                    identity_role="context",
                    source_ref=control.id,
                    evidence=control.evidence,
                )
            )

    return facts


def state_signature_from_facts(
    facts: list[AbstractStateFact],
) -> dict[str, Any]:
    return {
        fact.fact_id: fact.value
        for fact in facts
        if fact.identity_role == "identity"
    }
