from __future__ import annotations

import json
import math
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from ai_web_explorer.grounded_web.state_summary import StateSummary

EmbeddingProvider = Callable[[str], Sequence[float]]


@dataclass(frozen=True)
class StateEmbeddingRecord:
    node_id: str
    summary_text: str
    embedding: Sequence[float]
    planning_facts: tuple[str, ...] = ()
    context_markers: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "summary_text": self.summary_text,
            "embedding": list(self.embedding),
            "planning_facts": list(self.planning_facts),
            "context_markers": list(self.context_markers),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateEmbeddingRecord":
        return cls(
            node_id=str(data["node_id"]),
            summary_text=str(data["summary_text"]),
            embedding=[float(value) for value in data["embedding"]],
            planning_facts=tuple(str(value) for value in data.get("planning_facts", [])),
            context_markers=tuple(
                str(value) for value in data.get("context_markers", [])
            ),
        )


@dataclass(frozen=True)
class StateMatch:
    status: str
    node_id: str | None
    score: float
    blocked_reason: str | None = None


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(numerator / (left_norm * right_norm), 6)


def _context_compatible(
    current: StateSummary,
    record: StateEmbeddingRecord,
) -> bool:
    current_markers = set(current.context_markers)
    record_markers = set(record.context_markers)
    guarded = {"modal_open", "form_visible", "cart_non_empty"}
    return current_markers.intersection(guarded) == record_markers.intersection(
        guarded
    )


def find_best_state_match(
    current: StateSummary,
    records: Iterable[StateEmbeddingRecord],
    *,
    embedding_provider: EmbeddingProvider,
    same_threshold: float = 0.90,
    ambiguous_threshold: float = 0.82,
) -> StateMatch:
    current_embedding = embedding_provider(current.text)
    best_record: StateEmbeddingRecord | None = None
    best_score = 0.0
    for record in records:
        score = cosine_similarity(current_embedding, record.embedding)
        if score > best_score:
            best_record = record
            best_score = score
    if best_record is None:
        return StateMatch(status="new", node_id=None, score=0.0)
    if best_score >= same_threshold and not _context_compatible(
        current,
        best_record,
    ):
        return StateMatch(
            status="blocked",
            node_id=best_record.node_id,
            score=best_score,
            blocked_reason="context_marker_conflict",
        )
    if best_score >= same_threshold:
        return StateMatch(status="same", node_id=best_record.node_id, score=best_score)
    if best_score >= ambiguous_threshold:
        return StateMatch(
            status="ambiguous",
            node_id=best_record.node_id,
            score=best_score,
        )
    return StateMatch(status="new", node_id=None, score=best_score)


def read_state_embedding_records(path: Path) -> list[StateEmbeddingRecord]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [StateEmbeddingRecord.from_dict(item) for item in data.get("records", [])]


def write_state_embedding_records(
    path: Path,
    records: Iterable[StateEmbeddingRecord],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"records": [record.to_dict() for record in records]}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
        _replace_with_permission_retry(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return path


def _replace_with_permission_retry(
    source: Path,
    target: Path,
    *,
    max_attempts: int = 3,
    delay_seconds: float = 0.05,
) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == max_attempts:
                raise
            time.sleep(delay_seconds)
