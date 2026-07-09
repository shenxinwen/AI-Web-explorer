from dataclasses import FrozenInstanceError

import pytest

from ai_web_explorer.safesym_bridge.semantic_resolver import (
    ResolutionBatch,
    SemanticMatch,
)


def test_semantic_match_is_immutable_and_contains_no_execution_data():
    match = SemanticMatch(
        candidate_id="dom_001",
        semantic_id="login_submit",
        confidence=1.0,
        resolver="saucedemo_rule",
    )

    assert match.candidate_id == "dom_001"
    assert not hasattr(match, "selector")
    assert not hasattr(match, "values")
    with pytest.raises(FrozenInstanceError):
        match.confidence = 0.5


def test_resolution_batch_reports_unmatched_candidates():
    match = SemanticMatch("dom_001", "login_submit", 1.0, "saucedemo_rule")
    batch = ResolutionBatch(
        matches=[match],
        unmatched_candidate_ids=["dom_002"],
    )

    assert batch.matches == [match]
    assert batch.unmatched_candidate_ids == ["dom_002"]
