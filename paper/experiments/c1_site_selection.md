# C1 正式站点选择记录

> 决定日期：2026-09-12
>
> 适用实验：E003 / C1

## 决定

正式 C1 使用 SauceDemo 与 Practice Shopping。每个网站运行 3 次自然探索，每次最多 25 个 high-level action attempts。

## RealWorld 检查与排除

RealWorld 仅进行了一次非正式资格检查，产物位于本地忽略目录 `outputs/paper/pilots/c1/realworld_qualification_20260910/run_01/`，不进入 E003 统计。

该检查在最新 replay 适配后可记录 replay 成功，但未达到正式数据质量门槛：14 次 attempts 中只有 9 次具备完整的 C1 证据链，且只有 7 条运行内去重功能。因此不继续对 RealWorld 探索或修复；它可在未来作为独立稳健性检查重新评估。

## 影响

- `protocol_v1.md` 中原有的 SauceDemo + Practice Shopping 设计保持不变。
- Practice Shopping 的搜索框漏识别与首屏外分页仍属于 C2 候选召回/页面覆盖问题，不纳入 C1 修复范围。
- 任何 RealWorld 调试或资格检查工件均不与正式轨迹、人工 gold 或 E003 指标混合。
