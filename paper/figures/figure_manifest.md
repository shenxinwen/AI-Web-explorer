# 图表清单

每项图表必须说明支撑的主张、源数据、生成命令及最终使用位置。

| 图表 ID | 论点 | 源数据 | 生成命令 | 稿件位置 | 状态 |
| --- | --- | --- | --- | --- | --- |
| F1 | C2 在固定普通候选动作预算下的证据支持功能覆盖增长 | `experiments/results/E004/c2_metrics_consolidated_ai_initial.json` | `python scripts/paper/plot_c2.py paper/experiments/results/E004/c2_metrics_consolidated_ai_initial.json --output-dir paper/experiments/results/E004` | C2 实验结果；`experiments/results/E004/c2_coverage_growth.png` | 已生成，待主稿选用 |
| F2 | C2 replay 新增覆盖与额外 GUI 成本需同时报告 | 同 F1 | 同 F1 | C2 replay 分析；`experiments/results/E004/c2_replay_cost.png` | 已生成，待主稿选用 |
| F3 | C3 视觉上下文提高 recall、F1 与 acceptable-type accuracy，但降低 precision | `../outputs/paper/formal/E002_c3_external_v1/formal_metrics.json` | `python scripts/paper/plot_c3.py --metrics outputs/paper/formal/E002_c3_external_v1/formal_metrics.json --output paper/experiments/results/E002/c3_external_main_metrics.png` | C3 外部主比较；`experiments/results/E002/c3_external_main_metrics.png` | 已生成，待主稿选用 |
