from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from ai_web_explorer.grounded_web.dom_observer import DomInteractableCandidate

FactValue: TypeAlias = bool | int | float | str | None


@dataclass(frozen=True)
class PageIdentity:
    page_id: str
    url: str
    title: str = ""


@dataclass(frozen=True)
class ObservationEvidence:
    source: str
    selector: str | None = None
    url: str | None = None
    text: str | None = None
    attribute: str | None = None
    raw_value: str | None = None


@dataclass(frozen=True)
class ObservedFact:
    path: str
    value: FactValue
    evidence: list[ObservationEvidence] = field(default_factory=list)
    confidence: float = 1.0
    derived: bool = False


@dataclass(frozen=True)
class WebObservation:
    identity: PageIdentity
    facts: dict[str, ObservedFact]
    interactables: list[DomInteractableCandidate] = field(default_factory=list)
    observer: str = ""

    def to_signature(self) -> dict[str, FactValue]:
        return {path: fact.value for path, fact in self.facts.items()}
