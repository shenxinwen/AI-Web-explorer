# 项目结构

这份文档记录当前 active code 的结构、pipeline、模块职责和主要函数。英文版
`docs/project-structure.md` 用于 AI/代码接力；中文版用于人工审阅。项目结构变化时，两份文档需要同步更新。

## 当前主线

项目当前围绕 SafeSym-oriented、location-scoped 开放探索主线展开：

```text
浏览器观察 + VLM initial scan
  -> LocationExplorationMemory 保存动作及同位置 requires
  -> 本地选择前提已成功的未完成 (location, action)
  -> Stagehand 执行一个动作
  -> screenshot 动作后观察 outcome/location_change/evidence
  -> 记录位置限定完成 fact 和可选 semantic location transition
  -> 新 location 触发新的 initial scan
  -> frontier 耗尽时 reset + stored-action replay
  -> checkpoint 保存 graph、location memory 和累计预算
  -> SemanticPlanningGraph
  -> Minimal Semantic domain.pddl + problem.pddl
  -> SafeSym parse / solve
```

当前探索器仍然沿浏览器当前路径前向执行，但不再在当前路径耗尽后直接结束：controller
可以选择其他可恢复 frontier，通过重放保存的动作路径回到断点继续探索。重放只负责恢复，
不得修改图、候选池、planning facts、扫描状态和动作尝试次数。

VLM 输出的是候选假设，Stagehand 报告的是执行尝试，动作后观察才是验证证据。
同一位置内成功动作只执行一次并解锁明确依赖它的动作；同页继承原候选池，新位置只扫描一次。
active path 不做 targeted/supplement scan，旧机制仅作为兼容代码保留。

planner-facing 主线现在是 `SemanticPlanningGraph -> Minimal Semantic PDDL`，同时生成
`domain.pddl` 和 `problem.pddl`。旧 Planning Graph / Phase A、Location PDDL 和其他 projector
仍作为兼容或历史路径存在，但不再代表当前语义验收标准。

当前框架并非完全无硬编码。`practice_shopping_feasibility` profile、购物车结构化事实捷径、
CLI profile 注册和受控下单 URL 仍是显式领域/实验配置。后续优先把
`cart_count -> cart_has_items` 等映射迁入可配置 profile；PDDL 编译器、候选池、重放和
controller 本身不按购物动作或位置名称分支。

旧兼容路径仍可把 profile 传入 Visual Affordance；location-scoped active path 已改用不含
profile 答案的最小动作依赖响应和最小动作后观察响应。旧 profile/Visual Delta 路径仍保留。

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
- 收集低层 interactables，作为 state summary、embedding 或执行证据的辅助输入；
- 执行一个已选择动作；
- 截图；
- 保存底层 execution trace。

Stagehand 属于这一层，是执行后端。业务动作候选由观察/探索流程生成和选择；低层
interactables 不作为探索候选、memory/frontier 单位，也不恢复 selector/locator fallback。
Stagehand 不应该决定 graph identity、planning facts 或 PDDL 语义。

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
- `src/ai_web_explorer/grounded_web/exploration_semantics.py`
- `src/ai_web_explorer/grounded_web/business_affordance.py`
- `src/ai_web_explorer/grounded_web/visual_delta.py`
- `src/ai_web_explorer/grounded_web/openai_visual_delta.py`
- `src/ai_web_explorer/grounded_web/planning_fact_verifier.py`

观察层的 active 与兼容职责包括：

- 构造确定性的 state snapshot 和 signature；
- 为人工审查和 embedding 生成 state summary；
- 让 VLM 提出当前页面可执行的业务动作候选；
- 只比较 before/after 截图并输出 `candidate_added_facts` / `candidate_removed_facts`；
- 由本地结构化 verifier 生成 `PlanningDelta` 和 evidence；历史 `BusinessTransition` 仅保留兼容读取；
- 提供轻量结构化 verifier。

VLM affordance 结果只是候选假设。候选列表本身不等于已验证能力；只有本地验证和动作后
观察支持的成功边，才确认为已验证转换。

profile facts 位于这一层。旧兼容路径把它们作为实验认可的位置、普通能力和业务事实闭集，并把
完整 profile context 传给 Visual Affordance 和 Visual Delta。Visual Delta 语义输出必须经过
`validate_profile_semantic_observation` 闭集校验；候选业务事实还必须由动作后变化与本地 verifier
确认。原始响应和拒绝原因始终保留在 raw edge trace 中。节点可使用 Visual Affordance 提供的
技术性 state label，但 label 不决定 graph identity 或 PDDL facts。

当前 location-scoped active path 的边界是：Visual Affordance 自主发现明确动作及同位置 `requires`，
不接收具体 profile facts、动作示例、契约、预期流程或 PDDL goal；动作后观察只返回
`outcome`、`location_change` 和简短可见证据；稳定的动作完成 predicate 由本地根据成功动作
生成。新路径绕开 targeted scan 和 supplement scan，也不再要求 VLM 输出 planner-facing facts。

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
- `src/ai_web_explorer/grounded_web/location_exploration.py`

主要职责：

- 定义 `WebKobeGraph`、`WebKobeNode`、`WebKobeEdge`；
- 记录 `BusinessAffordance`、`PlanningDelta`、`PlanningState`、`PlanningTransition`，并兼容读取历史 `BusinessTransition`；
- 明确可见变化先保留为独立 raw observation，避免 embedding 提前覆盖；
- 保持可独立加载的紧凑 Raw Graph，并把详细证据放在可选的 `graph_evidence.json` sidecar；
- 离线把 presentation-equivalent observations 保守归入 Planning Graph，并聚合候选能力及精确观察来源；
- 传播 source-aware planning state；
- 在 `PlanningState` 中同时保留 `active_facts`、`profile_fact_ids` 和 `generated_fact_ids`；
- 将 Visual Delta 原始响应和校验轨迹写入 `execution_trace.metadata.visual_delta_trace`；只有闭集校验后的 semantic observation 和已验证 planning facts 才能进入当前语义投影；
- 存储 state embeddings；
- 使用 embedding 相似度结合可靠的本地 revisit evidence 做匹配；embedding 只是记忆辅助，
  不是 graph identity 或 PDDL facts；
- 判断 revisit，并给探索策略提供 memory context；有明确 URL path、结构签名或 Visual Delta 变化时，
  不把候选目标合并回本次 source，但仍可复用有可靠证据的其他历史节点。
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
- `src/ai_web_explorer/grounded_web/frontier_replay.py`
- `src/ai_web_explorer/grounded_web/location_exploration.py`

主要职责：

- 执行一轮 exploration step；
- 从观察层生成的 business affordances 中选择一个业务动作；
- 使用 memory context 和重复惩罚；
- 调用 Stagehand 操作层和 VLM/DOM 观察层；
- 更新 graph；
- 以语义位置维护固定候选池，并按 `(location, action)` 记录成功、重试、stale 和 no-change；
- 新位置执行一次 initial scan 并本地调度依赖链；active path 不触发 targeted/supplement scan，旧机制仅作兼容保留；
- 当前候选耗尽时选择其他可恢复 frontier，通过 `FrontierReplayRunner` reset 并执行保存动作路径；
- 重放末端只验证 semantic location 和必要业务事实，不逐 raw node 严格匹配，也不修改探索图；
- 按正式动作、连续无进展、候选重试、单 frontier replay 和总 replay 参数停止；
- 每个完成动作后更新 latest checkpoint；`--resume-graph` 可恢复 graph、location memory 和累计预算，在新浏览器中继续探索。恢复不还原 cookies、localStorage 或浏览器进程。

低层 DOM interactables 可以继续作为运行时 state summary / embedding matching 的辅助输入，但不再输出到 canonical `graph.json` node，也不作为 graph memory 或探索决策单位。旧的 LLM action selector 路径已经移除，避免系统回退到 selector/locator 驱动的探索。

`WebKobeExplorer` 目前是最大的协调类。后续新增探索策略时，应尽量拆成小组件，不要继续把所有逻辑堆进 `explore_one_step`。

主要函数/类：

- `WebKobeExplorer.explore_one_step`
- `WebKobeExplorer._select_action`
- `WebKobeExplorer._select_business_affordance_action`
- `WebKobeExplorer._match_current_state`
- `WebKobeExplorer._record_source_business_affordances`
- `WebKobeExplorationController.run`
- `LocationExplorationMemory`
- `LocationExplorationCoordinator`
- `FrontierReplayRunner.replay`
- `select_frontier`

### PDDL 映射与 SafeSym Bridge 层

负责 planner-facing 投影和验证。

主要模块：

- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py`
- `src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py`
- `src/ai_web_explorer/grounded_web/semantic_planning.py`
- `src/ai_web_explorer/safesym_bridge/minimal_semantic_pddl.py`
- `src/ai_web_explorer/safesym_bridge/cli.py`

主要职责：

- 读取 `WebKobeGraph` JSON；
- 从成功 raw edge 构建位置、普通能力事实、业务事实和动作前提/效果分离的 `SemanticPlanningGraph`；
- 生成 Minimal Semantic `domain.pddl` 和 `problem.pddl`；
- 保留旧 Phase A / Location PDDL 作为兼容与降级路径；
- 运行 PDDL readiness smoke；
- 运行 SafeSym parser、safety injection、planner smoke。

这一层应保持确定性。它应该消费 graph 中已经记录的语义，不应该直接调用 LLM/VLM。
Minimal Semantic 投影为每个成功动作生成位置限定完成 fact；只有 initial scan 明确给出的同位置
`requires` 才会把相应完成 fact 投影为其他动作的前提。位置变化同时删除旧 `at_*` 并增加新 `at_*`。失败、冲突或缺少
可用语义观察的边被排除，并在 projection report 中说明原因。

主要函数/类：

- `load_web_kobe_graph_json`
- `compile_web_kobe_graph_to_domain`
- `compile_web_kobe_graph_to_pddl`
- `write_web_kobe_pddl_smoke`
- `write_web_kobe_safesym_smoke`
- `build_semantic_planning_graph`
- `compile_minimal_semantic_domain`
- `compile_minimal_semantic_problem`
- `main`

graph artifact 的布局由 `src/ai_web_explorer/safesym_bridge/graph_artifacts.py` 负责：`graph.json` 是可独立加载的紧凑 Raw Graph，`graph_evidence.json` 是可选诊断 sidecar。`evidence_ref` 解析到 sidecar 中稳定的 node/edge key；历史完整 graph 继续兼容读取。当前 SemanticPlanningGraph 和 Minimal Semantic PDDL 只消费 graph 中的已验证语义，不从 sidecar 创造 facts。`raw_graph.json` 保留输入原形；旧 `planning_graph.json` 与 `planning_abstraction_report.json` 继续作为兼容审计产物。

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
  -> LocationExplorationMemory 保存一次 initial scan 的 actions/requires
  -> 本地选择一个 requirements 已满足的未完成 (location, action)
  -> adapter.execute
  -> capture after state/screenshots when execution succeeds or the known Stagehand tool_choice error is reported
  -> 最小动作后观察返回 outcome/location_change/evidence
  -> GraphManager.build_planning_transition
  -> GraphManager.add_edge
  -> LocationExplorationCoordinator 记录动作结果和业务事实变化
  -> 当前路径耗尽时 select_frontier + FrontierReplayRunner
  -> controller 调用可选的完成步骤 checkpoint
  -> 真实 runner 依次写入 embedding、Stagehand trace、graph/evidence
  -> 正常结束时写入 `graph.meta.exploration_summary`
  -> build_semantic_planning_graph
  -> compile_minimal_semantic_domain / compile_minimal_semantic_problem
  -> SafeSym parse / solve
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
