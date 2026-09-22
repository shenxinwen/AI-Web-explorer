# 实验注册表

在运行实验前登记；每个 ID 保持稳定，并链接到冻结配置、原始输出和论文级结果。

| 实验 ID | 假设/目的 | 配置 | 输出位置 | 状态 | 对应主张 |
| --- | --- | --- | --- | --- | --- |
| E001 | 验证风险检测能接入普通探索并持久化结果 | SauceDemo；10 步真实 VLM smoke + 1 步持久化 smoke；非冻结配置 | 本地忽略目录 `outputs/risk_smoke/`、`outputs/risk_persistence_smoke/` | 工程冒烟完成，不作为论文结果 | C3 可实现性 |
| E002 | RQ3：评估动作条件风险识别的准确性与上下文敏感性 | 探索关联：C2 Full 的 106 条运行内去重动作、4 条件；外部挑战：100 条 screenshot-action 样本、Text-only vs Context-conditioned、30 个候选配对 | `results/E002/final/c3_final_results.md`；原始输出位于 `outputs/paper/formal/E002_c3_v1/` 与 `E002_c3_external_v1/` | 两条正式评测、人工确认 gold、bootstrap、错误分析与最终结果包均已冻结 | C3 |
| E003 | RQ1：在冻结候选、执行前 expected outcomes 与交互轨迹上评估功能知识准入 | `protocol_v1.md`；SauceDemo v1 + Practice Shopping v4；每站 3 runs、每 run 最多 25 attempts；相同轨迹上的 proposal-as-fact、executor-success-as-fact、evidence-grounded admission；人工确认 outcome gold | `results/E003/final/`；原始轨迹位于 `outputs/paper/formal/E003_c1_v1/` 与 `E003_c1_v4/` | 正式实验完成；结果与误差分析已归档 | C1 |
| E004 | RQ2：在固定应用、起点与交互预算下评估证据获取、知识增长、功能发现保留和 frontier 恢复 | `protocol_v1.md`；SauceDemo + Practice Shopping；Random vs Linear vs Full；pilot 10、正式 25 normal candidate attempts；replay 成本单列；正式每条件 3 runs | `results/E004/final/c2_final_results.md`；pilot 位于 `outputs/paper/pilot/E004_c2_v1/` 与 `E004_c2_v2/`；正式输出位于 `outputs/paper/formal/E004_c2_v1/` 与 `E004_c2_v2/` | v2 的 18 条运行与覆盖账本 v1 已冻结；SauceDemo run_03 的登录失败原件已归档，replacement 已提升为标准路径。 | C2 |
