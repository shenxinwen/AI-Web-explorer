from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_web_explorer.grounded_web.dom_observer import (
    DomInteractableCandidate,
)
from ai_web_explorer.grounded_web.models import StateSnapshot


@dataclass(frozen=True)
class SemanticMatch:
    candidate_id: str
    semantic_id: str
    confidence: float
    resolver: str


@dataclass(frozen=True)
class ResolutionBatch:
    matches: list[SemanticMatch]
    unmatched_candidate_ids: list[str]


class SemanticActionResolver(Protocol):
    async def resolve(
        self,
        state: StateSnapshot,
        candidates: list[DomInteractableCandidate],
    ) -> ResolutionBatch: ...
