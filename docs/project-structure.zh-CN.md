# 项目结构

这份文档记录当前 active code 的结构、pipeline、模块职责和主要函数。英文版
`docs/project-structure.md` 用于 AI/代码接力；中文版用于人工审阅。项目结构变化时，两份文档需要同步更新。

## 当前主线

项目当前围绕 SafeSym-oriented Web-KOBE 主线展开：

```text
真实浏览器操作
  -> 观察与状态解释
  -> WebKobeGraph 记忆
  -> bounded forward-only exploration 策略
  -> PDDL 投影
  -> SafeSym smoke / 安全验证
```

旧 upstream `explore` runtime 和旧 `WebObservedGraph` 探索栈已经不属于 active code path。

## 分层结构

你说的“操作层、观察层、PDDL 映射层”是对的，但为了让结构更清楚，我建议当前按 6 层理解：

```text
操作层
观察与状态层
图与记忆层
探索策略层
PDDL 映射与 SafeSym bridge 层
实验运行层
```

### 操作层

负责浏览器执行和底层交互。

主要模块：

- `src/ai_web_explorer/grounded_web/automation_backend.py`
- `src/ai_web_explorer/grounded_web/playwright_backend.py`
- `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
- `src/ai_web_explorer/grounded_web/stagehand_prompt.py`

主要职责：

- 观察浏览器状态；
- 列出可执行的底层动作或 Stagehand-observed actions；
- 执行一个已选择动作；
- 截图；
- 保存底层 execution trace。

Stagehand 属于这一层。它可以看页面、生成候选、执行动作，但不应该决定 graph identity、planning facts 或 PDDL 语义。

主要函数/类：

- `AutomationBackend.observe_state`
- `AutomationBackend.list_interactables`
- `AutomationBackend.execute`
- `AutomationBackend.capture_screenshot`
- `WebKobePlaywrightAdapter`
- `StagehandAutomationBackend`
- `create_async_stagehand_provider_from_env`
- `build_generic_stagehand_exploration_goal`

### 观察与状态层

负责页面状态抽取、视觉变化比较和候选业务 facts。

主要模块：

- `src/ai_web_explorer/grounded_web/state_signature.py`
- `src/ai_web_explorer/grounded_web/state_facts.py`
- `src/ai_web_explorer/grounded_web/state_summary.py`
- `src/ai_web_explorer/grounded_web/semantic_assistor.py`
- `src/ai_web_explorer/grounded_web/business_profile.py`
- `src/ai_web_explorer/grounded_web/business_affordance.py`
- `src/ai_web_explorer/grounded_web/visual_delta.py`
- `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`

主要职责：

- 构造确定性的 state snapshot 和 signature；
- 为人工审查和 embedding 生成 state summary；
- 让 VLM 总结当前页面可执行的业务候选动作；
- 只比较 before/after 截图并输出 `candidate_added_facts` / `candidate_removed_facts`；
- 由本地结构化 verifier 生成 `PlanningDelta` 和 evidence；历史 `BusinessTransition` 仅保留兼容读取；
- 提供轻量结构化 verifier。

profile facts 位于这一层。它们的定位是“优先观察目标 + PDDL 候选谓词词表”，不是网页所有可能状态的全集。Visual Delta VLM 只接收动作和 before/after 截图，不接收 profile facts、supporting facts 或规划状态；它输出的观察事实只作为 raw edge trace 证据保留，不进入 `PlanningState`。只有本地结构化 verifier 明确确认的事实才归入 profile facts。节点可使用 Visual Affordance 提供的可选技术性 state label；profile facts 不再派生节点 label。

主要函数/类：

- `StateSnapshot`
- `DeterministicSemanticAssistor.describe_state`
- `ecommerce_checkout_profile`
- `summarize_visual_affordances`
- `summarize_visual_delta`
- `create_openai_visual_delta_provider_from_env`
- `verify_planning_delta`
- `build_state_summary`

### 图与记忆层

负责 active semantic graph 和状态记忆。

主要模块：

- `src/ai_web_explorer/grounded_web/graph.py`
- `src/ai_web_explorer/grounded_web/graph_manager.py`
- `src/ai_web_explorer/grounded_web/planning_abstraction.py`
- `src/ai_web_explorer/grounded_web/state_embedding.py`
- `src/ai_web_explorer/grounded_web/embedding_provider.py`
- `src/ai_web_explorer/grounded_web/exploration_index.py`

主要职责：

- 定义 `WebKobeGraph`、`WebKobeNode`、`WebKobeEdge`；
- 记录 `BusinessAffordance`、`PlanningDelta`、`PlanningState`、`PlanningTransition`，并兼容读取历史 `BusinessTransition`；
- 明确可见变化先保留为独立 raw observation，避免 embedding 提前覆盖；
- 离线把 presentation-equivalent observations 保守归入 planning groups，并聚合实际观察到的能力及来源；
- 传播 source-aware planning state；
- 在 `PlanningState` 中同时保留 `active_facts`、`profile_fact_ids` 和 `generated_fact_ids`；
- 将 Visual Delta 观察事实写入 raw edge 的 `execution_trace.metadata.visual_delta_trace`，不参与 planning transition、target matching planning facts 或 Phase A PDDL；
- 存储 state embeddings；
- 判断 revisit，并给探索策略提供 memory context；明确 URL path、结构签名或 Visual Delta 变化时，不将候选目标合并回本次 source，但仍可复用有可靠证据的其他历史节点。
- 在当前节点或可靠匹配的历史节点上下文内，使用 exact/embedding 相似度避免重复业务动作；不做全局动作屏蔽。

embedding memory 只辅助定位和避免重复，不直接进入 PDDL。

主要函数/类：

- `WebKobeGraph`
- `WebKobeNode`
- `WebKobeEdge`
- `WebKobeGraphManager.identify_or_add_node`
- `WebKobeGraphManager.build_planning_transition`
- `WebKobeGraphManager.apply_planning_transition`
- `WebKobeExplorer._avoid_incompatible_existing_target_state`，用于避免同页面壳但 planning facts 不兼容时污染已有节点。
- `find_best_state_match`
- `build_exploration_context`

### 探索策略层

负责 step loop 和动作选择。

主要模块：

- `src/ai_web_explorer/grounded_web/explorer.py`
- `src/ai_web_explorer/grounded_web/controller.py`

主要职责：

- 执行一轮 exploration step；
- 从观察层生成的 business affordances 中选择一个业务动作；
- 使用 memory context 和重复惩罚；
- 调用 Stagehand 操作层和 VLM/DOM 观察层；
- 更新 graph；
- 按 step budget 或 terminal condition 停止。
- 当前节点候选耗尽时以 `current_state_exhausted` 停止，不执行 browser back；连续没有新 graph information 时累计无进展。真实 Stagehand runner 暂时关闭连续无进展提前终止，主要受最大步数约束。
- 每个完成动作后更新 latest checkpoint（embedding、Stagehand trace、graph/evidence），正常完成后再写一次；最终 `graph.meta.exploration_summary` 记录 `requested_steps`、`steps_completed` 和 `stop_reason`。checkpoint 不提供 resume、replay、browser-back recovery 或逐步历史版本。

低层 DOM interactables 可以继续作为运行时 state summary / embedding matching 的辅助输入，但不再输出到 canonical `graph.json` node，也不作为 graph memory 或探索决策单位。旧的 LLM action selector 路径已经移除，避免系统回退到 selector/locator 驱动的探索。

`WebKobeExplorer` 目前是最大的协调类。后续新增探索策略时，应尽量拆成小组件，不要继续把所有逻辑堆进 `explore_one_step`。

主要函数/类：

- `WebKobeExplorer.explore_one_step`
- `WebKobeExplorer._select_action`
- `WebKobeExplorer._select_business_affordance_action`
- `WebKobeExplorer._match_current_state`
- `WebKobeExplorer._record_source_business_affordances`
- `WebKobeExplorationController.run`

### PDDL 映射与 SafeSym Bridge 层

负责 planner-facing 投影和验证。

主要模块：

- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py`
- `src/ai_web_explorer/safesym_bridge/cli.py`

主要职责：

- 读取 `WebKobeGraph` JSON；
- 把 graph location、profile facts、planning transitions 投影为 PDDL；
- 写出 domain/problem；
- 运行 PDDL readiness smoke；
- 运行 SafeSym parser、safety injection、planner smoke。

这一层应保持确定性。它应该消费 graph 中已经记录的语义，不应该直接调用 LLM/VLM。Phase A 先由 `planning_abstraction.py` 生成 planning graph，再只投影跨 planning-state 的成功转换；presentation 自环保留在 planning graph 中用于审计和能力发现，但不进入 PDDL。失败或缺失目标的边仍被排除。Visual Delta 观察事实、supporting facts 和 `PlanningState` 不作为 Phase A 的 predicates、preconditions 或 effects。

主要函数/类：

- `load_web_kobe_graph_json`
- `compile_web_kobe_graph_to_domain`
- `compile_web_kobe_graph_to_pddl`
- `write_web_kobe_pddl_smoke`
- `write_web_kobe_safesym_smoke`
- `main`

graph artifact 的布局由 `src/ai_web_explorer/safesym_bridge/graph_artifacts.py` 负责：`graph.json` 是可独立加载的紧凑主图，`graph_evidence.json` 是可选诊断 sidecar。`evidence_ref` 解析到 sidecar 中稳定的 node/edge key；历史完整 graph 继续兼容读取。Phase A 只消费 graph，不读取 sidecar，`raw_graph.json` 保留输入文件的原始 JSON 形状，因此 sidecar 证据不会被重新膨胀，也不参与 PDDL。该 artifact 拆分不改变探索、状态命名、matching 或 Phase A 语义。

### 实验运行层

负责 CLI-facing 的实验编排。

主要模块：

- `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- `src/ai_web_explorer/grounded_web/experiment_plan.py`

主要职责：

- 启动 Playwright；
- 配置 Stagehand；
- 配置 VLM 和 embedding provider；
- 注入 benchmark/test context；
- 写出 graph、trace、screenshots、embedding、PDDL、smoke outputs。
- generic `run_stagehand_exploration` 在每个完成动作后按 embedding、Stagehand trace、graph/evidence 的顺序写入 checkpoint，并在正常结束时写入带 `exploration_summary` 的最终 artifact；graph/evidence 是最后提交的配对标记。

这一层是工程 glue。它不应该成为 graph 语义或 planning 语义的来源。

主要函数/类：

- `run_web_kobe_exploration`
- `run_stagehand_exploration`
- `run_ecommerce_stagehand_step`
- `write_web_kobe_graph`
- `ecommerce_checkout_experiment_plan`

## 当前推荐命令

```text
web-kobe-explore
web-kobe-stagehand-explore
web-kobe-ecommerce-stagehand-smoke
web-kobe-domain-from-graph
web-kobe-pddl-from-graph
web-kobe-pddl-smoke
web-kobe-safesym-smoke
```

Debug helpers：

```text
web-kobe-graph
web-kobe-pddl
```

## 关键数据流

```text
WebKobeExplorer.explore_one_step
  -> adapter.observe_state
  -> adapter.list_interactables
  -> SemanticAssistor.describe_state
  -> GraphManager.identify_or_add_node
  -> optional embedding source match
  -> optional summarize_visual_affordances
  -> select business action
  -> adapter.execute
  -> capture after state/screenshots when execution succeeds or the known Stagehand tool_choice error is reported
  -> summarize_visual_delta (observation trace only) / verify_planning_delta
  -> GraphManager.build_planning_transition
  -> GraphManager.add_edge
  -> controller 调用可选的完成步骤 checkpoint
  -> 真实 runner 依次写入 embedding、Stagehand trace、graph/evidence
  -> 正常结束时写入 `graph.meta.exploration_summary`
  -> planning abstraction groups raw observations and aggregates capabilities
  -> Phase A projector consumes planning graph
```

对 `Thinking mode does not support this tool_choice`，探索器会继续动作后观察：有 URL path、结构签名或 Visual Delta 变化时记录成功转换，无变化时记录 `no_observed_change` 自环，并保留原始错误与 `backend_reported_success=false`。未知执行错误仍记录失败自环且跳过 Visual Delta。

## 相关文档

```text
docs/current-project-overview.md
docs/current-project-overview.zh-CN.md
  当前项目方向和问题。

docs/project-decisions.zh-CN.md
  项目决策记录。每次做有意义的架构、pipeline、数据结构调整后都要更新。

docs/project-structure.md
docs/project-structure.zh-CN.md
  当前 pipeline、模块边界和主要函数。

docs/safesym-bridge.md
  SafeSym bridge 命令和实验使用说明。
```
