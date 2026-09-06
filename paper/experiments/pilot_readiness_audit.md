# Pilot 工件就绪性核查

> 核查日期：2026-09-06
>
> 范围：只核查当前代码和已有工件能否支持 `protocol_v1.md`，不运行浏览器或模型实验。

| Pilot 所需信息 | 当前来源 | 状态 | 处理 |
| --- | --- | --- | --- |
| action / action label | edge `action`、`instruction` | 已有 | 直接抽取 |
| 唯一 action attempt | `execution_trace.metadata.attempt_id` | 已有 | 作为样本主键的一部分 |
| executor success/error | `execution_trace.success/error`、`backend_reported_success` | 已有 | 与 outcome 分开评测 |
| before/after screenshots | `execution_trace.metadata.before_screenshot_path/after_screenshot_path` | 已有，但需运行时保留文件 | Pilot 检查路径存在性 |
| outcome judgment | `action_outcome_trace.llm_response` | 已有 | 解析 success/failed/uncertain、location change、evidence |
| direct dependency | edge `required_action_ids` | 已有 | 人工标注是否由轨迹支持 |
| candidate lifecycle/frontier | graph meta `location_exploration_memory` | 已有 | 计算 pending、attempts、revisit/completion |
| 普通探索风险判断 | `execution_trace.metadata.risk_assessment` 或 error | 已有 | 计算识别与检测覆盖 |
| replay 风险判断 | graph meta `replay_risk_assessments` | 已有 | 单独标记 sample source |
| replay 次数和结果 | graph meta replay metrics | 已有 | 计算恢复相关指标 |
| 论文级 verification state | 无单一持久字段 | 可离线派生 | 使用 `annotation_guide_v1.md` 冻结映射，不新增运行时功能 |
| no-replay 条件 | controller 在 `max_total_replays=0` 时禁止 replay | 可配置 | Pilot 前用现有测试确认，不新增开关 |
| RQ1 baseline 输出 | 相同轨迹的离线准入规则 | 可派生 | 编写结果脚本，不重新运行浏览器 |

## 当前结论

当前 graph 和 execution-event 结构原则上覆盖 Pilot 所需原始信息。主要风险不是缺少核心字段，而是运行结束后截图文件可能未被完整保留、不同路径的 metadata 可能缺项，以及论文级 verification state 需要离线派生。

本地 `outputs/experiments/` 中仍保留 Practice Shopping 与 SauceDemo 的历史 graph、stagehand trace 和逐步 before/after screenshots，可用于样本导出格式验证。这些运行采用旧配置，只用于试标和工具检查，不转为正式论文结果。

## Pilot 前检查清单

1. 固定一次输出目录并确认 graph、execution events、普通动作截图和 replay 截图均不会被覆盖。
2. 用现有测试或 fixture 确认 `max_total_replays=0` 与 full 条件可区分。
3. 从一个历史 graph 导出候选样本表，验证所有 `attempt_id` 唯一且截图路径可定位。
4. 对 20 个样本完成双人试标；如暂无第二名标注者，只能完成格式试标，不能宣称标注一致性。
5. Pilot 后再决定是否需要补日志；在看到真实缺失前不修改探索框架。
