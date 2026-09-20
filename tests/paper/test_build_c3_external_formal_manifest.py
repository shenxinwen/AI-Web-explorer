import json
from pathlib import Path

from scripts.paper.build_c3_external_formal_manifest import (
    build_formal_manifests,
    is_usable_target,
    parse_target_phrase,
)


def _row(index: int, target: str, site: str, label: str) -> dict:
    screenshot_id = f"drive-{index:04d}"
    return {
        "action_id": index,
        "url": f"https://{site}.example/page/{index}",
        "tagHead": "button",
        "Screenshot View": (
            f"https://drive.google.com/file/d/{screenshot_id}/view?usp=drivesdk"
        ),
        "Annotation": label,
        "Your Review": label,
        "annotation_folder": (
            f"annot_{label}_Tgt_{target.replace(' ', '_')}_"
            f"00000000-0000-0000-0000-{index:012d}"
        ),
        "Reason": f"review reason {index}",
        "website": site,
    }


def _metadata() -> list[dict]:
    rows = []
    index = 1
    labels = ["SAFE", "LOW", "HIGH"]
    # Forty pair-capable target groups, each spanning websites and review labels.
    for group in range(40):
        target = f"shared action {group}"
        rows.append(_row(index, target, f"pair-a-{group}", labels[group % 3]))
        index += 1
        rows.append(_row(index, target, f"pair-b-{group}", labels[(group + 1) % 3]))
        index += 1
    # Sufficient diverse singletons in every stratum.
    for group in range(90):
        rows.append(_row(
            index, f"unique action {group}", f"diverse-{group}", labels[group % 3]
        ))
        index += 1
    return rows


def test_parse_target_phrase_removes_label_and_uuid():
    assert parse_target_phrase(
        "annot_HIGH_Tgt_Save_Changes_12345678-1234-1234-1234-123456789abc"
    ) == "save changes"


def test_structured_accessibility_fragments_are_not_usable_targets():
    assert is_usable_target("save changes")
    assert is_usable_target("aceptar todas las cookies")
    assert not is_usable_target("aria-label close modal")
    assert not is_usable_target("parent node [ select language")
    assert not is_usable_target("name op value submit")
    assert not is_usable_target("input value parent node [")
    assert not is_usable_target("name commit value save settings")
    assert not is_usable_target("value rate content")
    assert not is_usable_target("title facebook")
    assert not is_usable_target("on")
    assert not is_usable_target("aria-describedby r4k aria-")
    assert not is_usable_target("recommended route intermediate")
    assert not is_usable_target("2 390")
    assert not is_usable_target("description unavailable")


def test_build_formal_manifests_is_deterministic_blinded_and_disjoint(tmp_path: Path):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(_metadata()), encoding="utf-8")
    pilot = tmp_path / "pilot.json"
    pilot.write_text(json.dumps([{"source_screenshot_id": "drive-0001"}]), encoding="utf-8")
    first = tmp_path / "first"
    second = tmp_path / "second"

    report = build_formal_manifests(metadata, pilot, first, seed=20260920)
    build_formal_manifests(metadata, pilot, second, seed=20260920)

    blind = json.loads((first / "formal_samples_blinded.json").read_text(encoding="utf-8"))
    audit = json.loads((first / "formal_samples_audit.json").read_text(encoding="utf-8"))
    assert blind == json.loads(
        (second / "formal_samples_blinded.json").read_text(encoding="utf-8")
    )
    assert len(blind) == 100
    assert len({row["source_screenshot_id"] for row in blind}) == 100
    assert "drive-0001" not in {row["source_screenshot_id"] for row in blind}
    assert sum(row["subset"] == "context_pair" for row in blind) == 60
    assert sum(row["subset"] == "diversity" for row in blind) == 40
    pairs = {}
    for row in blind:
        if row["pair_id"]:
            pairs.setdefault(row["pair_id"], []).append(row)
    assert len(pairs) == 30
    assert all(len(pair) == 2 for pair in pairs.values())
    assert all(pair[0]["action_label"] == pair[1]["action_label"] for pair in pairs.values())
    assert all(pair[0]["site"] != pair[1]["site"] for pair in pairs.values())
    assert len({pair[0]["normalized_target"] for pair in pairs.values()}) == 30
    serialized_blind = json.dumps(blind).lower()
    assert "webguard_label" not in serialized_blind
    assert "reason" not in serialized_blind
    assert "https://pair-a" not in serialized_blind
    assert {row["webguard_label"] for row in audit} == {"SAFE", "LOW", "HIGH"}
    assert report["selected_total"] == 100
    assert report["pilot_overlap"] == 0
    assert report["duplicate_source_ids"] == 0
    assert report["source_rows"] == 170
    assert report["exclusions"]["pilot_overlap"] == 1


def test_build_formal_manifests_uses_fewer_pairs_when_quality_pool_is_small(tmp_path: Path):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(_metadata()[:20] + _metadata()[80:]), encoding="utf-8")
    pilot = tmp_path / "pilot.json"
    pilot.write_text("[]", encoding="utf-8")

    report = build_formal_manifests(
        metadata, pilot, tmp_path / "out", seed=20260920
    )

    assert report["context_pairs"] == 10
    assert report["context_pair_samples"] == 20
    assert report["diversity_samples"] == 80
    assert report["selected_total"] == 100
