# E003 / C1 正式运行配置 v4

> 状态：已冻结。冻结后不得改动；任何变更新建版本。

## 相对 v3 的修订

- OpenAI candidate/visual provider 的响应上限从 700 提高到 1400 tokens，以容纳最多 12 个候选的严格 JSON 响应。
- v3 的两个 0-attempt runs 原样保留为诊断记录，不进入正式统计。

## 正式范围与规则

- SauceDemo 沿用 `E003_c1_v1` 的 3 个正式 runs，不重跑。
- Practice Shopping 独立运行 3 次，每次从 `https://practiceautomatedtesting.com/shopping` 和全新浏览器上下文开始。
- 每个 run 最多 25 个正式 attempts；每个 location 最多 12 个候选。
- 失败 attempt 保留全部已有记录。缺少可比较 before/after evidence 时标记 evidence-incomplete，Evidence-grounded admission 不准入，但不使整个 run 无效。
- 知识按 `site + semantic_location + canonical_action_id` 聚合；筛选按业务维度区分，同一维度的具体值保存在冻结的 `execution_instance` 中。
- 输出目录：`outputs/paper/formal/E003_c1_v4/practice_shopping/run_01` 至 `run_03`。

## 冻结实现与参数

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-12 |
| 代码提交 | `587b6f2162a5cc7471b0fc27df9055ea799cc2aa` |
| Candidate prompt SHA-256 | `b38e7d3b17fee981da9c2f92c2abe463d12ccbfbd9a929ba531044eaf4bde275` |
| OpenAI visual provider SHA-256 | `44ce0efb473f71ef992b1b21c044b4ec74cd15c809e7f7a7de1cdf03e21d0046` |
| Candidate/visual response max tokens | 1400 |
| Stagehand / candidate / outcome 模型 | `gpt-4o` |
| Stagehand execution mode | `observe_act` |
| max exploration steps | 25 |
| max candidates per location | 12 |
| max action attempts per candidate | 2 |
| max VLM scan attempts | 2 |
| frontier replay | 开启 |
| max replay attempts per frontier | 2 |
| max total replays | 4 |
| 最终订单/提交动作 | 允许；仅限受控测试流程 |
