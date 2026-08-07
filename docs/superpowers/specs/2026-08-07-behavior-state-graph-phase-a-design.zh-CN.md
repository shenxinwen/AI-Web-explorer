# 行为状态图 Phase A 设计

## 目标

第一阶段先构造状态级业务行为图，再逐步增加稳定业务事实。当前只生成 `domain.pddl`，不推断任务目标，也不生成 `problem.pddl`。

状态抽象以业务动作可达性为准，不追求完整描述网页。两个网页观测只有在可执行的 canonical 业务动作相同，且每个动作导向相同类型的抽象结果状态时，才属于同一行为状态。具体商品、条目或其他业务对象不进入状态身份。

## 范围与假设

Phase A 假设网页行为稳定：同一行为状态执行同一业务动作会得到同一结果状态。暂不处理偶发登录过期、随机弹窗、执行环境异常或非确定性转移。

Phase A 的主要目标是验证：

- graph 能稳定表达有限业务状态和确定转移；
- 相同行为状态不因 VLM fact 措辞漂移而持续膨胀；
- PDDL 能确定性表达 canonical graph 的可达性；
- 原始 VLM 观察仍然完整可审查。

## 职责边界

### VLM

VLM 只观察当前页面、按功能区域提出可直接执行的业务动作，并记录动作前后的可见变化。

`supporting_facts`、`candidate_added_facts` 和 `candidate_removed_facts` 在 Phase A 中全部属于观察证据。它们不参与节点身份、行为等价判断、target matching 硬约束或 PDDL 投影。

### Stagehand

Stagehand 只执行本地系统选中的业务动作，不决定状态身份、节点合并或 PDDL 语义。

### WebKobeGraph

节点表示整体业务行为状态，边表示：

```text
source behavior state
+ canonical business action
-> target behavior state
```

现有 `WebKobeNode.business_affordances` 表示节点首次观察到的动作集合。现有 `WebKobeEdge` 表示已观察转移。行为签名从 affordances 和 outgoing edges 动态计算，不新增 `action_signature`、`transition_signature` 或新的行为状态字段。

`PlanningState` 在 Phase A 中不承担节点身份或开放事实累积职责。未来进入混合方案 Phase C 后，再用于少量稳定的 canonical business facts。

## 探索与整理分离

### 探索阶段

探索期间保守记录 raw graph，不对未知节点做行为等价合并：

- 行为信息不完整时不合并；
- frontier 未全部执行时不合并；
- 存在执行失败候选时不合并；
- 已知 graph 路径上的 revisit 直接恢复原节点；
- 节点候选仍只在首次观察时生成一次，revisit 不追加。

动作执行成功但没有业务状态变化时，记录为明确自环。执行失败不等价于自环，也不能证明动作不可执行。

### 整理阶段

一次探索结束后，从 raw graph 确定性生成 canonical graph。raw graph 永久保留，canonical graph 供 PDDL projector 消费。

整理过程不修改原始 VLM 动作名称和观察证据。节点合并关系及原因写入独立整理报告，不增加 graph 节点字段。

## Canonical action 对齐

VLM 可能用不同名称表达相同业务意图，例如 `search_items`、`search_products` 和 `submit_search`。动作语义归一化只在探索后的整理阶段执行。

动作身份只表达业务意图；动作目标状态差异用于拆分 source 状态，不用于把相同业务意图判成不同动作。

本地 embedding 可以提出和自动接受高置信度同义动作，但采用精度优先策略：

- 综合原始 intent、label 和 target hint；
- 高置信度且不存在明显语义冲突时自动归一化；
- 中等置信度或有歧义时保持分离，并写入整理报告；
- embedding 不参与在线 frontier 或执行决策。

每个同义动作组使用最早出现的规范化 snake_case 名称作为 canonical action name。

## 行为等价整理

只有 frontier 完成、所有候选均获得明确结果且不存在执行失败的节点，才具备合并资格。

整理采用迭代分组：

1. 按 canonical action 集合形成初始分组；
2. 将每个动作的目标表示为目标节点当前所在分组；
3. 如果同组节点的 `action -> target group` 不同，则拆分该组；
4. 重复拆分，直到所有分组稳定。

该过程比较目标行为类别而不是原始 node ID，因此能够合并重复探索得到的同构状态，并能正确处理循环 graph。行为不完整或失败节点始终保持独立。

## 产物与可审查性

Phase A 保留三类产物：

```text
raw graph
  完整探索轨迹、原始动作名称、VLM facts 和执行证据

canonical graph
  canonical actions、行为等价节点和确定转移

consolidation report
  动作归一化、节点合并、拒绝合并和不确定项的原因
```

不通过新增大量 node/edge 字段表达整理过程。

## PDDL 投影

当前只生成 `domain.pddl`。projector 从 canonical graph 确定性投影：

- canonical 节点生成 `at_<state>` 谓词；
- 每条非自环转移生成独立 PDDL action；
- 同一 canonical action 出现在多个 source 状态时，使用 source state 后缀区分；
- action precondition 只包含 source location；
- action effect 删除 source location，并增加 target location；
- 自环不进入 PDDL；
- observation facts 和 `PlanningState.active_facts` 不进入 Phase A PDDL。

示例：

```lisp
(:action search_items__from_default_list
  :precondition (at_default_list)
  :effect (and
    (not (at_default_list))
    (at_search_results)))
```

## 失败与保守策略

- 动作语义不确定：不归一化；
- frontier 不完整：节点不合并；
- 候选执行失败：节点不合并；
- 行为证据冲突：拆分节点；
- 无可见业务变化但执行成功：记录自环；
- evidence 不足：保留 raw 节点，不猜测 canonical 等价关系。

整体原则是允许短期重复，不允许错误合并。

## 验收标准

1. raw graph 完整保留实际探索轨迹。
2. canonical graph 只合并 frontier 完成、无失败且行为完全等价的节点。
3. 高置信度同义业务动作能够归一化，不确定动作保持分离。
4. `supporting_facts` 和 visual delta 可审查，但不影响节点合并和 PDDL。
5. `PlanningState.active_facts` 不参与 Phase A 状态传播、target matching 硬冲突或 PDDL 投影。
6. `domain.pddl` 只表达 canonical 状态和非自环业务转移。
7. 当前搜索/清空循环能够收敛为两个可往返的业务状态，而不是因事实累积持续生成新状态。
8. canonical graph 和 `domain.pddl` 的节点、非自环边及动作可以一一追溯。

## 后续演进到 Phase C

Phase A 稳定后，再从反复解释动作可达性差异的观察中选择少量 canonical business facts。Phase C 在行为状态位置谓词之外增加这些 facts，用于增强 SafeSym 的业务语义和安全条件表达，但不推翻 Phase A 的 graph 骨架。
