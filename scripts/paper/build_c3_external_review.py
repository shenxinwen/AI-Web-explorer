"""Build a self-contained visual review page for the C3 external pilot."""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


RISK_TYPES = [
    "destructive_change",
    "financial_transaction",
    "external_communication",
    "sensitive_data",
    "account_and_permission",
]
GOLD_COLUMNS = [
    "sample_id", "pair_id", "potential_risk", "risk_type",
    "acceptable_risk_types", "evidence", "review_status",
]


def _checked(condition: bool) -> str:
    return " checked" if condition else ""


def _card(sample: dict[str, Any], gold: dict[str, str], image_name: str) -> str:
    sample_id = html.escape(sample["sample_id"])
    selected_types = {
        item.strip() for item in gold.get("acceptable_risk_types", "").split(";")
        if item.strip()
    }
    type_controls = "".join(
        f'<label class="type"><input type="checkbox" data-field="risk-type" '
        f'value="{risk_type}"{_checked(risk_type in selected_types)}> '
        f'{risk_type}</label>'
        for risk_type in RISK_TYPES
    )
    is_risk = gold.get("potential_risk", "").lower() == "true"
    evidence = html.escape(gold.get("evidence", ""))
    return f'''<article class="sample" data-sample="{sample_id}" data-pair="{html.escape(sample["pair_id"])}">
<header><span class="sample-id">{sample_id}</span><span>{html.escape(sample.get("site", ""))} · {html.escape(sample.get("semantic_location", ""))}</span></header>
<p class="action"><b>候选动作：</b>{html.escape(sample.get("action_label", ""))}</p>
<img src="images/{html.escape(image_name)}" alt="{sample_id} 动作前截图">
<fieldset><legend>是否存在 taxonomy 覆盖的潜在风险？</legend>
<label><input type="radio" name="risk-{sample_id}" value="true"{_checked(is_risk)}> 是</label>
<label><input type="radio" name="risk-{sample_id}" value="false"{_checked(not is_risk)}> 否</label>
</fieldset>
<fieldset><legend>可接受的风险类型（可多选；非风险样本留空）</legend><div class="types">{type_controls}</div></fieldset>
<label class="block"><b>判断依据</b><textarea data-field="evidence">{evidence}</textarea></label>
<label class="block"><b>复核状态</b><select data-field="review-status">
<option value="pending">待复核</option><option value="confirmed">确认初标</option><option value="corrected">已修正</option>
</select></label>
</article>'''


def _page(pairs: dict[str, list[tuple[dict[str, Any], dict[str, str], str]]]) -> str:
    sections = []
    for pair_id, entries in pairs.items():
        action = html.escape(entries[0][0].get("action_label", ""))
        cards = "".join(_card(*entry) for entry in entries)
        sections.append(
            f'<section class="pair"><h2>{html.escape(pair_id)}</h2>'
            f'<p class="pair-note">相同动作文本：{action}。请只依据各自页面上下文判断。</p>'
            f'<div class="pair-grid">{cards}</div></section>'
        )
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>C3 外部 pilot 人工复核</title>
<style>
:root{{--ink:#172033;--muted:#64748b;--line:#cbd5e1;--accent:#2563eb;--paper:#fff;--bg:#f1f5f9}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,"Microsoft YaHei",sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}}h1{{margin-bottom:8px}}.intro{{max-width:980px;color:var(--muted)}}
.notice{{border-left:4px solid #f59e0b;background:#fffbeb;padding:12px 16px;margin:18px 0}}
.pair{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px;margin:22px 0;box-shadow:0 3px 12px #0f172a12}}
.pair h2{{margin:0}}.pair-note{{color:var(--muted)}}.pair-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.sample{{border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0}}header{{display:flex;justify-content:space-between;gap:12px;color:var(--muted)}}
.sample-id{{font-weight:750;color:var(--accent)}}.action{{min-height:48px}}img{{display:block;width:100%;max-height:620px;object-fit:contain;background:#eef2f7;border:1px solid var(--line);border-radius:8px}}
fieldset{{border:1px solid var(--line);border-radius:8px;margin:14px 0;padding:10px}}legend{{font-weight:650}}fieldset>label{{margin-right:22px}}
.types{{display:flex;flex-wrap:wrap;gap:8px}}.type{{background:#eff6ff;border-radius:6px;padding:5px 8px}}.block{{display:block;margin-top:12px}}
textarea,select{{display:block;width:100%;margin-top:6px;padding:9px;border:1px solid var(--line);border-radius:7px;font:inherit}}textarea{{min-height:82px;resize:vertical}}
.toolbar{{position:sticky;bottom:12px;display:flex;align-items:center;gap:12px;background:#172033ee;color:#fff;padding:12px 16px;border-radius:12px;box-shadow:0 6px 24px #0004}}
button{{background:#60a5fa;color:#081225;border:0;border-radius:8px;padding:10px 16px;font-weight:750;cursor:pointer}}#status{{color:#dbeafe}}
@media(max-width:900px){{main{{padding:14px}}.pair-grid{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>C3 外部 pilot：10 条图文复核</h1>
<p class="intro">目标是确认每个待执行动作在当前页面上下文中是否存在潜在风险。类型是解释性形式化词汇，可多选；复合风险中，只要类型有合理依据即可纳入可接受集合。</p>
<p class="notice"><b>当前内容是 AI 初标，不是最终 gold。</b> 请逐条选择“确认初标”或修改后选择“已修正”。页面不会展示外部数据集原标签。</p>
{''.join(sections)}
<div class="toolbar"><button id="export" type="button">导出复核 CSV</button><span id="status">尚有样本未确认</span></div>
</main><script>
const columns={json.dumps(GOLD_COLUMNS)};
const esc=v=>'"'+String(v??'').replaceAll('"','""')+'"';
function rows(){{return [...document.querySelectorAll('.sample')].map(card=>{{
 const risk=card.querySelector('input[type=radio]:checked').value;
 const types=[...card.querySelectorAll('[data-field=risk-type]:checked')].map(x=>x.value);
 return {{sample_id:card.dataset.sample,pair_id:card.dataset.pair,potential_risk:risk,
  risk_type:types[0]||'',acceptable_risk_types:types.join(';'),
  evidence:card.querySelector('[data-field=evidence]').value.trim(),review_status:'human_reviewed'}};
}})}}
function updateStatus(){{const pending=[...document.querySelectorAll('[data-field=review-status]')].filter(x=>x.value==='pending').length;
 document.querySelector('#status').textContent=pending?`尚有 ${{pending}} 条未确认`:'10 条均已复核，可以导出';}}
document.querySelectorAll('[data-field=review-status]').forEach(x=>x.addEventListener('change',updateStatus));
document.querySelector('#export').addEventListener('click',()=>{{
 const pending=[...document.querySelectorAll('[data-field=review-status]')].filter(x=>x.value==='pending');
 if(pending.length&&!confirm(`仍有 ${{pending.length}} 条未确认，仍要导出吗？`))return;
 const csv='\ufeff'+[columns.join(','),...rows().map(row=>columns.map(key=>esc(row[key])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{{type:'text/csv;charset=utf-8'}}));
 const a=document.createElement('a');a.href=url;a.download='c3_external_pilot_reviewed.csv';a.click();URL.revokeObjectURL(url);
}});updateStatus();
</script></body></html>'''


def build_review_package(
    manifest_path: Path,
    gold_path: Path,
    image_root: Path,
    destination: Path,
) -> int:
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    with gold_path.open(encoding="utf-8-sig", newline="") as handle:
        gold_rows = list(csv.DictReader(handle))
    gold_by_id = {row["sample_id"]: row for row in gold_rows}
    if {sample["sample_id"] for sample in samples} != set(gold_by_id):
        raise ValueError("Manifest and gold sample IDs do not match")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[sample["pair_id"]].append(sample)
    if any(len(group) != 2 for group in grouped.values()):
        raise ValueError("Each context pair must contain exactly two samples")

    destination.mkdir(parents=True, exist_ok=True)
    target_images = destination / "images"
    target_images.mkdir(exist_ok=True)
    rendered: dict[str, list[tuple[dict[str, Any], dict[str, str], str]]] = {}
    for pair_id, pair_samples in grouped.items():
        rendered[pair_id] = []
        for sample in pair_samples:
            source = image_root / sample["before_image"]
            if not source.is_file():
                raise FileNotFoundError(source)
            target_name = f'{sample["sample_id"]}{source.suffix or ".png"}'
            shutil.copy2(source, target_images / target_name)
            rendered[pair_id].append((sample, gold_by_id[sample["sample_id"]], target_name))

    shutil.copy2(gold_path, destination / "review_seed.csv")
    (destination / "samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destination / "review.html").write_text(_page(rendered), encoding="utf-8")
    return len(samples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    count = build_review_package(
        args.manifest, args.gold, args.image_root, args.destination
    )
    print(f"Built review page for {count} samples at {args.destination.resolve()}")


if __name__ == "__main__":
    main()
