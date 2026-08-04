# 当前项目概览

这份文档是项目的高层接力说明，只记录当前方向、阶段判断、主要问题和下一步优先级。更细的模块结构请看
`docs/project-structure.zh-CN.md`；重要决策原因请看 `docs/project-decisions.zh-CN.md`。英文版
`docs/current-project-overview.md` 用于 AI 接力和代码上下文。

## 一句话目标

这个项目不是通用 web agent 产品，而是面向 SafeSym 的网页探索与规划建模系统：

```text
真实网站交互
  -> 观察动作前后的页面和业务状态变化
  -> 构建 WebKobeGraph
  -> 抽象出 planner-facing 状态和动作
  -> 投影成 PDDL
  -> 交给 SafeSym 解析、安全检查注入和规划验证
```

核心问题不是“让模型完成一个网站任务”，而是：

```text
如何把真实网页交互转换成稳定、可审查、可规划、可被 SafeSym 消费的状态图。
```

Stagehand、Playwright、VLM/LLM、embedding 都是工具或证据来源。Web-KOBE 自己必须拥有图结构、状态记忆、PDDL 语义和探索控制权。

## 当前阶段判断

项目已经完成早期端到端链路验证：

```text
真实浏览器执行 -> graph -> PDDL -> SafeSym smoke
```

现在正在从 task-guided checkout baseline 转向 bounded exploration V1。当前目标不是继续优化单一 checkout prompt，而是建立最小可用的网页探索闭环：

```text
观察当前状态
  -> 生成当前页面可执行的业务候选动作
  -> 根据当前节点 frontier、已尝试候选、graph memory 和 embedding memory 选择一个未完成业务动作
  -> 执行动作
  -> 观察 before/after 业务变化
  -> 更新 node、edge、planning_state、planning_transition
  -> 生成或更新 PDDL/SafeSym 产物
  -> 如果当前节点候选耗尽，则回退到仍有 frontier 的历史节点
  -> 根据步数、重复、frontier 或目标覆盖决定是否继续
```

当前客观状态：

```text
真实浏览器链路：已成立
graph/PDDL/SafeSym 工程链路：已成立
VLM visual delta：已接入
business affordance 生成：已有初版
embedding memory：已接入，用于相似状态定位和重复提示
target matching：已有初版，动作后会尝试用 embedding + planning facts 复用已有业务节点
source 定位：正常探索默认信任当前节点指针；embedding source match 只作为恢复/诊断信号
frontier / DFS 探索策略：最小 business-affordance selector/backtrack 行为已实现；graph meta 已输出 frontier_metrics
连续无进展终止：已实现；failed/no-op 不再单次终止，达到阈值才停止
Stagehand thinking/tool_choice 异常：已定义为非致命异常；无变化时记为 no-op 而不是 failed edge
generated facts 记录：graph 层已接住，PDDL 默认不投影
自由探索策略：尚未稳定
profile fact verifier：尚未真正建立
PDDL 语义质量：可消费，但还不够稳定和可读
业务节点命名：materialized business node 已能从 profile hints / facts / action 推导 label
```

详细 pipeline 和模块职责见 `docs/project-structure.zh-CN.md`。

## 当前核心判断

### 1. WebKobeGraph 是主线图结构

旧 `WebObservedGraph` 探索栈已经从 active source tree 删除。当前探索、PDDL 和 SafeSym 主链路都应围绕：

```text
WebKobeGraph
WebKobeNode
WebKobeEdge
PlanningState
PlanningTransition
BusinessAffordance
BusinessTransition
```

历史 `WebObservedGraph` 设计只保留在旧 spec/plan 文档中作为参考。

### 2. profile facts 需要降低影响

profile facts 不是网页状态全集。它们的新定位是：

```text
PDDL 候选谓词词表 + 优先观察目标 + 跨网站语义对齐锚点
```

Graph 层现在允许记录 profile facts 和 generated facts；PDDL 层默认仍保守消费 profile facts。后续需要设计 generated facts 的晋升和可选投影策略。

### 3. 探索控制权必须留在本地系统

当前长期职责边界固定为：

```text
VLM 观察当前页面，并提出业务动作候选
本地 current-node pointer 维护 source 位置
本地 graph / embedding memory 做 target merge、recovery 和动作去重
Stagehand 只执行被选中的动作
VLM 总结动作前后的可见业务变化
graph policy 决定 create / merge / revisit
PDDL projector 确定性消费 graph 中已经记录的语义
```

这意味着 VLM 不应该判断“动作是否做过”“当前状态是否是新节点”“是否应该建新节点”。VLM 没有稳定的 graph 记忆，它应该提供的是页面证据、候选业务动作和 before/after 变化摘要。

正常探索不应每一步都用 embedding 重新定位 source。source 默认来自上一条成功 edge 的 target；如果动作生成新节点就跳转过去，如果命中旧节点就跳到旧节点，如果没有有效变化就留在原地。embedding source match 只用于 browser back、页面刷新、实验恢复、外部导航或浏览器实际位置和 graph 指针可能不一致的恢复场景。

动作去重不应只依赖 `node_id + action_slug`。这个方式可以作为快速索引，但相似节点上的动作记忆可以由 embedding-assisted memory 辅助：

```text
current / target state summary
  -> embedding match 到已有 node / state variant
  -> 查询相似节点下已经尝试过的业务动作或可复用目标状态
  -> 对重复或低价值动作降权或跳过
```

Profile facts 可以帮助对齐 planner-facing 语义，但不是唯一探索边界。Graph 可以记录 generated facts；默认 PDDL 仍只投影 profile facts，直到后续有晋升或显式投影策略。

### 4. Stagehand 是操作层，不是状态真相层

Stagehand 可以看页面、生成候选、执行动作和提供 trace，但不能直接决定：

- node identity；
- planning facts；
- PDDL predicates/effects；
- safety triggers；
- 探索是否完成。

状态真相应来自 Web-KOBE 的 before/after observation、VLM/结构化证据、graph memory 和后续 verifier。

在推荐探索链路里，Stagehand 应被视为动作执行器。它的 prompt 应接近“执行这个被选中的业务动作并停止”，而不是“探索网站并自己选择下一个有用目标”。Generic Stagehand exploration prompt 只能作为 fallback。

### 5. PDDL projector 应保持确定性

PDDL projector 应消费 graph 中已经记录的语义，不应直接调用 LLM/VLM，也不应自由发明谓词。

当前 PDDL 主要来自：

```text
node location
node.planning_state.profile_fact_ids 默认投影
edge.action.canonical_action_name
edge.planning_transition 中属于 profile facts 的 pre/added/removed facts
```

命名问题暂缓，但方向是：LLM/VLM 可以在探索阶段帮助生成语义 label；PDDL projector 只做确定性规范化和投影。

### 6. Graph 质量优先看业务状态唯一性

当前 graph 质量评价不应只看是否生成了节点、边和 PDDL，还要看业务状态是否稳定。基本原则是：

- 相同业务状态只能有一个节点；例如无论从首页、商品详情页还是其他页面进入购物车，都应指向同一个购物车业务节点。
- 边可以表达不同来源路径，节点不能因为来源路径不同而重复表达同一个状态。
- 新节点必须代表有意义的业务状态变化；如果只是在 `cart_has_items` 已经成立后把同一商品数量从 1 增加到 2，而我们暂不建模数量，就不应生成新的业务状态节点。
- 状态合并应优先于创建；动作执行后应先用 planning facts、VLM state summary 和 embedding 匹配已有节点，只有不匹配时才创建新节点。
- 节点命名要语义稳定；如果 PDDL 出现大量 `at_product_details_002` / `at_shopping_003`，通常说明 graph 的节点合并或命名存在问题。
- 每个节点和边都要能追溯到 evidence，包括 VLM summary、planning facts、before/after 截图或结构化观察。

### 7. 探索策略应以 frontier 为核心

当前确认的第一版探索策略是简单 DFS / frontier，而不是让 Stagehand 或 VLM 自由规划：

- 每个业务节点拥有 3-5 个当前可执行的 business affordances；这些候选只在节点首次获得 frontier 时写入，后续 revisit / target merge 回到同一节点时不再重新生成或追加。
- 本地系统把候选动作标记为未尝试、已尝试、no-op 或失败；VLM 只负责提出候选和证据，不负责记忆。
- 当前节点优先执行未尝试候选；动作成功后，若产生新业务状态就移动到新节点，若命中已有业务状态就移动到已有节点，若没有有效变化就留在原节点。
- 当前节点候选都尝试完后，不能继续重复“非 avoid 的成功动作”，而应回退到上一个仍有未尝试候选的节点。
- 停止条件包括最大步数、没有 frontier、多次重复状态、连续 no-op/失败，以及显式 terminal 状态。

短期先从已有 edges 反查 tried/no-op/failed 状态，不新增复杂 memory 表。旧的 selector/locator fallback 已删除；business-affordance selector 不再在候选耗尽后继续选择成功但已尝试的动作。browser back 成功后会用轻量 visit stack 回退 `_current_node_id`。`graph.meta.frontier_metrics` 已记录每个节点的候选、已尝试、未尝试、no-op、失败、重复 target 命中和 backtrack 次数。后续还需要把 embedding source relocalization 接入更完整的 DFS recovery。

## 当前主要问题

### P0: 相同业务状态还没有稳定合并

最新 Practice Automated Testing Shopping 8 步实验生成了 6 个节点和 8 条边，链路完整，但 graph 质量仍偏低。系统已经能用 target matching 复用部分已有节点，但仍出现 `product_details` / `product_list` 类似状态变体，PDDL 里也出现 `at_product_details_002`、`at_product_list_002` 这类可读性较差的谓词。

这说明 embedding 已经能提供相似状态信号，但目标节点 materialization / merge 逻辑还没有充分消费这个信号。当前已接入 target matching V1：动作后的目标状态会先用 planning facts + embedding 匹配已有节点；匹配成功则 edge 指向已有节点，而不是生成新的状态变体。下一步需要通过真实网站实验确认它是否能减少重复业务节点。

### P0: generated facts 还没有晋升策略

当前 graph 已能记录 generated facts，并在 `PlanningState` 中保留 `profile_fact_ids` / `generated_fact_ids` 来源信息。PDDL projector 默认只投影 profile facts，避免未审核事实污染 SafeSym。

剩余问题是：generated facts 何时可以晋升为 planner-facing facts、是否允许某轮实验显式投影、以及如何通过 verifier 确认它们，目前还没有策略。

### P0: PDDL 语义质量仍不稳定

SafeSym 可以结构性消费当前产物，但 PDDL 的语义质量还不稳定：

- location predicate 仍可能出现 `at_shopping_002` 这类不可读名字；
- materialized business node 已开始用 profile-provided hints / facts / action 推导 label，但非业务节点和重复 label 仍可能不够理想；
- action precondition 依赖 source node 定位，需要继续用实验确认；
- profile facts 不完整时，PDDL 会退化为 location path；
- generated facts 默认不进入 PDDL，可能丢失真实业务状态，需要后续晋升/投影策略弥补。

### P1: 探索还没有真正形成 frontier

当前系统已经有 business affordance 和 embedding memory，但还没有成熟的：

- candidate action ranking；
- tried action memory；
- duplicate/no-op penalty；
- backtracking；
- coverage stop condition。

现在更像 bounded exploration V1，还不是成熟自由探索。此前实验中页面在商品列表和商品详情之间来回切换，核心原因不是 VLM 完全不会提候选，而是旧 selector 在当前节点候选都尝试完后，会回退到“非 avoid 的成功动作”，导致成功但低进展的动作被重复执行。最小修复已完成：当前节点无未尝试业务候选时返回 None，并触发 browser back / visit stack 回退；旧的 LLM action selector / OpenAI action selector 模块已删除，避免探索链路回退到 locator-driven 行为。

controller 已改为连续无进展策略：单次 `failed_execution`、`no_observed_change` 或成功 backtrack 都不会立刻终止；只有连续无进展达到阈值、无法产生 edge 且没有有效控制动作、terminal condition 命中或达到最大步数时才停止。`graph.meta` 会记录 `last_step_kind`、`last_step_status`、`consecutive_unproductive_steps` 和 `max_consecutive_unproductive_steps`。

最近的清理已经把通用 Stagehand exploration 默认模式改为 `observed_action`，保留 VLM 候选动作的 `expected_change`，并移除了业务候选选择中的全局 completed action 降权；重复策略应基于当前节点或 embedding 命中的相似节点上下文。

已知 `Thinking mode does not support this tool_choice` 属于 Stagehand/模型适配异常，不再作为 failed edge 终止实验。若页面没有变化，该动作应记录为 `no_observed_change`，再由本地动作记忆避开并继续尝试其他候选。

### P1: WebKobeExplorer 有中心化风险

`WebKobeExplorer` 目前同时处理观察、动作选择、VLM、embedding、source matching、edge 构造、planning transition 和回退。它是当前主线核心，短期可以保留，但后续新增探索策略时不应该继续把所有逻辑塞进 `explore_one_step`。

### P2: graph 层仍保留底层 UI 证据字段

`interactable_elements` 仍存在于 node 中，主要作为页面观察证据和调试信息。它不再承担动作选择、动作记忆或 frontier 单位职责；`mark_interactable_explored`、`interactables_for_node`、旧 LLM action selector 和对应测试已经删除。业务探索图应逐渐围绕：

```text
business_affordances + business_transition + planning_transition
```

### P2: verifier 缺失

当前 facts 多来自 VLM candidate 或轻量结构化规则。未来 verifier 应判断 candidate facts 是否可以成为 planner-facing truth。

短期先不做完整 verifier，但必须保留 provenance 和 evidence。

## 下一阶段优先级

1. 重跑 Practice Automated Testing Shopping，验证最小 frontier/DFS 是否能离开 product list / product details 循环，并继续观察 cart / checkout 等业务状态。
2. 根据 `graph.meta.frontier_metrics` 分析每个节点候选数量、已尝试/未尝试/no-op/失败统计、回退次数、重复节点命中情况。
3. 检查连续无进展阈值是否合理；第一版 controller 默认阈值为 3。
4. 继续检查 target matching 是否减少重复业务节点，以及 embedding source/target matching 是否只在正确位置发挥作用。
5. 检查 graph 和 domain PDDL 质量，尤其是 source/target、precondition/effect、node label 和重复 `at_*_002`。
6. 讨论 generated facts 的晋升/可选投影策略。
7. 等 graph 层稳定后，评估是否进一步剥离或归档 `interactable_elements` 等底层 UI 证据字段。
8. 后续逐步拆分 `WebKobeExplorer`，避免核心协调类继续膨胀。

## 实验管理规则

每个网站只保留最新一轮有效结果：

```text
outputs/experiments/<site_name>/latest/
```

每轮实验报告至少记录：

- 命令和模型；
- prompt mode；
- execution mode；
- stop reason；
- graph 节点/边数量；
- node merge / revisit 情况；
- embedding records 和 memory hit；
- final planning facts；
- generated facts；
- PDDL smoke 是否 ready；
- SafeSym 是否可消费；
- 异常和 failed/no-op edges；
- 截图上可人工验证的状态变化；
- 客观结论：结构链路、语义链路、探索能力分别是否成立。

## 相关文档

```text
docs/project-structure.zh-CN.md
  当前 pipeline、模块边界和主要函数。

docs/project-decisions.zh-CN.md
  项目决策记录。每次做有意义的架构、pipeline、数据结构或主线清理调整后都要追加记录。

docs/safesym-bridge.md
  SafeSym bridge 命令和实验使用说明。

docs/current-project-overview.md
  本文档英文版，用于 AI 接力。
```
