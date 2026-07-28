# OpenMobile/SEE 风格网页探索 V1 设计

## 目标

下一阶段应该停止继续打磨 task-guided checkout prompt，转向做一个最小可运行的网页探索闭环。

目标不是一次性做完整自由探索，也不是追求全站覆盖率。目标是证明 Web-KOBE 可以反复探索网站中的有用功能，把状态变化记录进 `WebKobeGraph`，并保持 graph -> PDDL -> SafeSym 这条链路可消费。

这个设计借鉴 OpenMobile 和 SEE 中最实用的部分：

- 用历史交互形成图和记忆；
- 选择动作时考虑已探索状态和重复动作；
- 优先探索有功能意义的交互，而不是点击所有 DOM 元素；
- 让收集到的图继续作为 PDDL 和 SafeSym 的输入。

## 不做什么

- 不替换现有 graph 模型。
- 不做完整 crawler、replay、backtracking 或复杂 coverage optimizer。
- 不新建一套独立持久化 memory 数据库。
- 不把 DOM/UI/schema facts、截图、embedding、Stagehand 文本直接投影进 PDDL。
- 不要求人为设计一套通用网站变量 schema。

## 架构

第一版继续保持现在的边界：

```text
Stagehand
  -> 动作观察和动作执行

Web-KOBE grounded_web
  -> 状态观察、profile facts、图构建、探索策略

SafeSym bridge
  -> graph-to-PDDL、PDDL smoke、SafeSym smoke
```

`WebKobeGraph` 仍然是唯一持久化记忆。可以新增一个派生的 `GraphExplorationIndex`，但它只是从 graph 和可选 embedding sidecar 生成的查询视图/缓存，不能成为第二套真相来源。

## 探索循环

每一步使用一个简单循环：

```text
观察当前状态
生成当前状态摘要
用 embedding 查询相似 graph node
从 graph 派生已探索/已尝试/应避免动作
让 Stagehand 给出候选有用动作，或执行一个受引导动作
执行一个动作
观察动作后状态
推断 planning transition
记录 node/edge/update planning_state
需要时执行 PDDL smoke
```

循环必须有边界，例如 `max_steps`、同状态重复次数限制、无进展次数限制。

## 状态身份

V1 使用 embedding 作为主要的重复状态识别方式。原因很直接：它简单、通用，不需要我们提前为不同网站设计复杂 schema。

每个 node 生成一段紧凑的 `state_summary_text`，来源包括：

- 规范化后的 URL/path；
- 页面标题；
- 主要可见区域；
- 可见表单、弹窗、modal、购物车；
- 主要有用控件；
- 当前 active profile planning facts；
- 如果有 VLM，则加入简短视觉摘要。

初期 graph 很小，embedding 查询可以直接线性比较，不需要 vector DB。

阈值可以先这样设：

- `>= 0.90`：大概率是同一个/重复状态；
- `0.82-0.90`：相似但不确定，不自动强合并；
- `< 0.82`：大概率是新状态。

为了避免明显错误合并，需要两个最低限度的保护：

- profile planning facts 明显冲突时，不自动合并；
- modal/form/cart 等关键上下文明显不同时，不自动合并。

embedding 最好不要直接塞进 `graph.json`。建议放在 sidecar 文件里，例如 `state_embeddings.json`，这样 graph 仍然清晰可读。

## 动作选择

Stagehand 可以负责候选动作发现和底层执行，但探索策略仍然由项目自己掌握。

第一版策略：

- 优先选择和网站功能相关的动作；
- 优先选择可能改变业务状态或打开新功能区域的动作；
- 降低同一状态或相似状态下重复动作的权重；
- 降低 no-op、失败、外链、footer/legal/social、主题切换、语言切换等动作权重；
- 每一步只执行一个动作；
- 如果当前状态被识别为已访问，就把已尝试动作和应避免动作写进 Stagehand 指令，让它换方向。

这相当于吸收 SEE 的 action ranking 思想，但不实现复杂搜索算法。

## 图记录

现有 graph 语义保持不变：

- `node` 表示可以回到并继续探索的页面/上下文状态；
- `node.planning_state` 记录该状态下已知 profile facts；
- `edge` 表示一次实际执行过的动作；
- `edge.planning_transition` 记录 `pre_facts`、`added_facts`、`removed_facts`；
- 第一版可以保留 failed/no-change edge，作为负样本和诊断证据。

graph 可以记录一些解释探索决策的 metadata，但这些 metadata 不能进入 PDDL。

有用 metadata 包括：

- 匹配到的历史 node id 和 similarity score；
- 这个动作是否重复；
- 这条 edge 是新状态、重复状态、no-op 还是失败；
- 动作为什么被选择或降权。

## PDDL 映射

V1 不需要重新设计 PDDL 映射。当前策略仍然成立：

- location 来自 graph node；
- action precondition/effect 来自 `edge.planning_transition`；
- planner-facing facts 只来自预设 profile facts；
- UI facts、DOM evidence、截图、embedding、Stagehand 自然语言都只是证据，不是 predicate。

这样探索能力的改进就不会和 SafeSym projection 强耦合。

## 异常处理

Stagehand 执行异常不一定导致实验失败。如果页面或 planning facts 发生了可观察变化，可以把 edge 记录为 `succeeded_with_observed_change`，同时保留原始异常 metadata。

遇到这些情况应该停止：

- 浏览器导航不可恢复失败；
- 无法生成 observation；
- graph 序列化或 PDDL smoke 失败；
- 超过配置的重复状态/无进展限制；
- 即将越过真实敏感动作边界，且没有明确许可。

## 测试

实现时应该先写测试。第一批单元测试覆盖：

- state summary 生成；
- embedding node matching 和 guard rules；
- 从 graph 派生 explored/tried/avoid action；
- 重复/no-op 动作降权；
- PDDL projection 仍然排除 UI/schema/embedding facts。

然后加一个 fake Stagehand 后端的小型集成测试，模拟：

```text
home -> product list -> cart -> checkout-like form
```

真实网站实验仍然需要显式手动运行，因为它依赖网络、模型延迟和浏览器状态。

## 成功标准

V1 成功的标准是：

- 可以在没有 task-specific checkout script 的情况下探索一个网站数步；
- 重复动作相比当前流程明显减少；
- 能识别重复状态，并用这个信息引导 Stagehand 换方向；
- graph 输出仍然可读，且 SafeSym 可以消费；
- PDDL 仍然只使用 node identity 和 profile planning facts。

## 第一版实现切片

第一版要刻意小：

1. 增加 state summary 生成。
2. 增加 embedding-backed state matching 和 guard checks。
3. 增加从 graph 派生的 exploration index。
4. 增加 Stagehand exploration prompt/context，包含 tried 和 avoid actions。
5. 增加 exploration-style experiment CLI。
6. 先用 fake backend 测试，再跑真实网站。

这样我们可以先仿照 OpenMobile/SEE 把探索链路跑通，同时避免过度设计。
