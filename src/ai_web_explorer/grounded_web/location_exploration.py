"""Persisted candidate memory scoped by semantic location.

This module owns exploration bookkeeping only.  Browser execution and graph
edge creation remain in the explorer, while PDDL projection never consumes
this control state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ai_web_explorer.grounded_web.graph import BusinessAffordance, WebKobeGraph
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id


LOCATION_EXPLORATION_META_KEY = "location_exploration_memory"
LOCATION_EXPLORATION_SCHEMA_VERSION = "location-exploration-v1"

TERMINAL_CANDIDATE_STATUSES = frozenset(
    {
        "success",
        "no_observable_change",
        "failed_retry_exhausted",
        "stale/disabled",
    }
)


@dataclass(frozen=True)
class ExplorationLimits:
    max_exploration_steps: int = 20
    max_consecutive_no_progress: int = 3
    max_action_attempts_per_candidate: int = 2
    max_replay_attempts_per_frontier: int = 2
    max_total_replays: int = 4
    max_vlm_scan_attempts: int = 2
    max_candidates_per_location: int = 8

    def to_dict(self) -> dict[str, int]:
        return {
            "max_exploration_steps": self.max_exploration_steps,
            "max_consecutive_no_progress": self.max_consecutive_no_progress,
            "max_action_attempts_per_candidate": self.max_action_attempts_per_candidate,
            "max_replay_attempts_per_frontier": self.max_replay_attempts_per_frontier,
            "max_total_replays": self.max_total_replays,
            "max_vlm_scan_attempts": self.max_vlm_scan_attempts,
            "max_candidates_per_location": self.max_candidates_per_location,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExplorationLimits":
        if not data:
            return cls()
        defaults = cls().to_dict()
        values = {
            key: int(data.get(key, default))
            for key, default in defaults.items()
        }
        return cls(**values)


@dataclass(frozen=True, order=True)
class TargetedScanKey:
    location_id: str
    added_business_facts: tuple[str, ...]
    removed_business_facts: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "location_id", normalize_semantic_id(self.location_id))
        object.__setattr__(
            self,
            "added_business_facts",
            tuple(sorted(_normalized_ids(self.added_business_facts))),
        )
        object.__setattr__(
            self,
            "removed_business_facts",
            tuple(sorted(_normalized_ids(self.removed_business_facts))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "added_business_facts": list(self.added_business_facts),
            "removed_business_facts": list(self.removed_business_facts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetedScanKey":
        return cls(
            location_id=str(data.get("location_id", "")),
            added_business_facts=tuple(data.get("added_business_facts", [])),
            removed_business_facts=tuple(data.get("removed_business_facts", [])),
        )


@dataclass
class LocationCandidateRecord:
    affordance: BusinessAffordance
    status: str = "pending"
    attempts: int = 0
    discovery_order: int = 0
    last_error: str | None = None

    @property
    def action_id(self) -> str:
        return normalize_semantic_id(self.affordance.action_name)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_CANDIDATE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "affordance": self.affordance.to_dict(),
            "status": self.status,
            "attempts": self.attempts,
            "discovery_order": self.discovery_order,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocationCandidateRecord":
        affordance_data = data.get("affordance") or data
        affordance = _affordance_from_dict(affordance_data)
        return cls(
            affordance=affordance,
            status=str(data.get("status", "pending")),
            attempts=int(data.get("attempts", 0)),
            discovery_order=int(data.get("discovery_order", 0)),
            last_error=data.get("last_error"),
        )


@dataclass
class LocationCandidatePool:
    location_id: str
    candidates: dict[str, LocationCandidateRecord] = field(default_factory=dict)
    initial_scan_complete: bool = False
    supplement_scan_complete: bool = False
    scan_attempts: dict[str, int] = field(default_factory=dict)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.location_id = normalize_semantic_id(self.location_id)

    @property
    def exhausted(self) -> bool:
        return bool(self.candidates) and all(
            record.terminal for record in self.candidates.values()
        )

    def completed_action_ids(self) -> set[str]:
        return {
            action_id
            for action_id, record in self.candidates.items()
            if record.terminal
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "candidates": {
                action_id: self.candidates[action_id].to_dict()
                for action_id in sorted(self.candidates)
            },
            "initial_scan_complete": self.initial_scan_complete,
            "supplement_scan_complete": self.supplement_scan_complete,
            "scan_attempts": {
                key: int(self.scan_attempts[key])
                for key in sorted(self.scan_attempts)
            },
            "audit_log": [_sorted_json_value(item) for item in self.audit_log],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocationCandidatePool":
        raw_candidates = data.get("candidates") or {}
        candidates: dict[str, LocationCandidateRecord] = {}
        for key, value in raw_candidates.items():
            if not isinstance(value, dict):
                continue
            record = LocationCandidateRecord.from_dict(value)
            candidates[normalize_semantic_id(key) or record.action_id] = record
        raw_attempts = data.get("scan_attempts") or {}
        scan_attempts = {
            normalize_semantic_id(key): int(value)
            for key, value in raw_attempts.items()
            if normalize_semantic_id(key)
        }
        audit_log = data.get("audit_log")
        if not isinstance(audit_log, list):
            audit_log = []
        return cls(
            location_id=str(data.get("location_id", "")),
            candidates={key: candidates[key] for key in sorted(candidates)},
            initial_scan_complete=bool(data.get("initial_scan_complete", False)),
            supplement_scan_complete=bool(
                data.get("supplement_scan_complete", False)
            ),
            scan_attempts=scan_attempts,
            audit_log=[item for item in audit_log if isinstance(item, dict)],
        )


@dataclass(frozen=True)
class CandidateAttemptOutcome:
    location_id: str
    action_id: str
    status: str
    attempts: int
    terminal: bool


class LocationExplorationMemory:
    """Location-keyed candidate pools and persisted scan/outcome memory."""

    def __init__(
        self,
        *,
        limits: ExplorationLimits | None = None,
        locations: dict[str, LocationCandidatePool] | None = None,
        completed_targeted_scans: Iterable[TargetedScanKey] | None = None,
    ) -> None:
        self.limits = limits or ExplorationLimits()
        self.locations: dict[str, LocationCandidatePool] = {}
        for key, pool in (locations or {}).items():
            normalized = normalize_semantic_id(key)
            pool.location_id = normalized
            self.locations[normalized] = pool
        self.completed_targeted_scans = set(completed_targeted_scans or ())

    def pool_for(self, location_id: str) -> LocationCandidatePool:
        normalized = normalize_semantic_id(location_id)
        if not normalized:
            raise ValueError("semantic location must not be empty")
        if normalized not in self.locations:
            self.locations[normalized] = LocationCandidatePool(normalized)
        return self.locations[normalized]

    def completed_action_ids(self, location_id: str) -> set[str]:
        return self.pool_for(location_id).completed_action_ids()

    def merge_scan(
        self,
        location_id: str,
        affordances: Iterable[BusinessAffordance],
        *,
        kind: str = "initial",
        replacements: Iterable[tuple[str, str]] = (),
        disabled_action_ids: Iterable[str] = (),
        trace: dict[str, Any] | None = None,
    ) -> tuple[str, ...]:
        """Merge scan results by canonical action, returning newly added IDs."""

        pool = self.pool_for(location_id)
        normalized_kind = normalize_semantic_id(kind) or "initial"
        pool.scan_attempts[normalized_kind] = (
            pool.scan_attempts.get(normalized_kind, 0) + 1
        )

        for old_action, new_action in replacements:
            old_id = normalize_semantic_id(old_action)
            if old_id in pool.candidates:
                pool.candidates[old_id].status = "stale/disabled"
            if new_action:
                disabled_action_ids = tuple(disabled_action_ids) + (old_id,)

        for action_id in disabled_action_ids:
            normalized = normalize_semantic_id(action_id)
            if normalized in pool.candidates:
                pool.candidates[normalized].status = "stale/disabled"

        added: list[str] = []
        for affordance in affordances:
            action_id = normalize_semantic_id(affordance.action_name)
            if not action_id:
                continue
            normalized_affordance = _normalized_affordance(affordance, action_id)
            existing = pool.candidates.get(action_id)
            if existing is not None:
                if not existing.terminal:
                    existing.affordance = normalized_affordance
                continue
            if len(pool.candidates) >= self.limits.max_candidates_per_location:
                continue
            pool.candidates[action_id] = LocationCandidateRecord(
                affordance=normalized_affordance,
                discovery_order=len(pool.candidates),
            )
            added.append(action_id)

        if normalized_kind == "initial":
            pool.initial_scan_complete = True
        elif normalized_kind == "supplement":
            pool.supplement_scan_complete = True
        if trace is not None:
            pool.audit_log.append(
                {
                    "kind": normalized_kind,
                    "trace": _sorted_json_value(trace),
                    "added_action_ids": sorted(added),
                }
            )
        return tuple(added)

    def next_candidate(self, location_id: str) -> BusinessAffordance | None:
        pool = self.pool_for(location_id)
        eligible = [
            record
            for record in pool.candidates.values()
            if record.status
            in {"pending", "retryable_no_change", "retryable_failure"}
            and record.attempts < self.limits.max_action_attempts_per_candidate
        ]
        if not eligible:
            return None
        relevance = {"core": 0, "supporting": 1, "low_value": 2, "unknown": 3}
        return min(
            eligible,
            key=lambda item: (
                relevance.get(item.affordance.relevance_hint, 3),
                -(item.affordance.confidence or 0.0),
                item.discovery_order,
                item.action_id,
            ),
        ).affordance

    def record_attempt(
        self,
        location_id: str,
        action_id: str,
        *,
        observable_change: bool,
        failed: bool = False,
        error: str | None = None,
    ) -> CandidateAttemptOutcome:
        normalized_location = normalize_semantic_id(location_id)
        normalized_action = normalize_semantic_id(action_id)
        pool = self.pool_for(normalized_location)
        record = pool.candidates.get(normalized_action)
        if record is None:
            raise KeyError(
                f"candidate {normalized_action!r} is not known at "
                f"location {normalized_location!r}"
            )
        if record.terminal:
            return CandidateAttemptOutcome(
                normalized_location,
                normalized_action,
                record.status,
                record.attempts,
                True,
            )

        record.attempts += 1
        record.last_error = error
        if observable_change:
            record.status = "success"
        elif failed:
            record.status = (
                "failed_retry_exhausted"
                if record.attempts >= self.limits.max_action_attempts_per_candidate
                else "retryable_failure"
            )
        else:
            record.status = (
                "no_observable_change"
                if record.attempts >= self.limits.max_action_attempts_per_candidate
                else "retryable_no_change"
            )
        return CandidateAttemptOutcome(
            normalized_location,
            normalized_action,
            record.status,
            record.attempts,
            record.terminal,
        )

    def should_run_targeted_scan(
        self,
        location_id: str,
        *,
        added: Iterable[str],
        removed: Iterable[str],
    ) -> bool:
        key = TargetedScanKey(
            normalize_semantic_id(location_id),
            tuple(added),
            tuple(removed),
        )
        return bool(key.added_business_facts or key.removed_business_facts) and (
            key not in self.completed_targeted_scans
        )

    def mark_targeted_scan_complete(
        self,
        location_id: str,
        *,
        added: Iterable[str],
        removed: Iterable[str],
    ) -> TargetedScanKey:
        key = TargetedScanKey(
            normalize_semantic_id(location_id),
            tuple(added),
            tuple(removed),
        )
        if key.added_business_facts or key.removed_business_facts:
            self.completed_targeted_scans.add(key)
        return key

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": LOCATION_EXPLORATION_SCHEMA_VERSION,
            "limits": self.limits.to_dict(),
            "locations": {
                key: self.locations[key].to_dict()
                for key in sorted(self.locations)
            },
            "completed_targeted_scans": [
                key.to_dict() for key in sorted(self.completed_targeted_scans)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LocationExplorationMemory":
        if not data:
            return cls()
        version = data.get("version")
        if version != LOCATION_EXPLORATION_SCHEMA_VERSION:
            raise ValueError(f"unknown location exploration schema version: {version}")
        raw_locations = data.get("locations") or {}
        locations = {
            normalize_semantic_id(key): LocationCandidatePool.from_dict(value)
            for key, value in raw_locations.items()
            if isinstance(value, dict) and normalize_semantic_id(key)
        }
        raw_keys = data.get("completed_targeted_scans") or []
        keys = {
            TargetedScanKey.from_dict(item)
            for item in raw_keys
            if isinstance(item, dict)
        }
        return cls(
            limits=ExplorationLimits.from_dict(data.get("limits")),
            locations=locations,
            completed_targeted_scans=keys,
        )

    @classmethod
    def from_graph(cls, graph: WebKobeGraph) -> "LocationExplorationMemory":
        return cls.from_dict(graph.meta.get(LOCATION_EXPLORATION_META_KEY))

    def sync_graph_meta(self, graph: WebKobeGraph) -> None:
        graph.meta[LOCATION_EXPLORATION_META_KEY] = self.to_dict()


def _normalized_ids(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = normalize_semantic_id(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalized_affordance(
    affordance: BusinessAffordance,
    action_id: str,
) -> BusinessAffordance:
    return BusinessAffordance(
        action_name=action_id,
        label=affordance.label,
        relevance_hint=affordance.relevance_hint,
        target_hint=affordance.target_hint,
        source=affordance.source,
        confidence=affordance.confidence,
        supporting_facts=_normalized_ids(affordance.supporting_facts),
    )


def _affordance_from_dict(data: dict[str, Any]) -> BusinessAffordance:
    return _normalized_affordance(
        BusinessAffordance(
            action_name=str(data.get("action_name", data.get("action_id", ""))),
            label=data.get("label"),
            relevance_hint=str(data.get("relevance_hint", "unknown")),
            target_hint=data.get("target_hint"),
            source=str(data.get("source", "json")),
            confidence=data.get("confidence"),
            supporting_facts=list(data.get("supporting_facts") or []),
        ),
        normalize_semantic_id(data.get("action_name", data.get("action_id", ""))),
    )


def _sorted_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted_json_value(item) for item in value]
    return value


__all__ = [
    "CandidateAttemptOutcome",
    "ExplorationLimits",
    "LOCATION_EXPLORATION_META_KEY",
    "LocationCandidatePool",
    "LocationCandidateRecord",
    "LocationExplorationMemory",
    "TargetedScanKey",
]
