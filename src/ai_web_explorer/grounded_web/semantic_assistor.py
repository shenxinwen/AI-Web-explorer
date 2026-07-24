from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.state_signature import slug_identifier


def _url_pattern_for(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _state_node_id(page_id: str, signature: dict[str, Any]) -> str:
    if not signature:
        return page_id
    payload = json.dumps(signature, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"{page_id}__{digest}"


def _path_label_from_snapshot(snapshot: StateSnapshot) -> str | None:
    raw_path = snapshot.signature.get("url_path")
    if not raw_path:
        raw_path = urlsplit(snapshot.url).path
    path = str(raw_path).strip().strip("/")
    if not path:
        return None
    last_segment = path.rsplit("/", 1)[-1]
    for suffix in (".html", ".htm"):
        if last_segment.lower().endswith(suffix):
            last_segment = last_segment[: -len(suffix)]
            break
    label = slug_identifier(last_segment or path, fallback="")
    return label or None


@dataclass(frozen=True)
class SemanticStateDraft:
    node_id: str
    page_description: str
    page_frame: PageFrame
    state_schema: dict[str, list[Any]]
    last_state_snapshot: dict[str, Any]
    interactable_elements: list[dict[str, Any]]
    evidence: list[Evidence]
    node_label: str | None = None
    state_summary: str | None = None
    naming_provenance: dict[str, Any] | None = None


class SemanticAssistor(Protocol):
    def describe_state(
        self,
        *,
        snapshot: StateSnapshot,
        interactables: list[dict[str, Any]],
    ) -> SemanticStateDraft: ...


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
        node_id = _state_node_id(snapshot.page_id, last_state)
        node_label = _path_label_from_snapshot(snapshot) or slug_identifier(
            snapshot.page_id,
            fallback="state",
        )
        state_summary = f"{node_label} state"
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
            node_id=node_id,
            node_label=node_label,
            state_summary=state_summary,
            naming_provenance={"source": "deterministic_fallback"},
            page_description=f"{node_label} page",
            page_frame=page_frame,
            state_schema={key: [value] for key, value in last_state.items()},
            last_state_snapshot=last_state,
            interactable_elements=[dict(item) for item in interactables],
            evidence=evidence,
        )
