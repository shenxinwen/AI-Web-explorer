# 业务动作探索职责边界设计草案

日期：2026-08-02

状态：草案，待审查

## 背景

项目已经从“让模型完成一个购物任务”逐步转向“面向 SafeSym 的网页业务探索”。当前要避免继续把探索策略写进 prompt 里，否则系统会变成由 Stagehand 或 VLM 临时规划的任务代理，而不是 Web-KOBE 自己掌握图结构、记忆和 PDDL 语义的探索系统。

本设计固定一个已经讨论过的方向：

```text
VLM 负责看页面和总结候选业务动作
本地 graph / embedding memory 负责去重、定位、选择和建图
Stagehand 负责执行已经选中的动作
PDDL projector 只消费 graph 中已经记录的 planner-facing 语义
```

## 目标

- 明确 VLM、Stagehand、本地 graph/index、PDDL projector 的职责边界。
- 将“动作是否做过”“当前是否回到已有节点”“是否应该创建新节点”等判断收回到本地系统。
- 固定 embedding matching 在探索链路中的位置：它是状态重复识别和当前节点定位的主机制之一。
- 降低 prompt 对探索方向的硬编码，让系统逐步接近自由探索。

## 非目标

- 本轮不实现 verifier。
- 本轮不重构全部 graph 数据结构。
- 本轮不解决 generated facts 晋升策略。
- 本轮不追求完整 DFS/backtracking，只为后续预留接口。
- 本轮不让 PDDL projector 调用 LLM/VLM。

## 核心原则

### 1. VLM 只负责观察，不负责记忆

VLM 可以回答：

- 当前页面能执行哪些业务动作；
- 每个动作的可见证据是什么；
- 该动作可能带来什么业务状态变化；
- 执行动作前后页面发生了什么显式变化。

VLM 不应该回答：

- 这个动作之前是否做过；
- 这个状态是不是已有 graph node；
- 这个动作是否应该 create new node；
- 这个事实是否可以直接进入 PDDL。

原因是 VLM 没有稳定的本地记忆，也不拥有 graph 历史。记忆和建图判断必须由 Web-KOBE 控制。

### 2. Stagehand 是执行器，不是探索策略

Stagehand 的输入应该是本地选择器选中的一个业务动作，例如：

```text
open cart
view product details
add a product to cart
start checkout
fill required user information
```

Stagehand 的职责是完成这个动作并停止。它不应该自己决定下一步探索目标，也不应该因为页面上还有其它按钮就继续执行后续业务流程。

理想 prompt 语义应接近：

```text
Execute the specified business action only.
Stop after the first visible completion of that action.
Do not choose a different business goal.
Report visible evidence of what changed.
```

### 3. 本地系统负责动作选择和去重

候选动作由 VLM 生成，但动作选择由本地完成。本地选择时主要使用：

- 当前 graph node；
- 当前页面与已有节点的 embedding match；
- 当前节点或相似节点下已经尝试过的业务动作；
- 动作历史结果，如成功、新节点、重复、无变化、失败；
- 简单业务优先级规则，如优先页面跳转、购物车、checkout、订单完成，降低排序、筛选、下载、关闭弹窗等动作权重。

去重不应只依赖 `node_id + action_slug`。这个方式可以作为快速索引，但主机制应是 embedding-assisted memory：

```text
current page/state summary
  -> embedding match
  -> 找到相似已有 node 或 state variant
  -> 查询这些节点下的 tried business actions
  -> 对重复动作降权或跳过
```

这样即使 browser back、同 URL 页面、或者视觉上回到旧状态，系统也能通过 embedding 辅助定位，而不是只依赖 URL 或当前指针。

### 4. Graph 负责节点身份和状态边界

是否生成新节点由本地 graph policy 判断。VLM 可以提供变化摘要和候选 facts，但不能直接决定建节点。

短期节点生成判断可以采用多信号：

- 业务动作执行成功；
- VLM 认为存在显式业务变化；
- planning facts 或 generated facts 有实质变化；
- 当前状态与已有节点 embedding 不相似，或虽相似但 planning facts 不兼容；
- 动作属于高价值业务边界，如进入详情、购物车、checkout、订单完成、错误/阻塞状态。

如果动作只是排序、筛选、下载、关闭弹窗、重复填写、改变选项，并且没有形成新的业务状态，则倾向于记录为低价值尝试或普通 edge evidence，不创建新的核心业务节点。

### 5. Profile facts 是观察锚点，不是探索边界

Profile facts 的定位保持为：

```text
PDDL 候选谓词词表
+ 优先观察目标
+ 跨网站语义对齐锚点
```

它不应成为“只有命中 profile fact 才能建节点”的硬约束。真实探索中会出现 profile 未覆盖的状态，VLM 可以补充 generated facts。只是默认情况下，PDDL 仍应只投影 profile facts，直到 generated facts 有晋升或显式投影策略。

## 推荐 Pipeline

```text
1. observe current browser state
2. build state summary
3. use embedding to match current state against graph memory
4. VLM scans current page and returns 3-5 business action candidates
5. local selector ranks candidates using graph memory and repetition penalties
6. Stagehand executes exactly one selected business action
7. VLM compares before/after screenshots and summarizes visible business change
8. graph policy decides whether to create, merge, or revisit node
9. edge records action, source, target, evidence, planning_transition
10. PDDL domain projection consumes graph semantics deterministically
```

关键点：

- 第 3 步 embedding match 用于定位当前状态和查询记忆。
- 第 4 步 VLM 不知道哪些动作做过，只负责列出候选。
- 第 5 步本地 selector 才知道历史。
- 第 6 步 Stagehand 只执行动作，不规划。
- 第 8 步本地 graph policy 才决定 node。

## 动作候选格式建议

VLM 生成候选动作时，建议返回稳定结构：

```text
action_name: 规范化业务动作名，例如 open_cart
label: 页面上的自然语言描述
target_hint: 可能到达的业务状态，例如 cart_review
expected_change: 预期可见变化，例如 cart page opens
evidence: 页面上支持该动作存在的证据
confidence: 置信度
```

不要要求 VLM 返回：

```text
already_done
should_create_node
is_new_state
```

这些字段属于本地记忆和 graph policy。

## 动作记忆与去重

本地需要逐步形成一个业务动作记忆视图。短期可以不新建独立 memory store，而是基于 graph 和 embedding records 查询：

```text
current_state_embedding
  -> similar nodes
  -> outgoing edges / tried business actions
  -> action outcome summary
```

查询示例：

```text
当前页面看起来像 product_list
embedding 命中 product_list__business_2 和 product_list__business_5
这两个节点下已经尝试过 view_product_details / add_to_cart
本轮 VLM 又提出 add_to_cart / sort_products / open_cart
本地 selector 降低 add_to_cart 的重复权重
如果 open_cart 未尝试且业务价值更高，则选择 open_cart
```

这比简单的 `当前 node id + action slug` 更稳，因为当前指针可能落后、browser back 后需要重新定位，同一 URL 也可能对应不同业务状态。

## Stagehand Prompt 方向

Stagehand prompt 应该从“探索站点功能”改成“执行指定动作”：

```text
Execute this selected business action: {action_label}.
Only perform the steps necessary to complete this action.
Stop after the first visible completion or clear failure.
Do not continue to the next business goal.
Do not choose another action if this one is possible.
Report what visible evidence shows the action completed or failed.
```

如果没有 VLM 候选动作，才允许使用 generic fallback prompt。但 fallback 也应该弱化为“选择一个明显的业务动作并执行一次”，而不是完整规划网站任务。

## 与 PDDL 的关系

PDDL 映射不直接使用 VLM prompt 结果，而是使用 graph 中稳定记录的语义：

- node location / node_label；
- node.planning_state.profile_fact_ids；
- edge.action.canonical_action_name；
- edge.planning_transition.pre_facts / added_facts / removed_facts；
- generated facts 默认保留在 graph 中，不进入 PDDL。

因此，探索侧要保证 edge 和 node 记录的是业务语义，而不是 Stagehand 的底层点击细节。Stagehand trace 可以保留在实验 trace 文件中，但不应成为 PDDL 的主要语义来源。

## 已知风险

### 1. 候选动作抽象粒度不稳定

同一个页面，VLM 可能一次说 `checkout`，另一次说 `fill shipping information`。这会影响动作记忆。

短期缓解：

- prompt 要求 action_name 使用短小动词短语；
- 本地对 action_name 做 slug normalization；
- embedding memory 辅助识别相似状态下的相似动作；
- 后续可以增加 action embedding 或 action canonicalizer。

### 2. Embedding 可能误合并状态

页面文本相似但业务状态不同，例如商品列表和已加购后的商品列表，embedding 可能很接近。

短期缓解：

- embedding match 不能单独覆盖 planning facts 不兼容判断；
- 当 profile/generated facts 明显冲突时，应生成 state variant；
- source pointer 和 embedding match 要协同，而不是互相覆盖。

### 3. Stagehand 仍可能越界执行

即使 prompt 收紧，模型也可能顺手完成后续步骤。

短期缓解：

- prompt 明确只执行一个动作；
- before/after VLM 检查动作实际效果；
- edge evidence 记录实际发生了什么；
- 如果实际动作与选中动作偏离，记录异常，不让 PDDL 盲目信任 action name。

### 4. 低价值动作仍可能污染 graph

排序、筛选、下载、关闭、修改选项可能造成视觉变化，但不一定是业务状态边界。

短期缓解：

- selector 降权；
- graph policy 要区分“有变化”和“值得 materialize 的业务状态变化”；
- 低价值动作可记录为 tried action / evidence，但不一定生成核心节点。

## 第一版实现边界建议

第一版只做最小闭环：

1. 改候选动作 prompt：VLM 只列动作、证据、预期变化，不提 create new node / already tried。
2. 改 Stagehand prompt：只执行本地选中的动作，不做探索规划。
3. 明确 embedding match 的结果进入本地选择器和 source matching，而不是仅作为参考日志。
4. 本地记录相似节点下的 tried business actions，用于重复降权。
5. 建节点判断继续保守：成功动作 + 显式业务变化 + 不与已有节点重复或 facts 不兼容。

暂时不做：

- verifier；
- generated facts 自动晋升；
- 完整 DFS/backtracking；
- 大规模 graph schema 重构；
- PDDL problem 自动生成。

## 待确认问题

1. 候选动作数量第一版固定为 3 还是 5？
2. 低价值动作是直接过滤，还是保留但大幅降权？
3. Stagehand 越界完成多个业务动作时，是拆成多个 edge，还是先记录异常并只保留一个 edge？
4. embedding 相似度阈值是否沿用当前配置，还是为回退定位单独设置阈值？

