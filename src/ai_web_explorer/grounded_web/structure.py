from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items
    ]


@dataclass(frozen=True)
class StructureEvidence:
    source: str
    selector: str | None = None
    text_sample: str | None = None
    url: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "selector": self.selector,
            "text_sample": self.text_sample,
            "url": self.url,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PageInfo:
    url: str
    title: str
    page_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "page_id": self.page_id,
        }


@dataclass(frozen=True)
class RegionObservation:
    id: str
    role: str | None
    label: str | None
    visible: bool
    locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "label": self.label,
            "visible": self.visible,
            "locator": self.locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ControlObservation:
    id: str
    kind: str
    role: str | None
    name: str
    locator: str
    locator_strategy: str
    enabled: bool
    visible: bool
    metadata: dict[str, str] = field(default_factory=dict)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role,
            "name": self.name,
            "locator": self.locator,
            "locator_strategy": self.locator_strategy,
            "enabled": self.enabled,
            "visible": self.visible,
            "metadata": dict(self.metadata),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class FormFieldObservation:
    id: str
    kind: str
    name: str
    locator: str
    value: str | bool | int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "locator": self.locator,
            "value": self.value,
            "metadata": dict(self.metadata),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class FormObservation:
    id: str
    locator: str | None = None
    fields: list[FormFieldObservation] = field(default_factory=list)
    submit_controls: list[str] = field(default_factory=list)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "locator": self.locator,
            "fields": _list_to_dict(self.fields),
            "submit_controls": list(self.submit_controls),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class IndicatorObservation:
    id: str
    indicator_type: str
    key_hint: str
    value: str | bool | int
    visible: bool
    locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "indicator_type": self.indicator_type,
            "key_hint": self.key_hint,
            "value": self.value,
            "visible": self.visible,
            "locator": self.locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class RepeatedGroupObservation:
    id: str
    pattern_hint: str
    count: int
    representative_locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_hint": self.pattern_hint,
            "count": self.count,
            "representative_locator": self.representative_locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class PageStructureObservation:
    page: PageInfo
    regions: list[RegionObservation] = field(default_factory=list)
    controls: list[ControlObservation] = field(default_factory=list)
    forms: list[FormObservation] = field(default_factory=list)
    indicators: list[IndicatorObservation] = field(default_factory=list)
    repeated_groups: list[RepeatedGroupObservation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page.to_dict(),
            "regions": _list_to_dict(self.regions),
            "controls": _list_to_dict(self.controls),
            "forms": _list_to_dict(self.forms),
            "indicators": _list_to_dict(self.indicators),
            "repeated_groups": _list_to_dict(self.repeated_groups),
        }
