from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ai_web_explorer.safesym_bridge.capability_graph import Evidence, PageFrame
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import _url_pattern_for


@dataclass(frozen=True)
class SemanticStateDraft:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    interactable_elements: list[dict[str, Any]]
    evidence: list[Evidence]


class SemanticAssistor(Protocol):
    def describe_state(
        self,
        *,
        snapshot: StateSnapshot,
        interactables: list[dict[str, Any]],
    ) -> SemanticStateDraft:
        ...


class DeterministicSemanticAssistor:
    def __init__(self, app: str):
        self.app = app

    def describe_state(
        self,
        *,
        snapshot: StateSnapshot,
        interactables: list[dict[str, Any]],
    ) -> SemanticStateDraft:
        evidence = [
            Evidence(
                source="deterministic_assistor",
                url=snapshot.url,
                confidence=1.0,
            )
        ]
        last_state = dict(snapshot.signature)
        page_frame = PageFrame(
            page_id=f"{self.app}:{snapshot.page_id}",
            page_type=snapshot.page_id,
            url=snapshot.url,
            url_pattern=_url_pattern_for(snapshot.url),
            title=snapshot.title,
            heading=None,
            signature_hints=last_state,
            evidence=evidence,
        )
        return SemanticStateDraft(
            node_id=snapshot.page_id,
            page_description=f"{snapshot.page_id} page",
            page_frame=page_frame,
            state_schema={key: [value] for key, value in last_state.items()},
            last_state_snapshot=last_state,
            interactable_elements=[dict(item) for item in interactables],
            evidence=evidence,
        )
