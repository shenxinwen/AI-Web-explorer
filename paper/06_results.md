# 结果与结论

仅记录已完成、可复现且可用于论文的结果。探索性现象先保留在实验注册表中。

| 结果 ID | 支撑的主张 | 图或表 | 状态 | 结论边界 |
| --- | --- | --- | --- | --- |
| R1 | C1：功能结果验证与知识准入 | `experiments/results/E003/` | 已完成 | 在两个冻结网站和现有设置内，evidence-grounded admission 提高准入 precision 并保留绝大多数 supported knowledge；不得外推为绝对正确 |
| R2 | C2：执行驱动证据生产与功能发现保留 | `experiments/results/E004/c2_final_results.md` | 已完成并冻结 | 18 条运行与覆盖账本 v1 已人工确认；macro-average：Random 28.8%、Linear 42.6%、Full 54.5%；Full 相对 Linear +11.9 pp。 |
| R3 | C3：自动探索中已选执行动作的风险识别能力 | 待定 | 未开始 | 风险识别不等于实际拦截，也不能证明探索安全 |
| R4 | C1–C3 的下游规划与行为验证效用 | 待定 | 未开始 | 不外推为完整通用自动化能力 |

## 当前状态

C1 已有可归档结果：45 条候选功能中有 33 条人工支持；proposal-as-fact、executor-success-as-fact 和 evidence-grounded admission 的 precision 分别为 73.33%、82.50% 和 96.97%，后者的 supported knowledge retention 为 96.97%。C2 已完成 18 条运行与统一人工覆盖确认；Full 在两站点的 macro-average 覆盖率为 54.5%，高于 Linear 的 42.6% 和 Random 的 28.8%，同时单列 replay GUI 成本。C3 尚无论文级效果结果。综合 claim 继续保持为研究问题：知识可靠性与环境风险感知能否在固定预算下保留有用的功能发现能力。

工程可行性观察（不作为论文结果）：一次 SauceDemo 十步运行对全部十个执行前动作完成判断，记录 3 个潜在风险、7 个无风险和 0 个检测错误；另一次单步运行确认风险元数据可写入紧凑 graph。该观察不能支持准确率、召回率或跨网站泛化结论。
