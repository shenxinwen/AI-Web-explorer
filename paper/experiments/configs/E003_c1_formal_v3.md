# E003 / C1 正式运行配置 v3

> 状态：已冻结
>
> 冻结后不得改动；任何变更新建版本。

## 相对 v2 的修订

- Practice Shopping 的 `max_candidates_per_location` 从 8 提高到 12，避免维度级筛选候选挤掉购物车与结账等跨页面功能。
- 不再以 attempt 截图完整率判定整个 run 无效。执行失败 attempt 保留其候选、冻结主张、执行器状态、错误及已有 evidence。
- 缺少可比较 before/after evidence 的 attempt 标记为 evidence-incomplete；Evidence-grounded admission 不准入该 attempt，并单独报告 evidence completeness。
- `E003_c1_v2/practice_shopping/run_01` 保留为诊断运行，不进入正式统计，不删除、不替换。

## 正式运行范围

- SauceDemo 沿用 `E003_c1_v1` 的 3 个正式 runs，不重跑。
- Practice Shopping 从入口 `https://practiceautomatedtesting.com/shopping` 运行 3 个全新独立 runs。
- 每个 run 最多 25 个正式 high-level action attempts。
- 输出目录：`outputs/paper/formal/E003_c1_v3/practice_shopping/run_01` 至 `run_03`。

## 冻结实现与模型

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-12 |
| 代码提交 | `4802934c429ae36b09bd62a4024318d512a38705` |
| Candidate prompt SHA-256 | `b38e7d3b17fee981da9c2f92c2abe463d12ccbfbd9a929ba531044eaf4bde275` |
| Outcome prompt SHA-256 | `78756f9f85303edce0da78fbd952e25ff1bd3fd2ab7aa95f09106810a1bae577` |
| Stagehand goal prompt SHA-256 | `a0ea381a3839f823bc98028aaf2c2d63991da2deabe8528438eea42e42ecafc8` |
| Stagehand / candidate / outcome 模型 | `gpt-4o` |
| Stagehand execution mode | `observe_act` |

## 冻结探索参数

- `max_exploration_steps=25`
- `max_candidates_per_location=12`
- `max_action_attempts_per_candidate=2`
- `max_replay_attempts_per_frontier=2`
- `max_total_replays=4`
- `max_vlm_scan_attempts=2`
- frontier replay 开启；replay 不计为正式功能候选或 action attempt。
- 最终订单动作仅限受控测试网站，允许执行。

## 知识与准入规则

- 筛选按业务维度形成 canonical action；同一维度的具体值保存在 `execution_instance` 中。
- 知识按 `site + semantic_location + canonical_action_id` 聚合；重复 attempts 不增加知识条数。
- Proposal-as-fact：功能被提出即准入。
- Executor-success-as-fact：任一次 attempt 的执行器报告成功即准入。
- Evidence-grounded admission：仅当任一次 evidence-complete attempt 的 outcome 为 success 时准入。
- 失败和 evidence-incomplete attempts 全部保留，不静默删除。

## 必存工件

- `graph.json`、`graph_evidence.json`、Stagehand trace、已有 before/after screenshots、state embeddings。
- 每个 run 报告 attempts、候选数、locations、停止原因、executor status、outcome status 和 evidence completeness。
- 严格盲化标注包隐藏 executor-reported success、系统 outcome、evidence completeness 和三种准入结果。
