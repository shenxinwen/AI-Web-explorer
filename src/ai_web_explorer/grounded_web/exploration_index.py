from __future__ import annotations

from dataclasses import dataclass

from ai_web_explorer.grounded_web.graph import WebKobeGraph
from ai_web_explorer.grounded_web.state_embedding import (
    EmbeddingProvider,
    StateMatch,
    cosine_similarity,
)


@dataclass(frozen=True)
class ExplorationContext:
    current_node_id: str
    reference_node_id: str
    is_revisit: bool
    tried_action_ids: tuple[str, ...]
    avoid_action_ids: tuple[str, ...]
    state_match_status: str | None = None
    state_match_score: float | None = None

    def to_prompt_block(self) -> str:
        lines = [
            "Exploration memory:",
            f"Current graph node: {self.current_node_id}",
        ]
        if self.is_revisit:
            lines.append(
                f"This state appears to revisit node {self.reference_node_id}"
                f" with similarity {self.state_match_score:.2f}."
            )
        if self.tried_action_ids:
            lines.append("Already tried actions: " + ", ".join(self.tried_action_ids))
        if self.avoid_action_ids:
            lines.append("Avoid repeating actions: " + ", ".join(self.avoid_action_ids))
        lines.append(
            "Use this memory only as context for the already selected action. "
            "Do not choose a different business goal from this memory block."
        )
        return "\n".join(lines)


def _unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def semantically_matches_action(
    candidate: str,
    existing: tuple[str, ...],
    *,
    embedding_provider: EmbeddingProvider | None,
    same_threshold: float = 0.90,
) -> bool:
    normalized_candidate = candidate.strip().casefold()
    normalized_existing = {
        action.strip().casefold()
        for action in existing
    }
    if normalized_candidate in normalized_existing:
        return True
    if embedding_provider is None:
        return False

    try:
        candidate_embedding = list(embedding_provider(candidate))
        for action in existing:
            existing_embedding = list(embedding_provider(action))
            if len(candidate_embedding) != len(existing_embedding):
                return False
            if (
                cosine_similarity(candidate_embedding, existing_embedding)
                >= same_threshold
            ):
                return True
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    return False


def build_exploration_context(
    graph: WebKobeGraph,
    *,
    current_node_id: str,
    state_match: StateMatch | None = None,
) -> ExplorationContext:
    reference_node_id = (
        state_match.node_id
        if state_match is not None
        and state_match.status == "same"
        and state_match.node_id is not None
        else current_node_id
    )
    tried: list[str] = []
    avoid: list[str] = []
    for edge in graph.edges:
        if edge.source_node_id != reference_node_id:
            continue
        action_id = edge.action.canonical_action_name or edge.action.semantic_id
        tried.append(action_id)
        if edge.status in {"no_observed_change", "failed_execution"}:
            avoid.append(action_id)
    return ExplorationContext(
        current_node_id=current_node_id,
        reference_node_id=reference_node_id,
        is_revisit=reference_node_id != current_node_id,
        tried_action_ids=_unique(tried),
        avoid_action_ids=_unique(avoid),
        state_match_status=state_match.status if state_match is not None else None,
        state_match_score=state_match.score if state_match is not None else None,
    )
