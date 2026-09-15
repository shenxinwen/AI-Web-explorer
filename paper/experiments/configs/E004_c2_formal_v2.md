# E004 / C2 正式实验配置 v2

> 状态：已冻结，待运行。经用户确认，修复 replay reset 成本后从全新目录重新执行第一阶段。
>
> 本配置继承 `E004_c2_formal_v1.md` 的网站、方法、运行顺序、模型、prompt、viewport、候选限制、普通 attempt 预算、Random seeds、异常规则和第一阶段检查点；仅采用下列明确变更。

## 相对 v1 的变更

| 字段 | v2 值 |
| --- | --- |
| 冻结日期 | 2026-09-15 |
| 实现提交 | `bab1318824a945ef13fbe9e521aa4fd862bd53f1` |
| 输出根目录 | `outputs/paper/formal/E004_c2_v2/` |
| Frontier replay SHA-256 | `183fe7b03d046154d7fadef7ca53eff06db21b9527ab6206c0d16736e78975f3` |
| Replay GUI 成本 | 每次 `reset_to(start_url)` 尝试计 1，加上该 replay 的路径 action attempts |

## 成本记录口径

- `reset_attempted_steps`：入口重置尝试数；实际进入 reset 时每次为 1，入口状态不可用且未尝试 reset 时为 0。
- `attempted_steps`：reset 后沿历史路径执行的 GUI 动作数。
- `gui_action_attempts = reset_attempted_steps + attempted_steps`。
- run 级 `replay_gui_action_attempts` 为各 replay 的 `gui_action_attempts` 之和。
- 普通候选 attempts 仍是三种方法共享的 25-step 预算；replay GUI 成本不占该预算，但单独限额和报告。

## 数据隔离

- 正式 v1 的 Practice Shopping / Full / `run_01` 保持原样，并标记为 instrumentation-invalid，不进入主分析。
- v2 所有组合均从新浏览器上下文开始，不 resume v1 或 pilot 数据。
- v2 第一阶段仍为两个网站 × 三种方法 × 1 次，共 6 条 `run_01`；完成后暂停审计，再决定是否补齐 `run_02`、`run_03`。
