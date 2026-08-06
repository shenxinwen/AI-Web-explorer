# 候选动作局部前提事实设计

## 背景

VLM 负责观察当前网页并提出可直接执行的业务动作。为了让动作能够清晰映射到 WebKobeGraph 和 PDDL，需要记录 VLM 为什么认为某个动作在当前页面可执行。

本设计只处理候选动作的支持事实，不把这些事实扩展为全局节点状态。

## 核心边界

`supporting_facts` 是动作局部前提，表示：

> VLM 在当前页面观察到的、支持执行该业务动作的简短事实短语。

它不是：

- profile facts 的完整副本；
- 节点的全局 `active_facts`；
- 动作执行结果；
- 对动作效果的预测；
- PDDL 中必须永久保留的事实。

例如：

```json
{
  "intent": "search_items",
  "label": "Search",
  "target": "search input",
  "supporting_facts": [
    "search_input_visible",
    "result_collection_visible"
  ]
}
```

## 数据流

```text
页面截图
  -> VLM 候选动作
  -> BusinessAffordance.supporting_facts
  -> 被选动作的 edge action snapshot
  -> PDDL action precondition
```

执行动作后的变化仍然沿用现有的观察链路：

```text
before/after 页面
  -> 结构化 verifier + visual delta
  -> PlanningDelta
  -> PlanningTransition
  -> PDDL action effect
```

`supporting_facts` 不进入 `PlanningDelta`，因为 `PlanningDelta` 表示执行之后新增或移除的事实。

## 结构调整

### BusinessAffordance

增加：

```text
supporting_facts: list[str]
```

候选动作 prompt 只要求输出动作、目标和事实短语，不要求输出 `meaning`、`evidence` 或预期效果。

现有 `expected_change` 不再作为 VLM 候选动作的主要输出。第一阶段可以保留兼容读取，避免一次性破坏旧实验记录和测试；新生成的数据不再依赖它。

### WebKobeGraph edge

被选中的动作需要保存一份 `supporting_facts` 快照。这样即使源节点之后重新生成或更新候选动作，历史 edge 仍然保留当时的动作前提依据。

### PlanningState

第一阶段不增加这些事实到节点的 `active_facts`、`profile_fact_ids` 或 `generated_fact_ids`。同一页面上的不同动作可以拥有不同的局部 supporting facts。

### PDDL projector

第一阶段的目标是让 projector 能够读取 edge 上的 supporting facts，并将其作为对应 action 的候选前提。动作效果仍然只来自执行后的 observed facts，不使用 VLM 对效果的预测。

## 事实短语约束

- 使用简短、稳定、可比较的 snake_case 事实 ID；
- 每个动作只保留与该动作直接相关的事实；
- 不要求事实一定来自 profile；
- 不在事实中携带解释文本、截图坐标或置信度；
- 原始截图和执行 trace 仍然是审查依据。

## 非目标

本阶段不处理：

- supporting facts 与 profile facts 的自动匹配；
- 全局事实晋升或事实置信度传播；
- 候选动作排序；
- 页面区域模型的进一步拆分；
- 完整的 PDDL 事实验证。

## 验收标准

1. VLM 候选动作可以返回 `supporting_facts`，并被解析为 `BusinessAffordance`。
2. 选中的动作及其 supporting facts 能够保存在对应 graph edge 中。
3. supporting facts 不会写入源节点的全局 planning state。
4. 执行后的 added/removed facts 仍由 `PlanningDelta` 独立记录。
5. 旧格式输入仍能被兼容解析，现有测试不因字段增加而失效。
6. 至少覆盖一个有 supporting facts 的动作、一个空 supporting facts 的动作和一次 graph/PDDL 序列化测试。
