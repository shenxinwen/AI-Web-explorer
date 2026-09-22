# E004 / C2 run_02 执行指标与 AI 初标

生成日期：2026-09-16。此记录仅整理冻结 v2 配置下已执行的 run_02；未启动 run_03。功能覆盖率中，两个 Full run 已于 2026-09-15 完成人工复核；Random 与 Linear 的覆盖映射为 AI 初标，尚待同一流程复核。

## 有效运行与执行质量

| 网站 | 条件 | 有效目录 | 普通 attempts | executor 成功/失败 | evidence-incomplete | 停止原因 | replay 次数 / GUI actions |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| SauceDemo | Random | `saucedemo/random/run_02_replacement_01` | 13 | 9 / 4 | 0 | `current_state_exhausted` | 0 / 0 |
| SauceDemo | Linear | `saucedemo/linear/run_02` | 14 | 14 / 0 | 0 | `current_state_exhausted` | 0 / 0 |
| SauceDemo | Full | `saucedemo/full/run_02` | 21 | 21 / 0 | 0 | `no_recoverable_frontier` | 3 / 20 |
| Practice Shopping | Random | `practice_shopping/random/run_02` | 11 | 9 / 2 | 0 | `current_state_exhausted` | 0 / 0 |
| Practice Shopping | Linear | `practice_shopping/linear/run_02` | 16 | 12 / 4 | 1 | `current_state_exhausted` | 0 / 0 |
| Practice Shopping | Full | `practice_shopping/full/run_02_replacement_03` | 18 | 14 / 4 | 2 | `no_recoverable_frontier` | 1 / 1 |

Executor 成功率（成功 attempts / 普通 attempts）依次为 SauceDemo Random 69.2%、Linear 100.0%、Full 100.0%，Practice Shopping Random 81.8%、Linear 75.0%、Full 77.8%。

SauceDemo Random 的原始 `run_02` 在浏览器启动前发生 `spawn EPERM`，未创建 graph checkpoint，不进入正式结果；有效 replacement 使用相同 seed `5102` 和独立 embedding 路径。Practice Shopping Random 使用 seed `5202`。所有 Linear/Full 条件均无 random seed。

## 功能覆盖率

| 网站 | Random | Linear | Full |
| --- | --- | --- | --- |
| SauceDemo（22） | 8/22，36.4%（AI 初标） | 10/22，45.5%（AI 初标） | 14/22，63.6%（人工复核） |
| Practice Shopping（16） | 7/16，43.8%（AI 初标） | 7/16，43.8%（AI 初标） | 9/16，56.3%（人工复核） |

AI 初标匹配的 core IDs：

- SauceDemo Random：SD01、SD02、SD05、SD06、SD07、SD13、SD14、SD17。
- SauceDemo Linear：SD02、SD03、SD05、SD07、SD12、SD13、SD14、SD15、SD16、SD20。两次独立字段填写均为 SD01 的部分证据，按既有标注规则不单独计为复合 SD01。
- Practice Shopping Random：PS02、PS04、PS08、PS12、PS13、PS14、PS15。
- Practice Shopping Linear：PS02、PS04、PS08、PS12、PS13、PS14、PS15。

## 覆盖增长曲线

每个序列中的第 *i* 项为第 *i* 个普通 attempt 结束后的累计覆盖数：

| 网站 / 条件 | 累计覆盖数 |
| --- | --- |
| SauceDemo Random | 1, 2, 2, 2, 3, 4, 5, 6, 6, 7, 7, 7, 8 |
| SauceDemo Linear | 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 10 |
| SauceDemo Full | 1, 2, 3, 4, 4, 5, 6, 7, 7, 8, 9, 10, 11, 11, 11, 11, 12, 13, 14, 14, 14 |
| Practice Shopping Random | 1, 2, 2, 3, 3, 3, 4, 5, 6, 7, 7 |
| Practice Shopping Linear | 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 7 |
| Practice Shopping Full | 0, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 7, 8, 9 |

## Replay 的新增覆盖

该指标只归因于 replay 之后的普通候选 attempts，不把 replay GUI 动作计入普通预算：

- SauceDemo Full：第 13 个普通 attempt 后累计 11 项；3 次成功 replay 之后，第 17–19 个 attempt 新增 SD17、SD19、SD21，共 3 项新增覆盖；成本为 20 个 replay GUI actions。
- Practice Shopping Full：第 16 个普通 attempt 后累计 7 项；1 次成功 replay 后，第 17–18 个 attempt 新增 PS10、PS11，共 2 项新增覆盖；成本为 1 个 replay GUI action。

跨条件的 Full 减去同站点 Linear 差值分别为 SauceDemo +4 项、Practice Shopping +2 项，但这是 run-level 描述，不应替代上述在同一 Full 轨迹中、按 replay 后 attempt 观察到的新增覆盖。
