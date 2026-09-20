"""Deterministically sample the blinded C3 external formal manifest."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote


LABELS = ("SAFE", "LOW", "HIGH")
UUID_SUFFIX = re.compile(
    r"_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DRIVE_ID = re.compile(r"/d/([^/]+)")
STRUCTURED_TARGET_MARKERS = (
    "aria-label",
    "parent node",
    "name op value",
    "value submit",
    "input value",
)


def parse_target_phrase(annotation_folder: str) -> str:
    match = re.match(r"^annot_(?:SAFE|LOW|HIGH)_Tgt_(.+)$", annotation_folder or "")
    if not match:
        return ""
    target = UUID_SUFFIX.sub("", match.group(1))
    return " ".join(unquote(target).replace("_", " ").split()).casefold()


def is_usable_target(target: str) -> bool:
    normalized = target.casefold()
    words = normalized.split()
    return (
        bool(normalized)
        and len(normalized) < 30
        and any(character.isalpha() for character in normalized)
        and normalized != "description unavailable"
        and normalized not in {"on", "off"}
        and (not words or words[0] not in {"name", "value", "title"})
        and " value " not in f" {normalized} "
        and "[" not in normalized
        and "]" not in normalized
        and "aria-" not in normalized
        and not any(marker in normalized for marker in STRUCTURED_TARGET_MARKERS)
    )


def _source_id(screenshot_view: str) -> str:
    match = DRIVE_ID.search(screenshot_view or "")
    return match.group(1) if match else ""


def _eligible_rows(
    raw_rows: list[dict[str, Any]],
    pilot_ids: set[str],
    exclusions: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    exclusions = exclusions if exclusions is not None else Counter()
    rows = []
    for raw in raw_rows:
        label = str(raw.get("Your Review", "")).upper()
        target = parse_target_phrase(str(raw.get("annotation_folder", "")))
        source_id = _source_id(str(raw.get("Screenshot View", "")))
        site = str(raw.get("website", "")).strip()
        if label not in LABELS:
            exclusions["non_final_label"] += 1
            continue
        if not is_usable_target(target):
            exclusions["unusable_target"] += 1
            continue
        if not source_id:
            exclusions["missing_screenshot_id"] += 1
            continue
        if not site:
            exclusions["missing_site"] += 1
            continue
        if source_id in pilot_ids:
            exclusions["pilot_overlap"] += 1
            continue
        rows.append({
            "metadata_action_id": raw.get("action_id"),
            "source_screenshot_id": source_id,
            "screenshot_view": raw.get("Screenshot View", ""),
            "site": site,
            "normalized_target": target,
            "tag": str(raw.get("tagHead", "")),
            "webguard_label": label,
            "webguard_reason": raw.get("Reason"),
            "source_url": raw.get("url", ""),
            "annotation_folder": raw.get("annotation_folder", ""),
        })
    unique = {}
    for row in rows:
        unique.setdefault(row["source_screenshot_id"], row)
    exclusions["duplicate_source_id"] += len(rows) - len(unique)
    return list(unique.values())


def _select_pairs(
    rows: list[dict[str, Any]], rng: random.Random, count: int
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["normalized_target"]].append(row)
    candidates = []
    for target, members in sorted(groups.items()):
        possible = [
            (left, right)
            for left_index, left in enumerate(members)
            for right in members[left_index + 1:]
            if left["site"].casefold() != right["site"].casefold()
            and left["webguard_label"] != right["webguard_label"]
        ]
        if possible:
            candidates.append((target, possible))
    rng.shuffle(candidates)
    selected = []
    used_ids: set[str] = set()
    for _, possible in candidates:
        rng.shuffle(possible)
        choice = next((pair for pair in possible if not {
            pair[0]["source_screenshot_id"], pair[1]["source_screenshot_id"]
        } & used_ids), None)
        if choice is None:
            continue
        selected.append(choice)
        used_ids.update(row["source_screenshot_id"] for row in choice)
        if len(selected) == count:
            return selected
    return selected


def _select_diversity(
    rows: list[dict[str, Any]], used_ids: set[str], rng: random.Random, count: int
) -> list[dict[str, Any]]:
    pool = [row for row in rows if row["source_screenshot_id"] not in used_ids]
    rng.shuffle(pool)
    base, remainder = divmod(count, len(LABELS))
    quotas = {
        label: base + (1 if index < remainder else 0)
        for index, label in enumerate(LABELS)
    }
    selected = []
    site_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    for max_site in (1, 2, 3):
        for row in pool:
            label = row["webguard_label"]
            site_key = row["site"].casefold()
            if quotas[label] <= 0 or site_counts[site_key] >= max_site:
                continue
            if target_counts[row["normalized_target"]] >= 1 and max_site < 3:
                continue
            selected.append(row)
            quotas[label] -= 1
            site_counts[site_key] += 1
            target_counts[row["normalized_target"]] += 1
        if len(selected) == count:
            return selected
    raise ValueError(f"Need {count} diversity samples; selected {len(selected)}")


def _blind_row(row: dict[str, Any], sample_id: str, subset: str, pair_id: str) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "subset": subset,
        "pair_id": pair_id,
        "site": row["site"],
        "normalized_target": row["normalized_target"],
        "action_label": f"Click the target labeled '{row['normalized_target']}'.",
        "screenshot_view": row["screenshot_view"],
        "source_screenshot_id": row["source_screenshot_id"],
    }


def build_formal_manifests(
    metadata_path: Path,
    pilot_manifest_path: Path,
    destination: Path,
    seed: int = 20260920,
) -> dict[str, Any]:
    raw_rows = json.loads(metadata_path.read_text(encoding="utf-8"))
    pilot = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    pilot_ids = {str(row.get("source_screenshot_id", "")) for row in pilot}
    exclusions: Counter[str] = Counter()
    rows = _eligible_rows(raw_rows, pilot_ids, exclusions)
    rng = random.Random(seed)
    pairs = _select_pairs(rows, rng, 30)
    used_ids = {
        row["source_screenshot_id"] for pair in pairs for row in pair
    }
    diversity_count = 100 - 2 * len(pairs)
    diversity = _select_diversity(rows, used_ids, rng, diversity_count)

    blind = []
    audit = []
    sample_index = 1
    for pair_index, pair in enumerate(pairs, 1):
        pair_id = f"PAIR{pair_index:03d}"
        for row in pair:
            sample_id = f"EXTF{sample_index:03d}"
            public = _blind_row(row, sample_id, "context_pair", pair_id)
            blind.append(public)
            audit.append({**public, **row})
            sample_index += 1
    for row in diversity:
        sample_id = f"EXTF{sample_index:03d}"
        public = _blind_row(row, sample_id, "diversity", "")
        blind.append(public)
        audit.append({**public, **row})
        sample_index += 1

    selected_ids = [row["source_screenshot_id"] for row in blind]
    report = {
        "seed": seed,
        "source_rows": len(raw_rows),
        "eligible_source_rows": len(rows),
        "exclusions": dict(exclusions),
        "selected_total": len(blind),
        "context_pair_samples": 2 * len(pairs),
        "context_pairs": len(pairs),
        "diversity_samples": len(diversity),
        "pilot_overlap": len(set(selected_ids) & pilot_ids),
        "duplicate_source_ids": len(selected_ids) - len(set(selected_ids)),
        "subset_counts": dict(Counter(row["subset"] for row in blind)),
        "diversity_label_counts": dict(Counter(row["webguard_label"] for row in audit if row["subset"] == "diversity")),
        "unique_sites": len({row["site"].casefold() for row in blind}),
        "unique_targets": len({row["normalized_target"] for row in blind}),
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "formal_samples_blinded.json").write_text(
        json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destination / "formal_samples_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destination / "sampling_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--pilot-manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260920)
    args = parser.parse_args()
    report = build_formal_manifests(
        args.metadata, args.pilot_manifest, args.destination, args.seed
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
