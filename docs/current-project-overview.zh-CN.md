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

## 当前主线

```text
VLM 提出可能可执行的业务动作
  -> 本地 graph/embedding memory 选择一个候选并做语义去重
  -> Stagehand 尝试执行选中的动作
  -> 动作后观察验证可见结果
  -> 本地 verifier 确认已知 profile 边界
  -> Raw Graph 保留稳定观察和可审查结果
  -> 确定性 planning abstraction 只合并证据充分的等价状态
  -> Planning Graph 聚合候选能力并保留精确观察 provenance
  -> Phase A 将跨 planning state 的业务转换写入 domain.pddl
```

VLM affordance 只是“可能可执行”的候选假设，不是已验证能力。Stagehand
只报告执行尝试，不证明状态转换已经发生；动作后观察才是把 raw edge 分类为
观察成功转换、no-op 或失败的证据。候选能力可以被 planning group 聚合，但只有
动作后观察成功的边才能验证转换。

Stagehand、Playwright、VLM/LLM、embedding 都是工具或证据来源。Web-KOBE 自己必须拥有图结构、状态记忆、PDDL 语义和探索控制权。

当前实验必须明确区分三套模型配置：

- `STAGEHAND_MODEL` 只控制 Stagehand 动作执行；当前配置的 DS Flash 属于这一层。
- `OPENAI_VISUAL_DELTA_MODEL` 控制截图 VLM，用于业务候选、`state_label` 和动作前后 Visual Delta；当前中转使用 `gpt-4o`。不得根据 `STAGEHAND_MODEL` 推断或覆盖它。
- `EMBEDDING_MODEL` 只控制本地语义匹配和去重；当前使用 `text-embedding-v4`。

运行实验时，如果没有显式传 `--visual-delta-model`，截图 VLM 会读取 `OPENAI_VISUAL_DELTA_MODEL`，再回退到代码默认的 `gpt-4o`。DS Flash 仅代表 Stagehand 表现，不能描述为截图 VLM 的表现。

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
  -> 更新 raw node 和 edge evidence
  -> 写入已完成动作的 checkpoint
  -> 离线运行 planning abstraction 和 Phase A
  -> 如果当前节点候选耗尽，则以 `current_state_exhausted` 停止，不执行 browser back
  -> 根据步数、重复、frontier 或目标覆盖决定是否继续
```

当前客观状态：

```text
真实浏览器链路：已成立
graph/PDDL/SafeSym 工程链路：已成立
VLM visual delta：已接入，只观察 `candidate_added_facts` / `candidate_removed_facts`，并给出受限的 `visual_change_kind`
business affordance 生成：已有初版
embedding memory：已接入，用于相似状态定位和重复提示
target matching：已有初版，动作后会用 embedding 相似度和可靠的本地 revisit evidence 复用已有业务节点；state summary 可包含本地确认的 planning context，但不是独立否决或裁决门槛；存在明确 URL/signature/visual 变化时不得回并到 source
source 定位：正常探索默认信任当前节点指针；embedding source match 只作为恢复/诊断信号
forward-only frontier 探索策略：当前节点候选耗尽即停止；graph meta 记录 frontier/step 诊断信息
连续无进展终止：通用 controller 仍支持该机制；真实 Stagehand runner 暂时关闭这一提前终止条件，主要受最大步数约束
checkpoint：每个完成动作后更新 latest 的 embedding、Stagehand trace、graph/evidence；正常结束后写入带 `exploration_summary` 的最终结果
Stagehand thinking/tool_choice 异常：已定义为需要继续动作后观察；有变化时记为成功转换，无变化时记为 `no_observed_change`
Visual observations：只保留在 raw edge trace，不进入 `PlanningState` 或 Phase A PDDL
planning abstraction：已实现且已有单元测试，但尚未通过新的真实网页实验验证分组和能力 provenance
Phase A domain：当前只投影 planning locations 和非自环业务转换
Visual Delta taxonomy：当前有限分类已实现，但分类质量和最终 taxonomy 仍是待审查议题
自由探索策略：尚未稳定
profile fact verifier：已接入最小确定性 verifier，只负责从本地结构化签名确认 profile facts
PDDL 语义质量：可消费，但还不够稳定和可读
业务节点命名：新探索使用 VLM state label；名称不参与 node identity 或 matching
```

详细 pipeline 和模块职责见 `docs/project-structure.zh-CN.md`。

## 当前观察、规划和异常处理边界

- Visual Delta 只比较动作前后截图，输出 `candidate_added_facts` / `candidate_removed_facts` 和受限的 `visual_change_kind`；新探索不生成 VLM `BusinessTransition` 判断。
- Visual observations 只作为 raw edge 的可审查证据保留在 `execution_trace.metadata.visual_delta_trace`，不进入 `PlanningState`、planning transition 传播、target matching planning facts 或 Phase A PDDL。
- Structured profile verification 仍可独立构建 `PlanningState`；planning abstraction 只在本地证据足够时合并观察，Phase A 当前只基于 planning location 和非自环业务转换生成 `domain.pddl`。
- 只要 URL path、结构签名或 Visual Delta 有明确变化，target matching 就不能把候选目标合并回 source；仍可按既有可靠 revisit evidence 复用其他历史节点。
- `Thinking mode does not support this tool_choice` 只表示 Stagehand/模型适配层异常：探索器会继续获取动作后状态、截图和 Visual Delta；有明确变化时记录成功转换，无变化时记录 `no_observed_change` 自环。未知执行错误仍是失败自环且不调用 Visual Delta。

当前 planning-state 闭环为：

```text
VLM 提出可直接执行的业务动作
→ Stagehand 执行一个选中的动作
→ raw graph 记录观察转换
→ 本地 verifier 确认已知 profile 边界
→ planning abstraction 保守合并 presentation 等价观察
→ planning graph 聚合真实观察到的能力
→ Phase A projector 只输出跨 planning state 的转换
```

profile facts 是强但不完整的语义锚点。`visual_change_kind` 只是观察证据，不是规划决定：`0 → 1` 的购物车数量确认 `cart_has_items`，`1 → 2` 保留该 profile fact；presentation 动作仍保留在 graph 能力和自环中，即使不进入 PDDL；unknown、surface、mixed 默认保持分离。旧的 `BusinessTransition` 和 exact-action-set consolidator 已移除，历史 JSON 中的旧 key 仍会被忽略并正常读取。

### Graph artifact 与 evidence sidecar

当前实验 writer 将 `graph.json` 写为紧凑的主图，并将 verbose 的诊断证据写入同目录的 `graph_evidence.json`。紧凑 graph 保留节点/边拓扑、页面 URL 与结构签名、冻结的 `business_affordances`、状态/访问计数、动作语义、执行结果和非空规划 transition；重复的 page/node evidence、instruction/description、observed/schema delta、完整 Stagehand/Visual Delta trace 等放入 sidecar。紧凑项的 `evidence_ref` 以 `node-evidence:<node_id>` 或 `edge-evidence:<edge_id>` 解析到 sidecar 对应 entry。

历史完整 graph 仍可直接读取；紧凑 graph 即使没有 sidecar 也可加载和运行 Phase A。Phase A 只读取 graph，不 hydrate 或依赖 `graph_evidence.json`；CLI 生成的 `raw_graph.json` 保持输入 JSON 的紧凑/完整形状。sidecar 中的具体视觉事实不会进入 compact state、`PlanningState` 或 PDDL。状态命名保持不变，命名改进仍是独立后续主题；候选生成的失败/空结果区分也尚未在此 artifact 改动中解决。

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
```

历史 `WebObservedGraph` 设计只保留在旧 spec/plan 文档中作为参考。

### 2. profile facts 需要降低影响

profile facts 不是网页状态全集。它们的新定位是：

```text
PDDL 候选谓词词表 + 优先观察目标 + 跨网站语义对齐锚点
```

Graph 层仍需兼容读取历史 profile/generated facts；但当前新探索的 Visual Delta facts 只保留在 raw edge trace，不作为 planning facts 记录或投影。后续若要把观察事实晋升为 planner-facing 语义，需要单独的审查策略。

当前事实来源边界已经收紧：visual delta VLM 不接收 profile facts，也不负责把返回事实匹配到 profile。只有本地结构化 verifier 明确确认的事实，才进入 planning/profile facts；Visual Delta 返回事实只进入 raw edge trace。Graph manager 不再因为事实名称恰好出现在 profile 中而自动晋升。

### 3. 探索控制权必须留在本地系统

当前长期职责边界固定为：

```text
VLM 观察当前页面，并提出业务动作候选
本地 current-node pointer 维护 source 位置
本地 graph / embedding memory 做 target merge、recovery 和动作去重
Stagehand 只尝试执行被选中的动作
动作后观察总结可见业务变化并验证结果
graph policy 决定 create / merge / revisit
PDDL projector 确定性消费 graph 中已经记录的语义
```

这意味着 VLM 不应该判断“动作是否做过”“当前状态是否是新节点”“是否应该建新节点”。VLM 没有稳定的 graph 记忆，它应该提供的是页面证据、候选业务动作和 before/after 变化摘要。

正常探索不应每一步都用 embedding 重新定位 source。source 默认来自上一条成功 edge 的 target；如果动作生成新节点就跳转过去，如果命中旧节点就跳到旧节点，如果没有有效变化就留在原地。embedding source match 只用于页面刷新、实验恢复、外部导航或浏览器实际位置和 graph 指针可能不一致的诊断/恢复场景；当前探索 loop 不执行 browser back recovery。

动作去重不应只依赖 `node_id + action_slug`。这个方式可以作为快速索引，但相似节点上的动作记忆可以由 embedding-assisted memory 辅助：

```text
current / target state summary
  -> embedding match 到已有 node / state variant
  -> 查询相似节点下已经尝试过的业务动作或可复用目标状态
  -> 对重复或低价值动作降权或跳过
```

Profile facts 可以帮助对齐 planner-facing 语义，但不是唯一探索边界。Visual observations 与规划状态隔离；Phase A 不把这些观察事实作为 predicates、preconditions 或 effects。

### 4. Stagehand 是操作层，不是状态真相层

Stagehand 尝试执行选中的动作并提供 execution trace；它不负责候选生成，也不能直接决定：

- node identity；
- planning facts；
- PDDL predicates/effects；
- safety triggers；
- 探索是否完成。

状态真相应来自 Web-KOBE 的 before/after observation、VLM/结构化证据、graph memory 和后续 verifier。

在推荐探索链路里，Stagehand 应被视为动作执行器。它的 prompt 应接近“执行这个被选中的业务动作并停止”，而不是“探索网站并自己选择下一个有用目标”。Generic Stagehand exploration prompt 只能作为 fallback。

### 5. PDDL projector 应保持确定性

PDDL projector 应消费 planning graph 中已经记录的语义，不应直接调用 LLM/VLM，也不应自由发明谓词。

规划抽象先从 Raw Graph 生成 `planning_graph.json` 和
`planning_abstraction_report.json`，Phase A 只消费 Planning Graph。当前 Phase A
主要输入是：

```text
planning-group location
planning-group business affordances and observed capabilities
eligible non-self-loop edge action names
```

Phase A 只把 canonical locations 和 eligible non-self-loop business transitions
投影到 `domain.pddl`。`supporting_facts`、`PlanningState`、profile facts 和 Visual
Delta observations 都不进入 Phase A 的 preconditions 或 effects。

命名问题暂缓，但方向是：LLM/VLM 可以在探索阶段帮助生成语义 label；PDDL projector 只做确定性规范化和投影。

### 6. Graph 质量要区分 Raw observation identity 与 Planning-state identity

当前 graph 质量评价不应只看是否生成了节点、边和 PDDL，还要区分两种 identity：

- Raw Graph identity 追求观察忠实，而不是业务状态唯一。明确、稳定、可观察的 URL/signature/visual 变化，即使业务解释可能相同，也可以生成 raw observation node。
- Planning-state identity 才追求业务语义唯一。Planning Abstraction 可以保留 provenance，把 presentation-equivalent observations 归入同一 planning state；例如 `cart_has_items` 已为 true 且未建模数量时，购物车数量从 1 变为 2 可以保留 Raw Graph node，但通常不产生新的 planning node。
- embedding target matching 不得覆盖 explicit observation change，不得把候选目标合并回本次 source；有可靠证据的 non-source 历史 raw observation 仍可以复用。
- 不同来源路径可以由 edge 表达；Planning Graph 的 grouping 表达规划所使用的语义状态 identity。
- 节点命名要语义稳定；如果 PDDL 出现大量 `at_product_details_002` / `at_shopping_003`，通常说明 planning-group 或命名存在问题。
- 每个节点和边都要能追溯到 evidence，包括 VLM summary、planning facts、before/after 截图或结构化观察。

### 7. 探索策略应以 frontier 为核心

当前确认的第一版探索策略是简单、forward-only 的 frontier，而不是让 Stagehand 或 VLM 自由规划：

- 每个 Raw observation node 首次生成业务候选时，不超过配置的候选上限；上限不是 quota，不要求凑满，少于上限或空列表都合法。后续 revisit / target merge 回到同一节点时不再重新生成或追加候选。
- 本地系统把候选动作标记为未尝试、已尝试、no-op 或失败；VLM 只负责提出候选和证据，不负责记忆。
- 当前节点优先执行未尝试候选；动作后若有明确观察变化就生成新的 Raw observation node，若有可靠证据命中已有历史 raw observation 就复用，否则没有有效变化时留在原节点；Planning Abstraction 后续可以再把这些 Raw observations 归组。
- 命中已有节点时继续使用该节点首次建立的固定候选，不重新生成或追加候选。
- 当前节点候选都尝试完后，直接记录 `current_state_exhausted` 并停止，不执行 browser back；连续没有新节点或新语义转换时计为无进展，但真实 Stagehand runner 暂时不因此提前终止，最大步数仍有效。
- 每个完成的探索动作都会写入 latest checkpoint；checkpoint 只保护已完成探索，不提供 resume、replay 或逐步历史版本。
- runtime memory 只在当前节点或可靠 embedding 匹配的历史节点上下文内避免同义动作，不做全局动作屏蔽。

短期先从已有 edges 反查 tried/no-op/failed 状态，不新增复杂 memory 表。旧的 selector/locator fallback 已删除；business-affordance selector 不再在候选耗尽后继续选择成功但已尝试的动作。`graph.meta` 记录 step kind/status、连续无进展和 frontier 诊断信息。后续可再评估 replay、browser back recovery 或更完整的 frontier 恢复，但不属于当前闭环。

## 当前主要问题

### P0: planning abstraction 和 target matching 仍需真实网页验证

此前 Practice Automated Testing Shopping 实验曾生成重复的页面/业务状态变体；该历史结果不作为当前最新结论，仍需要新的受控实验确认 graph merge 质量。

planning abstraction 和 target matching 已实现并有单元测试，但尚未通过新的真实网页实验验证二者组合行为。当前已接入 target matching V1：动作后的目标状态会先用 embedding 相似度和可靠的本地 revisit evidence 匹配已有节点；state summary 可包含本地确认的 planning context，但不是独立否决或裁决门槛。匹配成功则 edge 指向已有节点，而不是生成新的状态变体。明确变化时 source 节点受到保护，但其他有可靠证据的历史节点仍可复用。下一步需要通过真实网站实验确认它是否能减少重复业务节点。

### P0: Visual observations 与规划状态保持隔离

Visual Delta facts 目前只作为 raw edge trace 的观察证据保留，不进入 `PlanningState.active_facts`，也不参与 planning transition、target matching planning conflict 或 Phase A PDDL。

后续若需要将视觉观察提升为 planner-facing facts，必须另行设计验证、晋升和投影策略；本轮不处理。

### P0: PDDL 语义质量仍不稳定

SafeSym 可以结构性消费当前产物，但 PDDL 的语义质量还不稳定：

- location predicate 仍可能出现 `at_shopping_002` 这类不可读名字；
- VLM state label 已用于节点展示；名称只做本地技术清洗，不参与 node identity 或 matching；
- action precondition 依赖 source node 定位，需要继续用实验确认；
- profile facts 不完整时，PDDL 会退化为 location path；
- Phase A 当前从 planning graph 投影 planning locations 和非自环业务转换；Visual Delta facts 不进入 domain PDDL。

### P1: 探索仍是受限的 forward-only frontier

当前系统已经有 business affordance、局部 tried/avoid memory、语义动作去重和连续无进展终止，但仍缺少：

- candidate action ranking；
- 更丰富的 coverage 评估；
- replay 或 browser back recovery；
- 跨节点的长期记忆模型。

现在更像 bounded exploration V1，还不是成熟自由探索。此前实验中页面在商品列表和商品详情之间来回切换，核心原因不是 VLM 完全不会提候选，而是旧 selector 在当前节点候选都尝试完后，会回退到“非 avoid 的成功动作”，导致成功但低进展的动作被重复执行。当前修复已改为：当前节点无未尝试业务候选时返回 None 并以 `current_state_exhausted` 停止；重复的已知 transition 或连续没有新 graph information 会计为无进展。旧的 LLM action selector / OpenAI action selector 模块已删除，避免探索链路回退到 locator-driven 行为。

通用 controller 仍保留连续无进展策略：单次 `failed_execution`、`no_observed_change` 或重复已知 transition 都不会立刻终止；默认调用者可在连续无进展达到阈值时停止。真实 Stagehand runner 显式关闭该阈值，仅在当前节点候选耗尽、达到最大步数或其他显式条件时停止。运行中 `graph.meta` 记录 step 诊断信息；正常结束后的 `exploration_summary` 记录请求步数、完成步数和终止原因。

最近的清理已经把通用 Stagehand exploration 默认模式改为 `observed_action`，保留 VLM 候选动作的 `supporting_facts`，并移除了业务候选选择中的全局 completed action 降权；重复策略应基于当前节点或 embedding 命中的相似节点上下文。

已知 `Thinking mode does not support this tool_choice` 属于 Stagehand/模型适配异常，不足以证明网页动作没有发生。探索器会继续获取动作后状态、截图和 Visual Delta：若 URL/signature/visual 任一明确变化，则记录成功转换；若没有变化，则记录 `no_observed_change` 自环，再由本地动作记忆避开并继续尝试其他候选。未知执行错误仍记录失败自环且不调用 Visual Delta。

当前 deferred item：`BusinessAffordance.action_name`、`label` 和 `target_hint` 存在部分语义重叠，需要后续单独进行 schema review。

### P1: WebKobeExplorer 有中心化风险

`WebKobeExplorer` 目前同时处理观察、动作选择、VLM、embedding、source/target matching、edge 构造和 planning transition。它是当前主线核心，短期可以保留，但后续新增探索策略时不应该继续把所有逻辑塞进 `explore_one_step`。

### P2: 低层 UI 证据已退出紧凑 raw graph

低层 DOM interactables 可以在运行时作为 state summary / embedding matching 的辅助输入，但不再输出到紧凑 `graph.json` 的 node 结构中。它不承担动作选择、动作记忆或 frontier 单位职责；`mark_interactable_explored`、`interactables_for_node`、旧 LLM action selector 和对应测试已经删除。业务探索图应围绕：

```text
business_affordances + raw observed edges + planning_transition
```

### P2: verifier 覆盖仍然有限

当前已有本地结构化 verifier，可确认少量 profile boundaries；它仍覆盖有限。VLM candidate facts 只作为观察证据，未来若要晋升为 planner-facing truth，仍需要显式本地规则或审查流程。

短期先不做完整 verifier，但必须保留 provenance 和 evidence。

## 下一阶段优先级

1. 重跑 Practice Automated Testing Shopping，验证 forward-only 候选耗尽停止、最大步数边界和 checkpoint 落盘，并继续观察 cart / checkout 等业务状态。
2. 根据 graph meta 和 edge trace 分析每个节点候选数量、已尝试/未尝试/no-op/失败统计、重复节点命中和 stop reason。
3. 单独评估通用 controller 的连续无进展默认阈值（当前为 3）；真实 Stagehand runner 当前不使用该提前终止条件。
4. 继续检查 target matching 是否减少重复业务节点，以及 embedding source/target matching 是否只在正确位置发挥作用。
5. 检查 graph 和 domain PDDL 质量，尤其是 source/target、precondition/effect、node label 和重复 `at_*_002`。
6. 讨论 generated facts 的晋升/可选投影策略。
7. 评估是否把运行时 DOM interactables 进一步迁入 trace/debug artifacts，或完全从主线状态匹配中剥离。
8. 后续逐步拆分 `WebKobeExplorer`，避免核心协调类继续膨胀。

## 实验管理规则

每个网站只保留最新一轮有效结果：

```text
outputs/experiments/<site_name>/latest/
```

默认每轮实验覆盖同一网站的 `latest/` 目录；只有明确归档时才复制到其他归档位置。

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
