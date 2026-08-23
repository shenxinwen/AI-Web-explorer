"""Persisted candidate memory scoped by semantic location.

This module owns exploration bookkeeping only.  Browser execution and graph
edge creation remain in the explorer, while PDDL projection never consumes
this control state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from ai_web_explorer.grounded_web.graph import BusinessAffordance, WebKobeGraph
from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    VisualAffordanceResult,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id


LOCATION_EXPLORATION_META_KEY = "location_exploration_memory"
LOCATION_EXPLORATION_SCHEMA_VERSION = "location-exploration-v1"

TERMINAL_CANDIDATE_STATUSES = frozenset(
    {
        "success",
        "blocked_by_failed_requirement",
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
    requires: list[str] = field(default_factory=list)
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
            "requires": list(self.requires),
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
            requires=_normalized_ids(data.get("requires") or []),
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


@dataclass(frozen=True)
class OutcomeUpdate:
    attempt: CandidateAttemptOutcome | None
    new_location: bool
    targeted_scan_required: bool
    has_progress: bool
    step_kind: str


@dataclass(frozen=True)
class CandidatePreflightResult:
    """Deterministic DOM preflight evidence for one remembered candidate."""

    status: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"available", "stale", "unknown"}:
            raise ValueError(f"invalid candidate preflight status: {self.status}")


class LocationExplorationCoordinator:
    """Coordinate location-level scans and candidate lifecycle bookkeeping."""

    def __init__(
        self,
        *,
        memory: LocationExplorationMemory | None = None,
        limits: ExplorationLimits | None = None,
    ) -> None:
        if memory is None:
            memory = LocationExplorationMemory(limits=limits)
        elif limits is not None and memory.limits != limits:
            memory.limits = limits
        self.memory = memory

    def ensure_candidates(
        self,
        location_id: str,
        *,
        goal: str,
        screenshot_path: str,
        current_signature: dict[str, Any] | None,
        provider: Callable[..., str] | None,
        max_actions: int | None = None,
        scan_kind: str = "initial",
        added_business_facts: Iterable[str] = (),
        removed_business_facts: Iterable[str] = (),
    ) -> tuple[str, VisualAffordanceResult | None, tuple[str, ...]]:
        """Ensure a pool exists, scanning only when this location requires it."""

        normalized_location = normalize_semantic_id(location_id)
        pool = self.memory.pool_for(normalized_location)
        kind = normalize_semantic_id(scan_kind) or "initial"
        if kind == "initial" and pool.initial_scan_complete:
            return normalized_location, None, ()
        if kind == "supplement" and pool.supplement_scan_complete:
            return normalized_location, None, ()
        if kind == "targeted" and not self.memory.should_run_targeted_scan(
            normalized_location,
            added=added_business_facts,
            removed=removed_business_facts,
        ):
            return normalized_location, None, ()
        if provider is None:
            if kind == "initial":
                pool.initial_scan_complete = True
            elif kind == "supplement":
                pool.supplement_scan_complete = True
            elif kind == "targeted":
                self.memory.mark_targeted_scan_complete(
                    normalized_location,
                    added=added_business_facts,
                    removed=removed_business_facts,
                )
            return normalized_location, None, ()

        result: VisualAffordanceResult | None = None
        added: tuple[str, ...] = ()
        max_attempts = max(1, self.memory.limits.max_vlm_scan_attempts)
        for attempt_index in range(max_attempts):
            request = VisualAffordanceRequest(
                goal=goal,
                current_screenshot_path=screenshot_path,
                current_signature=current_signature,
                max_actions=max_actions or self.memory.limits.max_candidates_per_location,
                scan_kind=kind,
                semantic_location=normalized_location,
                existing_action_ids=sorted(pool.candidates),
                completed_action_ids=sorted(pool.completed_action_ids()),
                added_business_facts=list(added_business_facts),
                removed_business_facts=list(removed_business_facts),
            )
            result = summarize_visual_affordances(request, provider=provider)
            if result.trace.status == "summarized":
                result_location = normalize_semantic_id(result.location_id or "")
                if kind == "initial" and result_location:
                    provisional_location = normalized_location
                    provisional_pool = pool
                    normalized_location = result_location
                    pool = self.memory.pool_for(normalized_location)
                    if (
                        provisional_location != normalized_location
                        and not provisional_pool.candidates
                        and not provisional_pool.audit_log
                    ):
                        self.memory.locations.pop(provisional_location, None)
                added = self.memory.merge_scan(
                    normalized_location,
                    result.business_affordances,
                    kind=kind,
                    requires_by_action_id=result.requires_by_action_id,
                    replacements=result.replacements,
                    disabled_action_ids=result.disabled_action_ids,
                    trace=result.trace.to_dict(),
                )
                if kind == "targeted":
                    self.memory.mark_targeted_scan_complete(
                        normalized_location,
                        added=added_business_facts,
                        removed=removed_business_facts,
                    )
                break

            # Keep the trace for audit but allow the configured retry count.
            self.memory.merge_scan(
                normalized_location,
                [],
                kind=kind,
                trace={"trace": result.trace.to_dict(), "attempt": attempt_index + 1},
            )
            pool = self.memory.pool_for(normalized_location)
            if kind == "initial":
                pool.initial_scan_complete = False
            elif kind == "supplement":
                pool.supplement_scan_complete = False
            if attempt_index + 1 == max_attempts:
                if kind == "initial":
                    pool.initial_scan_complete = True
                elif kind == "supplement":
                    pool.supplement_scan_complete = True
        return normalized_location, result, added

    def preflight_candidate(
        self,
        affordance: BusinessAffordance,
        current_interactables: Iterable[dict[str, Any]] | None,
    ) -> CandidatePreflightResult:
        """Classify a candidate using only exact DOM metadata.

        Missing or ambiguous DOM evidence remains executable as ``unknown``;
        only explicit absence, invisibility, or disabled state is stale.
        """

        candidate_id = normalize_semantic_id(affordance.action_name)
        interactables = [
            item for item in (current_interactables or ()) if isinstance(item, dict)
        ]
        id_matches = [
            item for item in interactables if candidate_id in _interactable_ids(item)
        ]
        if id_matches:
            return _preflight_records(id_matches, basis="canonical_id")

        target = (
            normalize_semantic_id(affordance.target_hint)
            if affordance.target_hint
            else ""
        )
        if target:
            target_matches = [
                item
                for item in interactables
                if target in _interactable_targets(item)
            ]
            if target_matches:
                return _preflight_records(target_matches, basis="target")

        return CandidatePreflightResult(
            "unknown",
            ("no exact canonical ID or target evidence",),
        )

    def select_candidate(
        self,
        location_id: str,
        *,
        current_interactables: Iterable[dict[str, Any]] | None = None,
        active_business_facts: Iterable[str] = (),
    ) -> tuple[BusinessAffordance | None, CandidatePreflightResult | None]:
        """Select the next candidate and retire only conclusively stale ones."""

        pool = self.memory.pool_for(location_id)
        gated_action_ids: set[str] = set()
        last_preflight: CandidatePreflightResult | None = None
        while True:
            candidate = self.memory.next_candidate(
                location_id,
                excluded_action_ids=gated_action_ids,
            )
            if candidate is None:
                return None, last_preflight
            result = self.preflight_candidate(candidate, current_interactables)
            if result.status != "stale":
                return candidate, result
            record = pool.candidates.get(normalize_semantic_id(candidate.action_name))
            if record is None:
                return None, result
            record.status = "stale/disabled"
            last_preflight = result

    def record_action_outcome(
        self,
        *,
        location_before: str,
        location_after: str,
        action_id: str,
        observable_change: bool,
        completion_facts: Iterable[str] = (),
        business_added: Iterable[str] = (),
        business_removed: Iterable[str] = (),
        failed: bool = False,
    ) -> OutcomeUpdate:
        location_before = normalize_semantic_id(location_before)
        location_after = normalize_semantic_id(location_after or location_before)
        action_id = normalize_semantic_id(action_id)
        completion_facts = list(completion_facts)
        business_added = list(business_added)
        business_removed = list(business_removed)
        pool = self.memory.pool_for(location_before)
        attempt: CandidateAttemptOutcome | None = None
        candidate_was_terminal = False
        if action_id in pool.candidates:
            candidate_was_terminal = pool.candidates[action_id].terminal
            attempt = self.memory.record_attempt(
                location_before,
                action_id,
                observable_change=observable_change,
                failed=failed,
            )
        added = business_added
        removed = business_removed
        new_location = location_after != location_before
        targeted = self.memory.should_run_targeted_scan(
            location_before,
            added=added,
            removed=removed,
        )
        has_progress = bool(
            new_location
            or completion_facts
            or added
            or removed
            or (
                attempt is not None
                and attempt.status == "success"
                and not candidate_was_terminal
            )
        )
        if new_location:
            step_kind = "location_transition"
        elif added or removed:
            step_kind = "business_fact_change"
        elif completion_facts:
            step_kind = "completion_fact_change"
        elif observable_change:
            step_kind = "observable_action"
        else:
            step_kind = "no_observable_change"
        return OutcomeUpdate(
            attempt=attempt,
            new_location=new_location,
            targeted_scan_required=targeted,
            has_progress=has_progress,
            step_kind=step_kind,
        )

    def sync_graph_meta(self, manager: Any) -> None:
        manager.meta[LOCATION_EXPLORATION_META_KEY] = self.memory.to_dict()

    def affordances_for(self, location_id: str) -> list[BusinessAffordance]:
        pool = self.memory.pool_for(location_id)
        return [
            pool.candidates[action_id].affordance
            for action_id in sorted(
                pool.candidates,
                key=lambda action_id: (
                    pool.candidates[action_id].discovery_order,
                    action_id,
                ),
            )
        ]


def _interactable_ids(item: dict[str, Any]) -> set[str]:
    values = {
        normalize_semantic_id(item.get(key))
        for key in ("canonical_action_name", "semantic_id", "action_name")
        if item.get(key) is not None
    }
    return {value for value in values if value}


def _interactable_targets(item: dict[str, Any]) -> set[str]:
    values = {
        normalize_semantic_id(item.get(key))
        for key in ("target", "action_label", "description", "text")
        if item.get(key) is not None
    }
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        values.update(
            normalize_semantic_id(metadata.get(key))
            for key in ("aria-label", "data-test", "id", "placeholder", "title")
            if metadata.get(key) is not None
        )
    return {value for value in values if value}


def _preflight_records(
    records: list[dict[str, Any]],
    *,
    basis: str,
) -> CandidatePreflightResult:
    if len(records) != 1:
        return CandidatePreflightResult(
            "unknown",
            (f"ambiguous exact {basis} evidence",),
        )
    item = records[0]
    if (
        item.get("disabled") is True
        or item.get("enabled") is False
        or str(item.get("aria_disabled", "")).lower() == "true"
        or item.get("present") is False
        or item.get("exists") is False
        or item.get("visible") is False
    ):
        return CandidatePreflightResult(
            "stale",
            (f"exact {basis} target is explicitly absent or disabled",),
        )
    if item.get("visible") is True and item.get("enabled") is True:
        return CandidatePreflightResult(
            "available",
            (f"exact {basis} target is visible and enabled",),
        )
    return CandidatePreflightResult(
        "unknown",
        (f"exact {basis} target lacks complete visibility metadata",),
    )


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
        requires_by_action_id: Mapping[str, Iterable[str]] | None = None,
        replacements: Iterable[tuple[str, str]] = (),
        disabled_action_ids: Iterable[str] = (),
        trace: dict[str, Any] | None = None,
    ) -> tuple[str, ...]:
        """Merge scan results by canonical action, returning newly added IDs."""

        pool = self.pool_for(location_id)
        disabled_action_ids = tuple(disabled_action_ids)
        normalized_kind = normalize_semantic_id(kind) or "initial"
        pool.scan_attempts[normalized_kind] = (
            pool.scan_attempts.get(normalized_kind, 0) + 1
        )

        for old_action, new_action in replacements:
            old_id = normalize_semantic_id(old_action)
            if old_id in pool.candidates:
                pool.candidates[old_id].status = "stale/disabled"
            if new_action:
                disabled_action_ids = disabled_action_ids + (old_id,)

        for action_id in disabled_action_ids:
            normalized = normalize_semantic_id(action_id)
            if normalized in pool.candidates:
                pool.candidates[normalized].status = "stale/disabled"

        added: list[str] = []
        affordances = tuple(affordances)
        normalized_requires = {
            normalize_semantic_id(action_id): _normalized_ids(requirements)
            for action_id, requirements in (requires_by_action_id or {}).items()
            if normalize_semantic_id(action_id)
        }
        known_scan_ids = {
            normalize_semantic_id(affordance.action_name)
            for affordance in affordances
            if normalize_semantic_id(affordance.action_name)
        }
        for affordance in affordances:
            action_id = normalize_semantic_id(affordance.action_name)
            if not action_id:
                continue
            normalized_affordance = _normalized_affordance(affordance, action_id)
            requires = [
                requirement
                for requirement in normalized_requires.get(action_id, [])
                if requirement in known_scan_ids and requirement != action_id
            ]
            existing = pool.candidates.get(action_id)
            if existing is not None:
                if not existing.terminal:
                    existing.affordance = normalized_affordance
                    existing.requires = requires
                continue
            if len(pool.candidates) >= self.limits.max_candidates_per_location:
                continue
            pool.candidates[action_id] = LocationCandidateRecord(
                affordance=normalized_affordance,
                requires=requires,
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

    def next_candidate(
        self,
        location_id: str,
        *,
        excluded_action_ids: Iterable[str] = (),
    ) -> BusinessAffordance | None:
        pool = self.pool_for(location_id)
        self._propagate_failed_requirements(pool)
        excluded = {
            normalize_semantic_id(action_id)
            for action_id in excluded_action_ids
            if normalize_semantic_id(action_id)
        }
        eligible = [
            record
            for record in pool.candidates.values()
            if record.status
            in {"pending", "retryable_no_change", "retryable_failure"}
            and record.attempts < self.limits.max_action_attempts_per_candidate
            and record.action_id not in excluded
            and all(
                requirement in pool.candidates
                and pool.candidates[requirement].status == "success"
                for requirement in record.requires
            )
        ]
        if not eligible:
            return None
        relevance = {"core": 0, "supporting": 1, "low_value": 2, "unknown": 3}
        return min(
            eligible,
            key=lambda item: (
                0
                if item.requires
                or any(
                    item.action_id in other.requires
                    for other in pool.candidates.values()
                )
                else 1,
                relevance.get(item.affordance.relevance_hint, 3),
                -(item.affordance.confidence or 0.0),
                item.discovery_order,
                item.action_id,
            ),
        ).affordance

    @staticmethod
    def _propagate_failed_requirements(pool: LocationCandidatePool) -> None:
        changed = True
        while changed:
            changed = False
            for record in pool.candidates.values():
                if record.terminal or not record.requires:
                    continue
                if any(
                    requirement not in pool.candidates
                    or pool.candidates[requirement].status
                    in TERMINAL_CANDIDATE_STATUSES - {"success"}
                    for requirement in record.requires
                ):
                    record.status = "blocked_by_failed_requirement"
                    changed = True

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
        self._propagate_failed_requirements(pool)
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
        execution_policy=affordance.execution_policy,
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
            execution_policy=str(data.get("execution_policy", "single_instance")),
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
    "LocationExplorationCoordinator",
    "OutcomeUpdate",
    "TargetedScanKey",
]
