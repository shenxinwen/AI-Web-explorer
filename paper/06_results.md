# 结果与结论

仅记录已完成、可复现且可用于论文的结果。探索性现象先保留在实验注册表中。

| 结果 ID | 支撑的主张 | 图或表 | 状态 | 结论边界 |
| --- | --- | --- | --- | --- |
| R1 | C1：功能结果验证与知识准入 | `experiments/results/E003/` | 已完成 | 在两个冻结网站和现有设置内，evidence-grounded admission 提高准入 precision 并保留绝大多数 supported knowledge；不得外推为绝对正确 |
| R2 | C2：执行驱动证据生产与功能发现保留 | `experiments/results/E004/c2_final_results.md` | 已完成并冻结 | 18 条运行与覆盖账本 v1 已人工确认；macro-average：Random 28.8%、Linear 42.6%、Full 54.5%；Full 相对 Linear +11.9 pp。 |
| R3 | C3：自动探索中已选执行动作的风险识别能力 | `experiments/results/E002/c3_final_results.md` | 已完成并冻结 | 探索关联数据证明记录链路可运行；外部数据支持更高风险类型 grounding 与召回导向的二元权衡，但风险识别不等于实际拦截或探索安全 |
| R4 | C1–C3 的下游规划与行为验证效用 | 待定 | 未开始 | 不外推为完整通用自动化能力 |

## 当前状态

C1 已有可归档结果：45 条候选功能中有 33 条人工支持；proposal-as-fact、executor-success-as-fact 和 evidence-grounded admission 的 precision 分别为 73.33%、82.50% 和 96.97%，后者的 supported knowledge retention 为 96.97%。C2 已完成 18 条运行与统一人工覆盖确认；Full 在两站点的 macro-average 覆盖率为 54.5%，高于 Linear 的 42.6% 和 Random 的 28.8%，同时单列 replay GUI 成本。C3 已完成探索关联与外部 context-challenge 两条正式评测：外部 100 样本上 Context-conditioned 相对 Text-only 的 recall、F1 和 acceptable-type accuracy 分别提高 12.3、5.2 和 35.4 pp，precision 降低 4.5 pp；只有类型准确率差异的 bootstrap 区间明确不跨 0。综合证据支持“可靠知识准入、保留有用覆盖、执行前风险可审查”的有界主张，不支持端到端安全提升。

早期工程冒烟仅用于证明风险记录可接入；正式 C3 结论以 E002 冻结结果包为准，不再以冒烟计数作为效果证据。
