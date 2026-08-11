# Explored Trace PDDL V1 设计

## 背景

当前 Location PDDL 只投影跨 Planning location 的已验证边。真实网站中的搜索、筛选、排序、加入购物车和打开弹窗经常不改变 URL，也可能没有被现有状态签名识别，因此成功动作会落成自环并从 PDDL 中消失。

第一版不再尝试判断页面语义等价性，也不等待更完整的 DOM 状态抽取。目标是尽快把已经成功执行的开放探索轨迹编译成 SafeSym 可解析、可求解、可回溯的 STRIPS 状态机。

## 目标

建立以下单向通路：

```text
开放式网站探索
  -> 成功业务动作与动作后观察
  -> 执行轨迹检查点
  -> Explored Trace PDDL
  -> 显式 start/goal 查询
  -> SafeSym / Fast Downward
```

PDDL 表达“如何重放已经成功探索过的动作路径”，不声称覆盖整个网站，也不声称理解购物车、筛选条件或用户权限等业务事实。

## 核心模型

### 检查点

每个成功业务动作事件连接两个检查点：动作执行前的 source checkpoint 和完成动作后观察后的 target checkpoint。

检查点不是页面位置，也不是完整世界状态。它只表示探索轨迹中的一个已记录执行阶段。URL 不变、DOM 未产生可用差异或页面仍在同一 SPA surface，都不阻止成功动作产生 target checkpoint。

失败动作保留在 Raw Graph 和证据产物中，但不生成可规划转换。

### 无类型 PDDL

第一版只使用 `:strips`，不声明 `:typing`、对象或常量。每个检查点编译成一个零参数 predicate：

```lisp
(:predicates
  (state-initial)
  (state-after-search-items)
  (state-after-apply-category-filter)
  (state-after-sort-by-price)
  (state-after-add-item-to-cart)
  (state-checkout-open)
)
```

每个 action 是 grounded action，没有参数。它删除 source predicate 并增加 target predicate：

```lisp
(:action apply-category-filter
  :parameters ()
  :precondition (state-after-search-items)
  :effect (and
    (not (state-after-search-items))
    (state-after-apply-category-filter)
  )
)
```

这种 one-hot checkpoint 语义避免 planner 同时处于多个轨迹阶段，也不需要推理 action 的业务前置条件和效果。

## 轨迹资格与顺序

一条探索事件进入 Trace PDDL 必须同时满足：

```text
execution_trace.success == true
AND status 不是 failed_execution
AND action identity 非空且可规范化
AND 动作后观察已经完成并有 after observation reference
```

第一版按 Raw Graph 中动作事件的记录顺序形成一条主轨迹。失败事件被跳过；成功事件依次连接前后 checkpoint。Raw Graph 原有 source/target 拓扑、Planning Abstraction 合并结果、URL、Visual Delta、embedding 和 DOM delta 都不决定 checkpoint 是否存在。

该顺序模型只承诺单次开放探索形成的一条已执行路线。分支、回溯、轨迹拼接和状态等价合并属于覆盖率与后续抽象工作，不进入 V1。

## 稳定命名

- 初始 predicate 固定为 `state-initial`。
- target predicate 使用 `state-after-<canonical-action>`；同名动作重复出现时追加基于 Raw edge identity 和轨迹位置的稳定短摘要。
- PDDL action 使用规范化 canonical action identity；重复 action 同样追加稳定短摘要，避免名称冲突。
- 名称不依赖 JSON 对象键顺序或文件遍历顺序；同一份冻结输入必须生成字节一致的 PDDL。
- 可读 label 不能替代稳定 identity。

## Domain、Problem 与报告

`domain.pddl` 是探索阶段主产物，只包含检查点 predicates 和合格的 grounded actions。

`problem.pddl` 只在探索产物冻结后、显式提供 start/goal checkpoint ID 时生成：

```lisp
(define (problem reach-checkout)
  (:domain explored-trace)
  (:init (state-initial))
  (:goal (state-checkout-open))
)
```

goal 必须在当前轨迹中从 start 向后可达；否则返回 `goal_unreachable_in_explored_trace`，不伪造 problem。

`projection_report.json` 记录：

- checkpoint predicate 到轨迹位置、Raw node/edge 和 after observation reference 的映射；
- PDDL action 到 Raw edge、原始 action identity 和 execution evidence 的映射；
- 被排除事件及 `failed_execution`、`missing_after_observation`、`invalid_action_identity` 等结构化原因；
- domain/problem 生成状态和 schema version。

DOM、截图、URL、页面标题和 Visual Delta 继续保留为审计证据，但不进入 V1 的 PDDL 判定。

## 与现有 Location PDDL 的关系

现有 Location PDDL compiler 和公开 API 保留为兼容路径，不删除、不改变其输出。新增独立的 Trace PDDL compiler，并让 Phase A 的推荐路径切换到 Trace V1；调用方仍可显式选择 Location V1 做页面级可达诊断。

探索器不接收 problem goal、SafeSym plan 或规划反馈。数据流继续严格保持：

```text
开放探索 -> Raw Graph -> Trace PDDL -> 事后规划查询
```

## 失败处理

- 没有任何成功事件：生成只含 `(state-initial)`、没有 action 的合法 domain。
- 成功事件缺少动作后观察引用：排除并报告，不补造 checkpoint。
- action identity 无法规范化：排除并报告。
- 重复名称：使用稳定摘要消歧。
- SafeSym parser、注入或 planner 失败：保留全部产物，并在 smoke report 中区分失败阶段。

## 验收标准

### PDDL 合法和可求解

- SafeSym 能解析无类型、零参数 predicate 的 domain/problem。
- Fast Downward 能对可达 start/goal 返回动作序列。
- 计划中每个 action 都能映射回一条成功 Raw edge 和动作后观察。
- 失败动作不会进入 domain。

### 实际网站短路线

在 `https://practiceautomatedtesting.com/shopping` 上进行无任务目标的短程探索，允许 URL 始终保持 `/shopping`。若探索实际成功执行了搜索、筛选、排序、加入购物车和打开结算，则输出至少六个 checkpoint，并能对首尾 checkpoint 求得对应动作序列。

验收只要求规划已经探索到的内容，不要求系统发现所有功能，也不要求证明这些动作是到达目标的最短业务流程。

### 泛化性

- compiler 不包含 search、filter、cart、checkout、login 等领域名称规则。
- 电商、文档或会议类 Raw Graph 使用同一个资格判断、命名和 PDDL schema。
- 不提供 DOM sidecar、截图、embedding 或 Visual Delta 时仍能生成相同 Trace PDDL。

## 有意接受的限制

- backend 误报成功的 no-op 可能成为 checkpoint；V1 优先打通轨迹规划，通过 provenance 暴露风险。
- checkpoint 表示动作历史阶段，不能作为完整业务世界状态解释。
- V1 不合并不同路线中语义等价的状态。
- V1 不支持从任意业务目标自动推导 goal predicate；start/goal 由已探索 checkpoint 显式选择。
- 覆盖率、frontier 回溯和多分支探索是独立后续目标，不阻塞本设计。
