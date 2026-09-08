"""Build a small, prediction-blind annotation package from exploration artifacts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from pathlib import Path
from typing import Any, Iterable


C1_COLUMNS = [
    "sample_id", "sample_valid", "invalid_reason",
    "function_exists", "functional_outcome", "notes",
]
C3_COLUMNS = ["sample_id", "potential_risk", "risk_type", "evidence", "notes"]


def _resolve_screenshot(value: str | None, source_root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = source_root / path
    return path.resolve()


def extract_samples(
    site: str, graph_path: Path, evidence_path: Path, source_root: Path
) -> list[dict[str, Any]]:
    """Return only annotator-visible fields; model outcome/risk predictions are excluded."""
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_by_edge = evidence.get("edges", {})
    evidence_by_event = evidence.get("execution_events", {})
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    records = graph.get("execution_events") or graph.get("edges", [])
    for index, edge in enumerate(records, 1):
        edge_id = edge.get("edge_id", "")
        detail = evidence_by_event.get(edge.get("evidence_ref", ""))
        if detail is None:
            detail = evidence_by_edge.get(f"edge-evidence:{edge_id}", {})
        metadata = detail.get("execution_trace", {}).get("metadata", {})
        attempt_id = str(metadata.get("attempt_id") or f"edge-{index:04d}")
        sample_id = f"{site}-{attempt_id}"
        if sample_id in seen:
            continue
        before = _resolve_screenshot(metadata.get("before_screenshot_path"), source_root)
        after = _resolve_screenshot(metadata.get("after_screenshot_path"), source_root)
        if before is None or not before.is_file():
            continue
        seen.add(sample_id)
        samples.append({
            "sample_id": sample_id,
            "site": site,
            "run_id": graph_path.parent.name,
            "edge_id": edge_id,
            "action_id": edge.get("action", {}).get("semantic_id", ""),
            "action_label": edge.get("action", {}).get("action_label") or detail.get("instruction", ""),
            "expected_outcome": edge.get("action", {}).get("expected_outcome", ""),
            "executor_success": edge.get("execution_trace", {}).get("success"),
            "required_action_ids": edge.get("required_action_ids", []),
            "before_source": str(before),
            "after_source": str(after) if after and after.is_file() else None,
        })
    return samples


def _round_robin(groups: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    cursor = 0
    while len(chosen) < limit and any(cursor < len(group) for group in groups):
        for group in groups:
            if cursor < len(group) and len(chosen) < limit:
                chosen.append(group[cursor])
        cursor += 1
    return chosen


def _write_csv(path: Path, columns: list[str], samples: Iterable[dict[str, Any]]) -> None:
    # UTF-8 BOM makes Chinese text open correctly in Windows Excel.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for sample in samples:
            writer.writerow([sample.get(column, "") for column in columns])


def _page(title: str, samples: list[dict[str, Any]], task: str) -> str:
    cards = []
    for sample in samples:
        sid = html.escape(sample["sample_id"])
        after = ""
        if task == "c1" and sample.get("after_image"):
            after = f'<figure><figcaption>动作后</figcaption><img src="{html.escape(sample["after_image"])}"></figure>'
        reminder = "只根据动作前截图和动作描述判断，勿查看 C1 页面。" if task == "c3" else "根据动作前后证据判断，不参考系统预测。"
        expected = ""
        if task == "c1":
            expected = (
                f'<p><b>执行前预期结果：</b>'
                f'{html.escape(sample.get("expected_outcome", ""))}</p>'
            )
        cards.append(f'''<article data-sample="{sid}"><h2>{sid}</h2>
<p><b>动作：</b>{html.escape(sample["action_label"])}</p>{expected}<p class="hint">{reminder}</p>
<div class="shots"><figure><figcaption>动作前</figcaption><img src="{html.escape(sample["before_image"])}"></figure>{after}</div>
<p>请在对应 CSV 中填写此样本标签。</p></article>''')
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{title}</title>
<style>body{{font:16px system-ui;margin:2rem;max-width:1400px}}article{{border:1px solid #bbb;padding:1rem;margin:1rem 0}}.shots{{display:flex;gap:1rem;flex-wrap:wrap}}figure{{margin:0;max-width:48%}}img{{max-width:100%;border:1px solid #ddd}}.hint{{color:#8a3b00}}</style>
<h1>{title}</h1><p>样本顺序已固定。标注定义见 paper/experiments/annotation_guide_v1.md。</p>{''.join(cards)}</html>'''


def build_package(
    runs: list[tuple[str, Path, Path]], destination: Path, limit: int = 20,
    source_root: Path | None = None,
) -> list[dict[str, Any]]:
    source_root = (source_root or Path.cwd()).resolve()
    groups = [extract_samples(site, graph, evidence, source_root) for site, graph, evidence in runs]
    selected = _round_robin(groups, limit)
    destination.mkdir(parents=True, exist_ok=True)
    image_dir = destination / "images"
    image_dir.mkdir(exist_ok=True)
    public_samples = []
    for index, sample in enumerate(selected, 1):
        short_id = f"S{index:03d}"
        public = {key: value for key, value in sample.items() if not key.endswith("_source")}
        public["source_sample_id"] = public["sample_id"]
        public["sample_id"] = short_id
        for phase in ("before", "after"):
            source = sample.get(f"{phase}_source")
            if source:
                suffix = Path(source).suffix or ".png"
                name = f"{short_id}_{phase}{suffix}"
                shutil.copy2(source, image_dir / name)
                public[f"{phase}_image"] = f"images/{name}"
        public_samples.append(public)
    (destination / "samples.json").write_text(
        json.dumps(public_samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for site in sorted({sample["site"] for sample in public_samples}):
        site_samples = [sample for sample in public_samples if sample["site"] == site]
        site_dir = destination / site.replace("-", "_")
        site_dir.mkdir(exist_ok=True)
        _write_csv(site_dir / "c1_annotations.csv", C1_COLUMNS, site_samples)
        _write_csv(site_dir / "c3_annotations.csv", C3_COLUMNS, site_samples)
        run_ids = sorted({sample["run_id"] for sample in site_samples})
        metadata = {
            "site": site,
            "run_id": run_ids[0] if len(run_ids) == 1 else run_ids,
            "sample_count": len(site_samples),
        }
        (site_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (destination / "c1.html").write_text(_page("C1 功能证据标注", public_samples, "c1"), encoding="utf-8")
    (destination / "c3.html").write_text(_page("C3 动作风险标注（无结果泄漏）", public_samples, "c3"), encoding="utf-8")
    (destination / "README.md").write_text(
        "# 20 条样本试标包\n\n"
        "本包只用于检查标注流程，不作为论文正式实验结果。\n\n"
        "1. 先标风险：打开 `c3.html`，填写 `c3_annotations.csv`。\n"
        "2. 再标功能证据：打开 `c1.html`，填写 `c1_annotations.csv`。\n"
        "3. 标签定义见 `paper/experiments/annotation_guide_v1.md`。\n"
        "4. 标注时不要查看模型输出；拿不准的情况写入 `notes`。\n",
        encoding="utf-8",
    )
    return public_samples


def migrate_existing_package(destination: Path) -> dict[str, str]:
    """Shorten IDs in an existing package while preserving traceability and labels."""
    manifest_path = destination / "samples.json"
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_mapping = {
        sample.get("source_sample_id", sample["sample_id"]): f"S{index:03d}"
        for index, sample in enumerate(samples, 1)
    }
    mapping = dict(source_mapping)
    mapping.update({sample["sample_id"]: f"S{index:03d}" for index, sample in enumerate(samples, 1)})
    image_dir = destination / "images"
    for sample in samples:
        old_id = sample["sample_id"]
        short_id = mapping[old_id]
        sample["source_sample_id"] = sample.get("source_sample_id", old_id)
        sample["sample_id"] = short_id
        for phase in ("before", "after"):
            field = f"{phase}_image"
            if not sample.get(field):
                continue
            old_image = destination / sample[field]
            new_image = image_dir / f"{short_id}_{phase}{old_image.suffix}"
            if old_image.is_file() and not new_image.exists():
                shutil.copy2(old_image, new_image)
            sample[field] = f"images/{new_image.name}"
    manifest_path.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for csv_path in destination.glob("*_annotations.csv"):
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        for row in rows[1:]:
            if row and row[0] in mapping:
                row[0] = mapping[row[0]]
        try:
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                csv.writer(handle).writerows(rows)
        except PermissionError:
            # A CSV preview may hold the file open on Windows; other artifacts can migrate safely.
            continue
    for html_path in destination.glob("*.html"):
        content = html_path.read_text(encoding="utf-8")
        for old_id, short_id in mapping.items():
            content = content.replace(old_id, short_id)
        html_path.write_text(content, encoding="utf-8")
    (destination / "id_mapping.json").write_text(
        json.dumps(source_mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path("outputs/paper/annotation_pilot_v1"))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    root = Path.cwd()
    runs = [
        ("saucedemo", root / "outputs/experiments/saucedemo/open_exploration_prompt_policy_v1_gpt4o_no_profile_max25/graph.json", root / "outputs/experiments/saucedemo/open_exploration_prompt_policy_v1_gpt4o_no_profile_max25/graph_evidence.json"),
        ("practice-shopping", root / "outputs/experiments/practice_automated_testing/latest/graph.json", root / "outputs/experiments/practice_automated_testing/latest/graph_evidence.json"),
    ]
    samples = build_package(runs, args.destination, args.limit, root)
    print(f"Built {len(samples)} samples at {args.destination.resolve()}")


if __name__ == "__main__":
    main()
