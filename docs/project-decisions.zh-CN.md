# 项目决策记录

这份文档记录项目中的关键调整：改了什么、为什么改、影响范围是什么。后续每次做架构、pipeline、数据结构、实验策略或主线清理时，都应该追加一条简短记录。

记录格式：

```text
## YYYY-MM-DD - 决策标题

更改：
- ...

原因：
- ...

影响：
- ...
```

## 2026-07-31 - 将业务节点命名 hint 放回 profile

更改：

- `PlanningFactSpec` 新增 `state_label_hint`，由具体 business profile 为 planning fact 声明推荐节点 label。
- `business_state_policy.resolve_business_target_node` 改为接收 `state_label_hints`，不再硬编码 ecommerce facts。
- `WebKobeExplorer` 从当前 `BusinessFlowProfile` 提取 hints 后传给 graph policy。

原因：

- profile facts 会根据网站类型变化，通用 graph policy 不应该认识 `cart_page_visible`、`checkout_started` 等具体业务事实。
- 节点是否 materialize 属于 graph policy；具体 fact 应该怎么命名属于 profile 语义。
- 这样后续新增非电商 profile 时，不需要修改通用 graph policy。

影响：

- PDDL 可读性仍可通过 `node_label` 改善，但命名知识从通用层移回 profile 层。
- 不同网站类型可以定义自己的 state label hints。
- 没有 hint 的 generated/profile facts 仍使用通用后缀规则或 business action fallback。

## 2026-07-31 - 业务节点命名前移到 graph policy

更改：

- `business_state_policy.resolve_business_target_node` 在 materialize 业务节点时，会根据 `planning_transition.added_facts` / `post_facts` 和 `business_transition.action_name` 生成更可读的 `node_label`。
- 业务节点的 `node_id` 前缀同步使用该语义 label，例如 `cart_with_items__business_*`，而不是退回 `shopping__business_*`。
- PDDL projector 仍只读取 graph 中已有的 `node_label`，不直接调用 LLM/VLM，也不自行猜测网页含义。

原因：

- PDDL 可读性问题主要来自 graph 语义名不足，而不是 projector 缺少后处理。
- 如果把命名逻辑放到 PDDL projector，会让 planner-facing 投影层承担语义解释职责，增加耦合。
- 业务状态是否 materialize 本来就在 graph policy 中判断，因此在这里补充业务节点 label 更自然。

影响：

- 同页业务变化生成的新节点更容易读，PDDL location predicate 也会随之更清楚。
- `node_label` 继续只服务可读性和投影命名，不承担节点唯一身份；唯一身份仍由 `node_id` 负责。
- 仍需后续处理非 materialized 节点、重复 label 和 action naming 的整体可读性。

## 2026-07-31 - 让 graph 记录 generated facts，PDDL 默认保守投影

更改：

- `PlanningState` 新增 `profile_fact_ids` 和 `generated_fact_ids`，用于记录 active facts 的来源。
- `WebKobeGraphManager` 不再用 profile facts 硬过滤 `planning_transition`，而是允许 profile facts 和 generated facts 一起进入 graph 状态。
- `web_kobe_pddl_projector` 默认只投影 profile facts；generated facts 默认留在 graph 中，不进入 PDDL。
- `PddlProjectionOptions` 预留 `include_generated_planning_facts` 开关，供后续实验或晋升策略使用。

原因：

- 开放网页探索会遇到 profile 未覆盖的新业务状态，如果 graph 层丢弃这些状态，会损害探索记忆和人工分析。
- SafeSym 消费的是 planner-facing PDDL，不能让未审核的 VLM-generated facts 默认进入谓词集合。
- 因此需要把“记录事实”和“投影事实”分开：graph 可以更开放，PDDL 默认更保守。

影响：

- 实验 graph JSON 会更完整地保存 profile/generated 两类 facts。
- PDDL 默认输出更稳定，不会因为 VLM 新造 fact 直接漂移。
- 后续仍需要设计 generated facts 的晋升、验证和显式投影策略。

## 2026-07-31 - 建立项目决策记录和项目结构文档

更改：

- 新增 `docs/project-decisions.zh-CN.md`，作为长期维护的项目决策记录。
- 新增 `docs/project-structure.zh-CN.md`，记录中文项目结构、pipeline、模块职责和主要函数。
- 重写 `docs/project-structure.md`，让英文版与当前 Web-KOBE/SafeSym 主线同步。

原因：

- 当前项目方向多次调整，如果只靠对话记忆，后续容易忘记为什么做某个结构选择。
- 项目需要明确分层，避免操作层、观察层、图记忆层、探索策略层和 PDDL 映射层互相污染。
- 后续每次清理或调整数据结构时，需要留下低成本、可审查的决策痕迹。

影响：

- 后续有意义的架构或 pipeline 调整，都应追加本文件。
- `docs/project-structure.md` 和 `docs/project-structure.zh-CN.md` 应作为当前结构事实来源。

## 2026-07-31 - 收窄 current-project-overview 的职责

更改：

- 将 `docs/current-project-overview.md` 和 `docs/current-project-overview.zh-CN.md` 调整为高层接力文档。
- 将详细 pipeline、模块职责和主要函数放入 `docs/project-structure.md` / `docs/project-structure.zh-CN.md`。
- 将“为什么做这个调整”记录在本决策文件中。

原因：

- overview 原本已经承担项目方向、当前问题和下一步优先级的职责。
- 如果再把完整模块结构、pipeline 和决策原因都放进 overview，会造成重复维护和信息漂移。
- 三份文档需要分工清楚：overview 讲“现在在哪”，structure 讲“系统怎么组织”，decisions 讲“为什么这么改”。

影响：

- 后续更新项目方向时优先改 overview。
- 后续更新模块边界或主函数时优先改 project structure。
- 后续做架构或数据结构调整时追加 decision record。

## 2026-07-31 - 删除旧 WebObservedGraph 探索栈

更改：

- 删除旧探索栈源码：
  - `src/ai_web_explorer/safesym_bridge/action_catalog.py`
  - `src/ai_web_explorer/safesym_bridge/effect_inferer.py`
  - `src/ai_web_explorer/safesym_bridge/graph_explorer.py`
  - `src/ai_web_explorer/safesym_bridge/observed_graph.py`
  - `src/ai_web_explorer/safesym_bridge/semantic_resolver.py`
- 删除旧测试：
  - `tests/safesym_bridge/test_semantic_resolver.py`
- 更新 `docs/safesym-bridge.md`，说明旧 `WebObservedGraph` 只作为历史设计存在，不再保留 active source。

原因：

- 当前 CLI 和实验主链路已经使用 `WebKobeGraph`、`WebKobeExplorer`、`WebKobeGraphManager`。
- 旧 `WebObservedGraph` 栈不再被主链路调用，继续留在 `safesym_bridge` 源码主目录会误导后续开发。
- 旧栈包含 SauceDemo 风格 precondition 和旧探索模型，容易让项目重新偏向历史路线。

影响：

- active code path 更清楚：探索图统一使用 `WebKobeGraph`。
- 历史设计仍可从 `docs/superpowers/` 的旧 spec/plan 中查阅。
- 验证结果：`pytest -q` 通过，`243 passed, 2 skipped`。

## 2026-07-31 - 明确 profile facts 的新定位

更改：

- 在项目 overview 和结构文档中明确：profile facts 不应再被理解为网页状态全集。
- profile facts 的定位调整为：

```text
PDDL 候选谓词词表 + 优先观察目标 + 跨网站语义对齐锚点
```

原因：

- 开放网页探索会遇到 profile 没覆盖的新状态。
- 如果 profile facts 继续作为 graph state 硬白名单，VLM 发现的 generated facts 很难进入图记忆。
- 但完全放弃 profile facts 会导致 PDDL 谓词漂移，SafeSym 难以稳定消费。

影响：

- Graph 层应允许记录 profile facts 和 generated facts。
- PDDL 层默认仍保守消费 profile facts。
- 后续需要设计 generated facts 的记录、晋升和投影策略。

## 2026-07-31 - 初次整理 current project overview

更改：

- 重写 `docs/current-project-overview.md` 和 `docs/current-project-overview.zh-CN.md`。
- 初步明确当前方向、pipeline、核心结构职责、主要问题和下一阶段优先级。

原因：

- 原文档包含较多历史实验叙述，主线和问题优先级不够聚焦。
- 项目已经从 task-guided checkout baseline 转向 bounded exploration V1。

影响：

- 该整理后来被“收窄 current-project-overview 的职责”决策修正。
- 当前分工是：overview 只保留高层项目状态；结构细节归 `docs/project-structure.md` 和 `docs/project-structure.zh-CN.md`。
