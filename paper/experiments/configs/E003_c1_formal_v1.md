# E003 / C1 正式运行配置 v1

> 状态：已冻结
>
> 冻结后不得改动；任何变更新建版本。

## 固定实验设计

- 网站：SauceDemo（`https://www.saucedemo.com/`）与 Practice Shopping（`https://practiceautomatedtesting.com/shopping`）。
- repeats：每站 3 个独立 run。
- 预算：每个 run 最多 25 个已选 high-level action attempts。
- 起点：每个 run 使用新的浏览器上下文和入口 URL。
- C1 比较：所有三种准入策略从同一自然探索冻结轨迹离线派生；不为 baseline 重跑探索。
- 统计单位：单次 run 内以 `site + semantic_location + canonical_action_id` 去重后的功能知识。

## 不可变运行信息

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-12 |
| 代码提交 | `50d112ee7008d3d4265f95ecd2a050cb7d9182bd` |
| Stagehand 模型 | `gpt-4o`（CLI 显式传入；用户确认） |
| Outcome verifier 模型 | `gpt-4o` |
| Outcome verifier temperature | 0 |
| Stagehand temperature | Stagehand SDK 默认值；当前 CLI 不暴露该参数 |
| Candidate prompt 源 | `business_affordance.py`，SHA-256 `806ea0c5faa20b68b4cfe84397b2a0e34df1395bfeb3aeccf8d7ceac1034bc1f` |
| Outcome prompt 源 | `action_outcome.py`，SHA-256 `78756f9f85303edce0da78fbd952e25ff1bd3fd2ab7aa95f09106810a1bae577` |
| Stagehand goal prompt 源 | `stagehand_prompt.py`，SHA-256 `a0ea381a3839f823bc98028aaf2c2d63991da2deabe8528438eea42e42ecafc8` |
| Stagehand execution mode | `observe_act` |
| frontier replay | 开启；作为同一 run 内恢复步骤，不计为发现功能 |
| max action attempts per candidate | 2 |
| max replay attempts per frontier | 2 |
| max total replays | 4 |
| 最终订单/提交动作 | 允许；仅限 SauceDemo 与 Practice Shopping 的受控测试流程 |
| 输出根目录 | `outputs/paper/formal/E003_c1_v1/` |

## 每次运行的必存工件

- `graph.json` 与 `graph_evidence.json`；
- Stagehand trace；
- 每次 attempt 的 before/after screenshots；
- 运行命令、环境快照、模型和 prompt 标识；
- 工件完整性审计结果。

若一次 run 缺少必要工件，保留其原始产物并标记无效；不得静默重跑替换。

## 已确认的验收规则

- 每个 run 独立进行工件完整性审计。
- 有效 run 的必要工件完整率须达到 95%；在 25-attempt 上限下最多允许 1 个 attempt 缺少必要工件。超过该阈值则整个 run 无效。
- 缺少必要工件的 run 标记为无效，保留原始产物和无效原因，并计入无效样本率。
- 无效 run 不进入主要指标计算；有效 run 仍按协议独立计算后做网站内平均。
- 每个网站仅运行预先登记的 3 个 run；不得为了替换无效 run 而选择性补跑或删除运行记录。
- 不设每个 run 的最小功能数量门槛；在预算内因 frontier 耗尽而自然结束的 run，若工件合格则纳入统计，并报告实际 attempts 和运行内去重功能数。
- AI 初标和人工审核严格盲化：只展示候选、冻结 `expected_outcome`、实际交互步骤与 before/after evidence；隐藏 executor-reported success、系统 `predicted_outcome`、`evidence_complete` 和三种准入结果。正式包必须由最新版导出器重新生成。
- 结果解释标准暂不预设：正式实验先按本文件固定的设置、指标定义与数据质量规则生成结果；完成全部 run、严格盲化标注和离线统计后，再单独讨论结果解释与补充分析。逐网站报告后按网站 macro-average 汇总，主要比例指标附 bootstrap 95% CI。
- 功能级准入派生：proposal-as-fact 在功能被提出后准入；executor-success-as-fact 在任一次 attempt 的 executor 报成功后准入；evidence-grounded admission 仅在任一次 evidence-complete attempt 的系统 outcome 为 success 后准入。重复失败 attempt 保留为证据，但不增加功能知识条数。
- Replay 只作为同一 run 内的上下文恢复与诊断步骤，不计作 C1 功能候选或 action attempt；replay 后新选出的正常探索动作照常纳入 C1，且 replay 日志完整保留。
