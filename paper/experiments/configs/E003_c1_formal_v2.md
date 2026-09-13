# E003 / C1 正式运行配置 v2

> 状态：已冻结
>
> 冻结后不得改动；任何变更新建版本。

## 修订范围

- SauceDemo 沿用 `outputs/paper/formal/E003_c1_v1/saucedemo/` 中已经完成的 3 个正式 runs，不重跑。
- Practice Shopping 的 v1 轨迹完整保留，但不进入最终 C1 统计。
- Practice Shopping 使用本配置重新运行 3 个独立 runs，写入 `outputs/paper/formal/E003_c1_v2/practice_shopping/`。
- 修订原因：v1 将不同筛选维度聚合为宽泛的 `filter_results`，且未冻结具体筛选值，候选—执行契约不足。

## 候选与知识粒度

- 筛选按业务维度形成 canonical action，例如 `filter_by_category`、`filter_by_price`、`filter_by_rating`、`filter_by_availability`。
- 同一维度内的不同值不是不同知识；它们通过 `execution_instance` 表示本次 attempt 的具体实例。
- 每个新候选必须在执行前冻结非空 `execution_instance` 和 `expected_outcome`。
- `target` 与 `execution_instance` 必须指向当前可见的具体控件、对象、选项或值。
- 展开菜单、滚动到控件或聚焦输入框不构成核心功能完成。
- 知识仍按 `site + semantic_location + canonical_action_id` 聚合；重复 attempts 不增加知识条数。

## 固定实验设计

- 网站：Practice Shopping（`https://practiceautomatedtesting.com/shopping`）。
- repeats：3 个独立 runs。
- 预算：每个 run 最多 25 个已选 high-level action attempts。
- 起点：每个 run 使用新的浏览器上下文和入口 URL。
- C1 比较：三种准入策略从每个 run 的同一冻结轨迹离线派生，不为 baseline 重跑探索。

## 不可变运行信息

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-12 |
| 代码提交 | `4802934c429ae36b09bd62a4024318d512a38705` |
| Stagehand 模型 | `gpt-4o` |
| Outcome verifier 模型 | `gpt-4o` |
| Outcome verifier temperature | 0 |
| Stagehand temperature | Stagehand SDK 默认值；当前 CLI 不暴露该参数 |
| Candidate prompt 源 | `business_affordance.py`，SHA-256 `b38e7d3b17fee981da9c2f92c2abe463d12ccbfbd9a929ba531044eaf4bde275` |
| Outcome prompt 源 | `action_outcome.py`，SHA-256 `78756f9f85303edce0da78fbd952e25ff1bd3fd2ab7aa95f09106810a1bae577` |
| Stagehand goal prompt 源 | `stagehand_prompt.py`，SHA-256 `a0ea381a3839f823bc98028aaf2c2d63991da2deabe8528438eea42e42ecafc8` |
| Stagehand execution mode | `observe_act` |
| frontier replay | 开启；replay 不计为功能候选或正式 action attempt |
| max candidates per location | 8 |
| max action attempts per candidate | 2 |
| max replay attempts per frontier | 2 |
| max total replays | 4 |
| max VLM scan attempts | 2 |
| 最终订单/提交动作 | 允许；仅限受控测试流程 |
| 输出根目录 | `outputs/paper/formal/E003_c1_v2/practice_shopping/` |

## 运行前资格检查

- 非正式 Practice Shopping smoke 将筛选拆为 category、price、rating、availability 和 deals，并冻结了具体实例。
- category、rating 和 availability 在 smoke 中产生可观察变化并通过 outcome verification；price 的失败被保留为失败证据。
- 该 smoke 的 PDDL 投影排除了失败动作，SafeSym parser、安全注入和 Fast Downward base/safe planning 均成功。
- 非正式 SauceDemo smoke 不进入正式统计；它显示当实例选择当前默认排序值时，页面不变化且 C1 正确判为失败。

## 每次运行的必存工件与验收规则

- 保存 `graph.json`、`graph_evidence.json`、Stagehand trace、每次 attempt 的 before/after screenshots、运行命令、环境快照、模型和 prompt 标识。
- 每个 run 独立审计；必要工件完整率须达到 95%，最多允许 1 个 attempt 缺少必要工件。
- 无效 run 保留原始产物和无效原因，不补跑替换。
- 不设最小功能数门槛；预算内自然耗尽 frontier 的完整 run 仍纳入统计。
- 标注包严格盲化，只展示候选、冻结的 `execution_instance` 与 `expected_outcome`、实际交互和 before/after evidence。
- 隐藏 executor-reported success、系统 outcome、evidence completeness 和三种准入结果。
- Proposal-as-fact 在功能被提出后准入；executor-success-as-fact 在任一次 attempt 的 executor 报成功后准入；evidence-grounded admission 仅在任一次 evidence-complete attempt 的系统 outcome 为 success 后准入。
