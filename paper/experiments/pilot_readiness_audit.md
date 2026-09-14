# Pilot 工件就绪性核查

> 核查日期：2026-09-14
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
| replay 次数和结果 | graph meta replay metrics、`replay_attempt_history` | 已有 | 计算 replay GUI 成本、恢复结果和后续正常 attempt |
| 论文级 verification state | 无单一持久字段 | 可离线派生 | 使用 `annotation_guide_v1.md` 冻结映射，不新增运行时功能 |
| 三种 C2 条件 | CLI `--exploration-condition random/linear/full` | 已实现并测试 | Random 强制 seed；Linear 禁止 replay；Full 启用 replay |
| C2 attempt 表 | `scripts/paper/build_c2_attempt_table.py` | 已实现并测试 | 不因失败或截图缺失删除 attempt |
| C2 指标 | `scripts/paper/analyze_c2.py` | 已实现并测试 | 计算功能覆盖率、增长曲线和 attempt 诊断 |

## 当前结论

当前 graph 和 execution-event 结构覆盖 Pilot 所需原始信息。剩余运行风险主要是截图文件是否完整保留、真实 replay 是否都能关联到恢复后的首个普通 attempt，以及两个网站的候选是否能在 10-attempt pilot 内形成可计算覆盖曲线。

本地 `outputs/experiments/` 中仍保留 Practice Shopping 与 SauceDemo 的历史 graph、stagehand trace 和逐步 before/after screenshots，可用于样本导出格式验证。这些运行采用旧配置，只用于试标和工具检查，不转为正式论文结果。

## Pilot 前检查清单

1. 固定一次输出目录并确认 graph、execution events、普通动作截图和 replay 截图均不会被覆盖。
2. 分别运行 Random、Linear、Full 的最小 smoke，确认条件名、seed、普通 attempt 数和 replay GUI 成本写入元数据。
3. 从 smoke graph 导出完整 attempt 表，验证所有 `attempt_id` 唯一；截图缺失的 attempt 必须保留并标为 evidence-incomplete。
4. 对 20 个样本完成 AI 初标与人工逐项审查，检查标签定义是否可执行；该流程不作为双人独立标注，也不报告标注者一致性。
5. Pilot 后再决定是否需要补日志；在看到真实缺失前不修改探索框架。
