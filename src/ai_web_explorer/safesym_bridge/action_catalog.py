from __future__ import annotations

from dataclasses import dataclass, field

from ai_web_explorer.safesym_bridge.dom_observer import (
    DomInteractableCandidate,
)
from ai_web_explorer.safesym_bridge.graph_explorer import ExplorationAction
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.semantic_resolver import SemanticMatch


@dataclass(frozen=True)
class ActionDefinition:
    raw_description: str
    execution_kind: str
    values: dict[str, str] = field(default_factory=dict)
    position: str = ""
    priority: int = 0


class DomainActionCatalog:
    def __init__(
        self,
        definitions: dict[tuple[str, str], ActionDefinition],
        *,
        minimum_confidence: float = 1.0,
    ) -> None:
        self._definitions = definitions
        self._minimum_confidence = minimum_confidence

    def build_actions(
        self,
        state: StateSnapshot,
        matches: list[SemanticMatch],
        candidates: list[DomInteractableCandidate],
    ) -> list[ExplorationAction]:
        candidates_by_id = {candidate.id: candidate for candidate in candidates}
        built: list[tuple[int, ExplorationAction]] = []

        for match in matches:
            if match.confidence < self._minimum_confidence:
                continue
            candidate = candidates_by_id.get(match.candidate_id)
            if candidate is None:
                raise ValueError(f"Missing candidate: {match.candidate_id}")
            key = (state.page_id, match.semantic_id)
            definition = self._definitions.get(key)
            if definition is None:
                raise ValueError(
                    "Missing action definition: "
                    f"{state.page_id}/{match.semantic_id}"
                )
            built.append(
                (
                    definition.priority,
                    ExplorationAction(
                        raw_description=definition.raw_description,
                        semantic_id=match.semantic_id,
                        page_id=state.page_id,
                        execution_kind=definition.execution_kind,
                        selector=candidate.locator,
                        values=dict(definition.values),
                        position=definition.position,
                    ),
                )
            )

        return [action for _, action in sorted(built, key=lambda item: item[0])]
