# Generalized Location PDDL V1 设计

## 背景

项目需要同时完成三个目标：

1. 能在未知网站上探索并发现基本功能；
2. 能生成合法、可由 SafeSym 解析和求解的 PDDL；
3. 不把电商、登录、搜索等具体领域知识硬编码进通用 pipeline。

AutoExploration 的 FSM 示例证明了一条足够简单的可行路径：把状态看作图节点，把动作看作图边，使用统一的
`location` 类型和 `(at ?location)` 谓词表达可达性。当前 Web-KOBE 已经具备真实浏览器执行、Raw Graph、
Planning Abstraction、Planning Graph 和 PDDL projector，因此本设计改造现有主线，不建立第二套探索系统。

## 目标

建立一条可尽快验收的通路：

```text
未知网站
  -> 无任务目标的有界探索，发现当前路线上的基本业务功能
  -> Raw Graph 保存真实观察和执行证据
  -> Planning Graph 表达可规划 location 和已验证转换
  -> Location PDDL V1
  -> SafeSym 解析并求解显式 start/goal 问题
```

第一版只解决 location-level reachability。它不要求理解网站的完整业务状态，也不要求把
`cart_has_items`、`logged_in` 等事实写入 PDDL。

这里的“一条主要路线”是探索过程自主形成的路线，不是用户任务、goal location 或预设典型流程导向的路线。
探索阶段不知道之后会用哪个 start/goal 做规划验证。

## 非目标

- 不宣称 forward-only 探索已经覆盖整个网站。
- 不从一次探索自动猜测用户任务或 goal。
- 不把规划查询、目标页面、业务任务或 profile stage 反馈给探索器做动作选择。
- 不把探索退化为“为了到达指定 goal 而执行网页任务”。
- 不让 VLM、embedding、Visual Delta 或 Stagehand 直接生成 PDDL。
- 不在 projector 中按 `search`、`filter`、`checkout` 等动作名称编写领域规则。
- 不在 V1 中解决业务 facts 的晋升、安全语义或完整 problem 自动生成。
- 不要求 Raw observation 与 Planning location 一一对应。

## 设计原则

### 1. 泛化来自稳定元模型，而不是领域词表

所有网站共享同一 PDDL schema：

```lisp
(:types location)
(:predicates (at ?location - location))
```

具体网站只提供数据：location、动作名称和转换拓扑。projector 不解释这些名称的业务含义。

### 2. 探索、抽象和投影分别负责一种判断

- 探索层判断“当前可尝试什么”，并执行一个选中的业务动作。
- Raw Graph 判断“动作前后实际观察到了什么”。
- Planning Abstraction 判断“这些观察是否属于同一可规划 location”。
- projector 只把已经确定的 Planning Graph 机械编译为 PDDL。

### 3. 探索与任务规划单向隔离

数据只允许沿以下方向流动：

```text
开放式探索 -> Planning Graph -> PDDL -> 显式规划查询
```

规划查询的 start、goal 和求解结果不得反向进入候选生成、候选排序或 Stagehand prompt。这样生成的图表示系统
实际探索到的网站能力，而不是某个任务所需路径的记录。

### 4. 保守但不中断

证据不足的 edge 不进入 PDDL，但不阻止生成其余合法 domain。只有一个 location 时也可以生成没有动作的合法
domain，不能为了让 planner 有路可走而虚构转换。

### 5. Location V1 是永久可用的基础层

未来可以增加 Semantic PDDL V2，但不得破坏 V1。事实识别失败时，系统仍能降级为 location graph 规划。

## 总体架构

### 探索层：发现基本功能

沿用当前 Web-KOBE bounded exploration：

```text
观察当前页面
  -> VLM 提出少量当前可见的业务动作候选
  -> 本地 frontier/memory 选择一个未尝试候选
  -> 每步调用一次 Stagehand 执行整个业务动作
  -> 等待动作后观察
  -> 写入 Raw Graph 和 checkpoint
```

“基本功能”不使用固定 action family 定义。VLM 根据当前 active surface 提出用户可直接执行、具有可见结果的
业务动作；本地系统只做数量限制、稳定身份、尝试状态和局部语义去重。电商可以发现商品、购物车和结账动作，
文档系统可以发现打开、编辑和共享动作，而通用代码无需增加领域分支。

候选选择以探索价值为准：优先当前 Planning/Raw node 中尚未尝试的可见业务动作，并减少局部语义重复；不能
因为某个动作更接近后来设置的 goal 而优先它。V1 接受 forward-only 的局部覆盖：至少自主形成一条包含多个
已验证 location/transition 的路线，并保存未尝试候选用于审计。replay、browser back 和全站覆盖不阻塞本阶段。

### Raw Graph：观察真相

Raw Graph 继续保存稳定可见观察、业务动作执行结果和证据。页面局部变化可以产生新的 Raw node，即使这些观察
最终属于同一个 Planning location。`graph_evidence.json` 仍是可选诊断 sidecar，不是 PDDL 输入。

### Planning Graph：唯一的 PDDL 语义输入

Planning Graph 输出领域无关的最小契约：

```json
{
  "locations": [
    {"id": "planning_001", "label": "document_list"}
  ],
  "transitions": [
    {
      "id": "transition_001",
      "source": "planning_001",
      "target": "planning_002",
      "action": "open_document",
      "status": "verified",
      "raw_edge_ids": ["raw_edge_008"]
    }
  ]
}
```

这里的名称只是数据，不是 projector 的判断依据。Planning Graph 必须保留精确 Raw edge provenance。

### Location PDDL projector：确定性编译

projector 只认识：

- location ID 和可选 label；
- transition ID；
- source 和 target；
- 稳定 action identity；
- verified 状态和 provenance。

一条 transition 进入 domain 的充分必要条件是：

```text
status 是可投影的已验证成功
AND source location 存在
AND target location 存在
AND source != target
AND action identity 非空且可规范化
```

它不按 action 名称、网站类型、profile、Visual Delta 分类或 business fact 做特判。自环自然留在 Planning Graph
中而不进入 Location PDDL。

## PDDL 格式

### Domain

```lisp
(define (domain explored_site)
  (:requirements :strips :typing)

  (:types location)

  (:constants
    home product_list product_details - location
  )

  (:predicates
    (at ?location - location)
  )

  (:action open_product_details
    :parameters ()
    :precondition (and (at product_list))
    :effect (and
      (not (at product_list))
      (at product_details)
    )
  )
)
```

domain 名称、location 名称和 action 名称都由稳定 ID 确定性规范化。label 只改善可读性，不能改变 identity。
发生名称冲突时使用稳定 ID 摘要，不使用依赖遍历顺序的 `_002`。

### Problem

problem 由显式 planning node ID 参数生成：

```json
{
  "start_location_id": "planning_001",
  "goal_location_id": "planning_004"
}
```

```lisp
(define (problem reach_goal)
  (:domain explored_site)
  (:init (at home))
  (:goal (at checkout))
)
```

start 和 goal 必须存在，且 goal 必须在当前 Planning Graph 中从 start 结构可达。不可达时返回
`goal_unreachable`，不伪造 problem。start/goal 只能在探索产物冻结后选择；它们不允许反向影响探索轨迹。
探索主产物仍以 domain 为主；problem 只用于事后的显式规划查询和验收。

## 代码结构方向

保留现有探索和 Planning Abstraction。当前 `web_kobe_pddl_projector.py` 同时承担 JSON 兼容读取、历史 facts
投影、domain/problem 生成和 smoke 辅助，职责过多。实现阶段应做一次有边界的整理：

1. 保留现有 graph loader 和公开 CLI 入口；
2. 提取一个小型、纯函数式 Location PDDL compiler，输入只包含 Planning Graph；
3. 让当前 Phase A domain 路径调用该 compiler；
4. 旧 fact-rich/problem 能力只保留为明确的兼容或诊断路径，不再决定 Phase A；
5. 不复制 exploration、graph 或 planning abstraction 数据结构。

具体文件拆分在实施计划中根据现有测试耦合决定。本设计不要求为了形式新建大量模块。

## 产物

一次可规划导出包含：

```text
planning_graph.json
planning_abstraction_report.json
domain.pddl
projection_report.json
problem.pddl                 # 仅在显式提供 start/goal 时
safesym_smoke.json           # 验收或诊断运行时
```

`projection_report.json` 记录：

- PDDL location 到 Planning node ID 的映射；
- PDDL action 到 Planning edge/Raw edge 的映射；
- 被排除 edge 及结构化原因；
- domain/problem 生成状态。

SafeSym 只依赖 PDDL。审查工具通过 report 回溯证据。

## 失败处理

- 没有 location：拒绝生成并报告 `no_planning_locations`。
- 只有 location、没有合格 transition：生成合法空动作 domain。
- self-loop：排除并报告 `planning_self_loop`。
- candidate-only、failed 或 no-op edge：排除并报告对应状态。
- 缺失 source/target：排除并报告 `missing_location_reference`。
- action identity 无法规范化：排除并报告 `invalid_action_identity`。
- 名称冲突：加入稳定 ID 摘要并记录映射。
- sidecar 缺失：不影响投影。
- SafeSym parse 或 planner 失败：保留全部产物，明确区分 parser、problem consistency 和 planner 失败。

## 验收标准

### 目标一：能够探索网站

- 在至少两个不同类型的网站或 fixture 上运行相同探索 pipeline，无领域专用 selector/policy 分支。
- 探索输入不包含任务描述、目标页面、goal location 或预设业务流程。
- 每步最多执行一个 VLM 选出的业务动作，Stagehand 每步只调用一次。
- 每个完成动作都有动作后观察和 checkpoint。
- 每个实验至少自主发现并验证一条基本功能路线；路线不是为完成规划查询而预先指定，且不等于全站覆盖。

### 目标二：生成 SafeSym 可求解的 PDDL

- SafeSym parser 能读取生成的 domain 和显式 problem。
- SafeSym 使用当前 planner 对一个可达 start/goal 返回动作序列。
- 计划中的每个 action 都能映射回 Planning edge 和 Raw evidence。
- self-loop、失败和未验证候选不进入 domain。

### 目标三：具有泛化性

- 用电商、文档系统和会议系统三种合成 Planning Graph 运行同一个 compiler，不修改代码或配置领域规则。
- projector 源码不包含领域 action/page 名称白名单或黑名单。
- 同一 Planning Graph 在节点/边输入顺序变化后生成字节一致的 PDDL。
- 删除 `graph_evidence.json` 后仍可生成相同 PDDL。
- 新网站只改变 graph 数据，不改变 PDDL schema 和投影算法。

## 自我审查结论

### 与三个目标的对应关系

- 探索目标由现有 Web-KOBE 闭环承担，本设计没有用 PDDL 简化反向削弱真实探索证据。
- 探索和任务规划保持单向隔离；事后 start/goal 查询不参与网页动作选择。
- 可求解目标不仅要求 parser 通过，还要求显式 start/goal problem 能由 SafeSym planner 找到路径。
- 泛化目标通过统一 `location + at` 元模型、Planning Graph 契约和禁止领域名称分支实现。

### 有意接受的限制

- Location V1 只能回答“如何到达某个 location”，不能表达购物车内容、权限或表单字段等丰富状态。
- Planning Graph 的合并质量仍决定 domain 质量；projector 不修复上游语义错误。
- forward-only 探索只能建立局部可达图。
- 第一版只沿自主形成的当前路线前进，尚不能系统地返回历史 frontier 扩展其他分支。

这些限制不会阻止三个近期目标：系统仍能探索基本功能、生成合法可求解 PDDL，并在不同网站上复用同一通路。
后续 Semantic PDDL 应作为独立增强设计，而不是扩大本次范围。

## 实施边界

本设计批准后，实施计划应按以下顺序展开：

1. 用测试固定通用 Location PDDL 格式、确定性和排除规则；
2. 整理/提取现有 Phase A projector，保持现有 CLI 入口兼容；
3. 增加显式 start/goal problem 生成和 projection report；
4. 增加回归测试，证明 task/goal 不进入探索候选、排序或 Stagehand prompt；
5. 用 SafeSym parser 与 planner 做真实跨项目验收；
6. 用多个领域无关 fixture 验证泛化；
7. 最后再运行一次无任务目标的真实网站短探索，不在同一轮顺手修改 Planning Abstraction 或 Visual Delta。
