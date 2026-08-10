from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.state_embedding import (
    StateEmbeddingRecord,
    cosine_similarity,
    find_best_state_match,
    read_state_embedding_records,
    write_state_embedding_records,
)
from ai_web_explorer.grounded_web.state_summary import StateSummary


def fake_embed(text: str):
    if "cart page" in text:
        return [1.0, 0.0, 0.0]
    if "similar product" in text:
        return [0.9, 0.1, 0.0]
    return [0.0, 1.0, 0.0]


def test_cosine_similarity_returns_expected_score():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_find_best_state_match_returns_same_when_embedding_is_high():
    current = StateSummary(
        text="cart page with checkout button",
        context_markers=("cart_non_empty",),
        planning_facts=("cart_has_items",),
    )
    records = [
        StateEmbeddingRecord(
            node_id="cart",
            summary_text="cart page",
            embedding=[1.0, 0.0, 0.0],
            planning_facts=("cart_has_items",),
            context_markers=("cart_non_empty",),
        )
    ]

    match = find_best_state_match(current, records, embedding_provider=fake_embed)

    assert match.status == "same"
    assert match.node_id == "cart"
    assert match.score == 1.0


def test_find_best_state_match_blocks_modal_context_conflict():
    current = StateSummary(
        text="cart page with checkout button",
        context_markers=("cart_non_empty", "modal_open"),
        planning_facts=("cart_has_items",),
    )
    records = [
        StateEmbeddingRecord(
            node_id="cart",
            summary_text="cart page",
            embedding=[1.0, 0.0, 0.0],
            planning_facts=("cart_has_items",),
            context_markers=("cart_non_empty",),
        )
    ]

    match = find_best_state_match(current, records, embedding_provider=fake_embed)

    assert match.status == "blocked"
    assert match.blocked_reason == "context_marker_conflict"


def test_state_embedding_sidecar_round_trips(tmp_path: Path):
    path = tmp_path / "state_embeddings.json"
    records = [
        StateEmbeddingRecord(
            node_id="products",
            summary_text="similar product list",
            embedding=[0.9, 0.1, 0.0],
            planning_facts=("product_list_visible",),
            context_markers=(),
        )
    ]

    write_state_embedding_records(path, records)
    loaded = read_state_embedding_records(path)

    assert loaded == records


def test_failed_embedding_replace_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "state_embeddings.json"
    path.write_text('{"records":[{"node_id":"old"}]}', encoding="utf-8")
    old_bytes = path.read_bytes()
    original_replace = Path.replace

    def fail_target_replace(self, target):
        if Path(target) == path:
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_target_replace)
    with pytest.raises(OSError, match="replace failed"):
        write_state_embedding_records(path, [])

    assert path.read_bytes() == old_bytes
    assert list(tmp_path.glob("*.tmp")) == []
