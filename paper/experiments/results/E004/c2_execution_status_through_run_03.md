# E004 / C2：执行状态与可报告结果（至 run_03）

更新日期：2026-09-17。

## 结论状态

18 条预定的 C2 运行均已完成并保留了原始工件。SauceDemo / Linear 与 Full 的原始 `run_03` 因登录动作类型兼容性缺口而无效；修复后重跑的有效结果已提升为标准 `run_03` 路径，原结果归档为 `run_03_login_type_failure_archived`。

执行矩阵与覆盖映射均已冻结。用户于 2026-09-19 接受覆盖账本 v1，逐 run 的首次证据与 core 映射见 [c2_coverage_mapping_ledger_v1.md](c2_coverage_mapping_ledger_v1.md)，机器可读输入与输出分别为 [ledger CSV](c2_coverage_mapping_ledger_v1.csv) 和 [metrics JSON](c2_metrics_consolidated_ai_initial.json)。逐 attempt CSV 保留原始 AI 初标；最终人工确认以冻结账本为准。

## 执行质量

`success / failed` 指 executor status 计数；`incomplete` 为缺少可比较 evidence 的普通 attempts。replay GUI 动作不占普通 attempt 预算。

| run | 网站 | 条件 | 有效目录 | 普通 attempts | success / failed | incomplete | replay / GUI | 停止原因 |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- |
| 01 | Practice Shopping | Random | `practice_shopping/random/run_01` | 19 | 7 / 12 | 1 | 0 / 0 | `current_state_exhausted` |
| 01 | Practice Shopping | Linear | `practice_shopping/linear/run_01` | 17 | 11 / 6 | 2 | 0 / 0 | `current_state_exhausted` |
| 01 | Practice Shopping | Full | `practice_shopping/full/replacement_01` | 25 | 17 / 8 | 4 | 0 / 0 | `max_exploration_steps_reached` |
| 01 | SauceDemo | Random | `saucedemo/random/run_01` | 3 | 1 / 2 | 0 | 0 / 0 | `current_state_exhausted` |
| 01 | SauceDemo | Linear | `saucedemo/linear/run_01` | 10 | 10 / 0 | 0 | 0 / 0 | `current_state_exhausted` |
| 01 | SauceDemo | Full | `saucedemo/full/run_01` | 20 | 16 / 4 | 0 | 4 / 28 | `total_replay_limit_reached` |
| 02 | Practice Shopping | Random | `practice_shopping/random/run_02` | 11 | 9 / 2 | 0 | 0 / 0 | `current_state_exhausted` |
| 02 | Practice Shopping | Linear | `practice_shopping/linear/run_02` | 16 | 12 / 4 | 1 | 0 / 0 | `current_state_exhausted` |
| 02 | Practice Shopping | Full | `practice_shopping/full/run_02_replacement_03` | 18 | 14 / 4 | 2 | 1 / 1 | `no_recoverable_frontier` |
| 02 | SauceDemo | Random | `saucedemo/random/run_02_replacement_01` | 13 | 9 / 4 | 0 | 0 / 0 | `current_state_exhausted` |
| 02 | SauceDemo | Linear | `saucedemo/linear/run_02` | 14 | 14 / 0 | 0 | 0 / 0 | `current_state_exhausted` |
| 02 | SauceDemo | Full | `saucedemo/full/run_02` | 21 | 21 / 0 | 0 | 3 / 20 | `no_recoverable_frontier` |
| 03 | Practice Shopping | Random | `practice_shopping/random/run_03` | 10 | 9 / 1 | 0 | 0 / 0 | `current_state_exhausted` |
| 03 | Practice Shopping | Linear | `practice_shopping/linear/run_03` | 16 | 14 / 2 | 2 | 0 / 0 | `current_state_exhausted` |
| 03 | Practice Shopping | Full | `practice_shopping/full/run_03` | 25 | 16 / 9 | 4 | 0 / 0 | `max_exploration_steps_reached` |
| 03 | SauceDemo | Random | `saucedemo/random/run_03` | 11 | 9 / 2 | 0 | 0 / 0 | `current_state_exhausted` |
| 03 | SauceDemo | Linear | `saucedemo/linear/run_03` | 10 | 8 / 2 | 0 | 0 / 0 | `current_state_exhausted` |
| 03 | SauceDemo | Full | `saucedemo/full/run_03` | 21 | 18 / 3 | 0 | 4 / 28 | `total_replay_limit_reached` |

## 覆盖率的当前可报告范围

| run | 网站 | Random | Linear | Full | 覆核状态 |
| --- | --- | ---: | ---: | ---: | --- |
| 01 | Practice Shopping | 5/16 (31.2%) | 7/16 (43.8%) | 7/16 (43.8%) | 已人工确认 |
| 01 | SauceDemo | 1/22 (4.5%) | 10/22 (45.5%) | 12/22 (54.5%) | 已人工确认 |
| 02 | Practice Shopping | 7/16 (43.8%) | 7/16 (43.8%) | 9/16 (56.3%) | 已人工确认 |
| 02 | SauceDemo | 8/22 (36.4%) | 10/22 (45.5%) | 14/22 (63.6%) | 已人工确认 |
| 03 | Practice Shopping | 4/16 (25.0%) | 8/16 (50.0%) | 8/16 (50.0%) | 已人工确认 |
| 03 | SauceDemo | 7/22 (31.8%) | 6/22 (27.3%) | 13/22 (59.1%) | 已人工确认 |

不应在完成缺失映射与人工复核之前，对三条件的平均覆盖率或显著性作出论文级结论。

## 三次重复覆盖率（最终人工确认）

下表基于冻结的覆盖账本 v1。

| 网站 | 条件 | run_01 | run_02 | run_03 | 平均覆盖数 / 分母 | 平均覆盖率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Practice Shopping | Random | 5/16 | 7/16 | 4/16 | 5.33/16 | 33.3% |
| Practice Shopping | Linear | 7/16 | 7/16 | 8/16 | 7.33/16 | 45.8% |
| Practice Shopping | Full | 7/16 | 9/16 | 8/16 | 8.00/16 | 50.0% |
| SauceDemo | Random | 1/22 | 8/22 | 7/22 | 5.33/22 | 24.2% |
| SauceDemo | Linear | 10/22 | 10/22 | 6/22 | 8.67/22 | 39.4% |
| SauceDemo | Full | 12/22 | 14/22 | 13/22 | 13.00/22 | 59.1% |

按网站 macro-average（先在各网站内以其 16 或 22 的固定分母计算比例，再平均），三条件覆盖率分别为 Random 28.8%、Linear 42.6%、Full 54.5%。Full 相对 Linear 的 macro-average 差为 +11.9 个百分点，相对 Random 为 +25.8 个百分点。

这些数字支持结构化探索优于 Random、Full 进一步优于 Linear 的方向性主张。三次重复不提供可靠的显著性检验功效，因此本实验报告效应方向与描述统计，不主张显著性。

## 已知 replay 结果

- SauceDemo / Full / run_02：3 次 replay、20 GUI 动作；replay 后的普通 attempts 新增 3 项 AI 初标覆盖。
- Practice Shopping / Full / run_02：1 次 replay、1 GUI 动作；replay 后的普通 attempts 新增 2 项 AI 初标覆盖。
- SauceDemo / Full / run_03：4 次 replay、28 GUI 动作；前三次成功 replay 后新增 SD17、SD19、SD21 共 3 项覆盖。前三次成功 replay 成本为 19 GUI 动作；第 4 次以 target-state mismatch 失败但仍产生 9 GUI 动作成本，故 run 级报告成本保持 28。

## 三次重复的执行指标（不依赖覆盖映射）

| 网站 | 条件 | 平均普通 attempts | executor 成功率 | failed attempts | evidence-incomplete | replay / GUI actions |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Practice Shopping | Random | 13.33 | 62.5% (25/40) | 15 | 1 | 0 / 0 |
| Practice Shopping | Linear | 16.33 | 75.5% (37/49) | 12 | 5 | 0 / 0 |
| Practice Shopping | Full | 22.67 | 69.1% (47/68) | 21 | 10 | 1 / 1 |
| SauceDemo | Random | 9.00 | 70.4% (19/27) | 8 | 0 | 0 / 0 |
| SauceDemo | Linear | 11.33 | 94.1% (32/34) | 2 | 0 | 0 / 0 |
| SauceDemo | Full | 20.67 | 88.7% (55/62) | 7 | 0 | 11 / 76 |

Practice Shopping / Full 的 run_01 与 run_03 均未产生可恢复 frontier，因此没有 replay；这不是运行异常，但限制了该站点上 replay 贡献的可观测性。SauceDemo / Full 三次运行均发生 replay，必须在报告覆盖提升时同时报告 76 个额外 GUI actions 的成本。
