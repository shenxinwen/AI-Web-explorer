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
  -> 根据 graph memory / embedding memory / 重复惩罚选择一个动作
  -> 执行动作
  -> 观察 before/after 业务变化
  -> 更新 node、edge、planning_state、planning_transition
  -> 生成或更新 PDDL/SafeSym 产物
  -> 根据步数、重复、frontier 或目标覆盖决定是否继续
```

当前客观状态：

```text
真实浏览器链路：已成立
graph/PDDL/SafeSym 工程链路：已成立
VLM visual delta：已接入
business affordance 生成：已有初版
embedding memory：已接入，用于相似状态定位和重复提示
自由探索策略：尚未稳定
profile fact verifier：尚未真正建立
PDDL 语义质量：可消费，但还不够稳定和可读
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

Graph 层应该允许记录 profile facts 和 generated facts；PDDL 层默认仍保守消费 profile facts。后续需要设计 generated facts 的记录、晋升和投影策略。

### 3. Stagehand 是操作层，不是状态真相层

Stagehand 可以看页面、生成候选、执行动作和提供 trace，但不能直接决定：

- node identity；
- planning facts；
- PDDL predicates/effects；
- safety triggers；
- 探索是否完成。

状态真相应来自 Web-KOBE 的 before/after observation、VLM/结构化证据、graph memory 和后续 verifier。

### 4. PDDL projector 应保持确定性

PDDL projector 应消费 graph 中已经记录的语义，不应直接调用 LLM/VLM，也不应自由发明谓词。

当前 PDDL 主要来自：

```text
node location
node.planning_state.active_facts
edge.action.canonical_action_name
edge.planning_transition.pre_facts
edge.planning_transition.added_facts
edge.planning_transition.removed_facts
```

命名问题暂缓，但方向是：LLM/VLM 可以在探索阶段帮助生成语义 label；PDDL projector 只做确定性规范化和投影。

## 当前主要问题

### P0: profile facts 职责过重

当前代码里 profile facts 仍然影响 VLM 提示、fact 归类、structured verifier、planning_state 传播和 PDDL 谓词。它们还没有完全降级成 planner-facing 参考系。

最直接的问题是：`planning_transition` 仍会被 profile facts 过滤，导致 generated facts 难以进入节点状态。

### P0: PDDL 语义质量仍不稳定

SafeSym 可以结构性消费当前产物，但 PDDL 的语义质量还不稳定：

- location predicate 仍可能出现 `at_shopping_002` 这类不可读名字；
- action precondition 依赖 source node 定位，需要继续用实验确认；
- profile facts 不完整时，PDDL 会退化为 location path；
- generated facts 默认不进入 PDDL，可能丢失真实业务状态。

### P1: 探索还没有真正形成 frontier

当前系统已经有 business affordance 和 embedding memory，但还没有成熟的：

- candidate action ranking；
- tried action memory；
- duplicate/no-op penalty；
- backtracking；
- coverage stop condition。

现在更像 bounded single-path exploration，还不是成熟自由探索。

### P1: WebKobeExplorer 有中心化风险

`WebKobeExplorer` 目前同时处理观察、动作选择、VLM、embedding、source matching、edge 构造、planning transition 和回退。它是当前主线核心，短期可以保留，但后续新增探索策略时不应该继续把所有逻辑塞进 `explore_one_step`。

### P2: graph 层仍混有底层 UI 结构

`interactable_elements`、selector、低层 action trace 仍存在于 graph 结构中。短期可以保留兼容和调试，但业务探索图应逐渐围绕：

```text
business_affordances + business_transition + planning_transition
```

### P2: verifier 缺失

当前 facts 多来自 VLM candidate 或轻量结构化规则。未来 verifier 应判断 candidate facts 是否可以成为 planner-facing truth。

短期先不做完整 verifier，但必须保留 provenance 和 evidence。

## 下一阶段优先级

1. 修正 profile facts 的硬白名单问题，让 graph 能记录 generated facts，同时让 PDDL 默认保持保守。
2. 跑一轮实验验证 embedding source matching 是否真正影响 edge source。
3. 检查 graph 和 PDDL 质量，尤其是 source/target、precondition/effect、node label。
4. 再讨论 PDDL 命名策略，不急着让 LLM 直接参与 PDDL projector。
5. 等 graph 层稳定后，重构或剥离 `interactable_elements` 等底层 UI 字段。
6. 后续逐步拆分 `WebKobeExplorer`，避免核心协调类继续膨胀。

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
