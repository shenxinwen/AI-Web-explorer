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

## 2026-08-10 - 真实 Stagehand 实验采用有界 checkpoint

更改：
- 当前真实 Stagehand runner 以请求的最大步数作为主要终止条件。
- 当前节点没有可执行候选时仍可自然提前结束；真实 runner 暂时关闭连续无进展提前终止，通用 controller 仍保留该可选机制。
- 每个完成动作后原子更新 latest 的 embedding、Stagehand trace 和 graph/evidence；正常完成后再写一次最终结果，graph/evidence 是最后提交的配对标记。
- 正常完成后的 `graph.meta.exploration_summary` 记录 `requested_steps`、`steps_completed` 和 `stop_reason`；中途 checkpoint 不写入尚未确定的终止摘要。
- checkpoint 只保护已经完成的探索，不提供 resume、replay 或逐步历史版本。

原因：
- 真实实验中的单步 Stagehand/VLM/embedding 调用可能较慢或被外部中断；必须先保留已完成步骤，避免只在整轮结束时落盘。
- 在当前 forward-only 路径中，连续无进展不应暂时抢先于用户配置的最大步数终止真实 runner。

影响：
- 中断时最近一次成功 checkpoint 仍可读取；未完成的当前动作不会被虚构成 graph edge。
- embedding 或 trace 可能在 graph 提交前包含同轮较新的内容，但 graph/evidence 配对仍是正式 checkpoint 依据。

## 2026-08-06 - 分离 VLM 观察事实与本地 profile facts

更改：
- visual delta VLM prompt 不再携带 `BusinessFlowProfile` 或探索目标，只接收动作和 before/after 观察上下文。
- VLM 返回的 `candidate_added_facts` / `candidate_removed_facts` 默认全部记录为 `generated_fact_ids`，不再因为名称与 profile fact 相同而自动归类。
- `profile_fact_ids` 只接受本地结构化 verifier 明确确认的结果；`WebKobeGraphManager` 不再根据 profile 词表和 fact 名称做隐式推断。

原因：
- profile facts 不是网页状态全集，直接交给 VLM 会让模型把预设词表当成当前页面事实或典型流程提示。
- VLM 观察到的事实可能是 profile 未覆盖的新状态，也可能只是视觉层面的局部变化；名称相同不等于已经满足本地事实定义。
- 需要把“VLM 观察到什么”和“本地系统确认了什么”分开，保留事实来源，方便 graph/PDDL 审查。

影响：
- graph 仍然可以记录更开放的 VLM generated facts，不会因为 profile 词表不完整而丢失状态信息。
- profile facts 的稳定入口变成本地 verifier；后续若要把 generated fact 晋升为 profile fact，必须增加显式规则或审查流程。
- 现有 `VisualDeltaRequest.profile` 和 graph manager 的兼容参数暂时保留，但不再作为 VLM 输入或自动匹配依据。

## 2026-08-08 - Stagehand tool_choice 异常必须继续动作后观察

更改：
- 仅对 `Thinking mode does not support this tool_choice` 启用继续观察。
- 有明确变化时记录成功转换；无变化时记录 `no_observed_change` 自环。
- 保留原始 error 和 `backend_reported_success=false`。
- Visual observations 只保留在 raw edge trace，不进入 `PlanningState` 或 Phase A PDDL。
- 有明确变化时 target matching 不得回并到 source，但可复用有可靠证据的非 source 历史节点。

原因：
- Stagehand 可能先完成输入、点击或按键，再在工具协议收尾阶段返回该错误。
- 执行器错误不能替代 Web-KOBE 的动作后页面观察。

边界：
- 未知错误仍是失败自环且不调用 Visual Delta。
- 不调整 embedding 阈值、URL/signature 粒度或 Phase A/PDDL 规则。
- 实验默认覆盖 `outputs/experiments/<site>/latest/`，除非显式归档。
- `BusinessAffordance.action_name`、`label`、`target_hint` 的语义重叠留待后续 schema review。

## 2026-08-08 - 探索 loop 收束为 forward-only frontier

更改：
- 当前节点候选耗尽时直接记录 `current_state_exhausted` 并停止，不执行 browser back 或 visit-stack recovery。
- 命中已有节点时继续使用该节点已经建立的固定候选，不重新生成候选。
- 重复已知 `(source, action, target)` transition，或连续没有新节点/新语义转换，计为无进展；最大步数仍然有效。
- runtime memory 只在当前节点或可靠匹配的历史节点上下文内避免同义动作；embedding 相似度用于局部语义去重，不做全局屏蔽。
- Phase A 不再因为 frontier 尚未覆盖全部 affordance 而拒绝节点；部分 frontier 上已经真实观察成功、目标存在的边仍可进入 canonical graph 和 `domain.pddl`，失败或缺失目标的边仍排除。

原因：
- 当前阶段需要先验证单向探索和停止边界，browser back、replay 和复杂 DFS recovery 不属于本轮最小闭环。
- 已观察到的业务边即使节点仍有未尝试候选，也应成为 Phase A 的可审查事实；未完成候选不等于已观察边无效。

影响：
- 通用 controller 仍可由 `current_state_exhausted`、可选连续无进展阈值和最大步数决定停止；自 2026-08-10 起，真实 Stagehand runner 关闭连续无进展阈值，主要由最大步数和当前节点候选耗尽决定。
- raw graph 仍原样保留；planning graph/domain 只消费符合现有成功和目标存在规则的 observed edges；presentation 自环保留在 planning graph 中用于审计和能力发现，但不进入 Phase A PDDL。
- 不新增持久化 graph 字段、memory 表或 PDDL 事实来源。

## 2026-08-02 - 将探索策略收束为 frontier / DFS

更改：
- 在 current project overview 中明确 bounded exploration V1 的方向：每个节点维护一组当前可执行业务候选，优先执行未尝试候选。
- 历史计划曾要求当前节点候选耗尽时回退到仍有 frontier 的历史节点；该方案已由 2026-08-08 的 forward-only 决策取代。
- 短期继续从已有 edges 反查 tried / no-op / failed 状态，不急着新增复杂 memory 表；browser back / DFS recovery 后续再接 embedding source relocalization。
- 当时的最小实现曾包含 selector 去重和 browser back visit stack；当前代码已移除 browser back recovery，保留局部候选去重。

原因：
- 最新 Practice Automated Testing Shopping 实验在商品列表和商品详情之间反复切换，说明当前 selector 的“全部尝试后选择非 avoid 成功动作”兜底会制造循环。
- VLM 可以提出候选动作和证据，但没有稳定图记忆；动作是否做过、是否回退、是否终止应由本地 graph/controller 决定。
- 这个方向更接近 SEE / UI-KOBE 类探索图构建的 frontier 思路，同时保持第一版实现足够简单。

影响：
- 后续实验应验证 forward-only 候选耗尽停止和重复节点命中；连续无进展阈值只在通用 controller 中单独评估，真实 Stagehand runner 自 2026-08-10 起不使用该提前终止条件。
- embedding 继续服务 target merge 和当前/可信历史节点上下文内的动作记忆，不在正常探索中每步覆盖 source。
- graph/PDDL 质量评估继续关注候选耗尽、重复节点命中和观察成功边，不把 browser back 次数作为当前闭环指标。

## 2026-08-03 - 将 frontier 指标写入 graph meta（历史记录）

更改：
- `write_web_kobe_graph` 在输出 `graph.json` 时写入 `meta.frontier_metrics`。
- 指标包括每个节点的候选动作数、已尝试动作、未尝试动作、no-op 动作、失败动作、全局 frontier/exhausted 节点数和重复 target 命中数。
- `WebKobeGraphManager` 新增轻量 `meta` 字典；当时的实现还曾记录 visit-stack backtrack。

原因：
- 后续实验不能只看 node/edge 数量，需要知道每个节点的候选动作是否真的被消耗、是否仍有 frontier、重复节点是否被命中。
- 指标可以由现有 graph 派生，不需要提前引入新的 memory 表或改变 node/edge schema。
- 当时认为 backtrack 不记录为业务 edge，因此需要记录控制层回退次数；该 recovery 方案已被 forward-only 决策取代。

影响：
- 当时计划下一轮实验从 `graph.json` 判断探索是否卡在某个节点、是否因为候选耗尽触发回退、哪些动作被 no-op/failed；当前应改为观察候选耗尽停止和无进展统计。
- 本条关于完整 DFS/backtrack controller 的设计属于历史方案；当前 controller 在当前节点候选耗尽时记录 `current_state_exhausted` 并停止。
- 指标属于诊断/实验质量信息，不进入 PDDL projector。

## 2026-08-03 - controller 改为连续无进展终止（历史记录）

更改：
- `WebKobeExplorationController` 不再遇到单次 `failed_execution` 就终止。
- 新增 `max_consecutive_unproductive_steps`，默认值为 3。
- `failed_execution`、`no_observed_change` 等无进展业务 edge 会累加连续无进展计数；成功业务 edge 会清零。
- 当时将成功的 `control_backtrack` 视为有效探索控制动作；该行为已由当前 `current_state_exhausted` forward-only 边界取代。
- `graph.meta` 记录 `last_step_kind`、`last_step_status`、`consecutive_unproductive_steps` 和 `max_consecutive_unproductive_steps`。

原因：
- 开放探索中失败是正常试错信号，不应把系统重新拉回“任务必须每步成功”的执行器逻辑。
- 用户明确要求业务动作也允许失败，只有连续失败或连续无进展后才终止并记录。
- 当时认为 backtrack 属于探索控制动作；当前不执行 browser back，重复已知 transition 和无新 graph information 会计为无进展。

影响：
- 实验仍可继续越过偶发的 Stagehand 执行失败、no-op 或模型适配异常，直至连续无进展阈值或其他停止条件命中。
- stop reason 更符合探索语义：`current_state_exhausted` 表示当前节点候选耗尽，`consecutive_unproductive_steps` 表示连续无进展耗尽。
- 后续真实实验需要评估默认阈值 3 是否合适。

## 2026-08-02 - 将 Stagehand thinking/tool_choice 异常视为非致命执行异常

更改：
- `WebKobeExplorer._edge_status` 遇到 `Thinking mode does not support this tool_choice` 时，不再直接返回 `failed_execution`。
- 如果该异常伴随 observed delta 或 planning delta fact change，edge 仍记录为 `succeeded_with_observed_change`。
- 如果没有可见变化，则记录为 `no_observed_change`，让 controller 继续探索并由本地动作记忆避开该 no-op 动作。

原因：
- 该异常来自所选模型与 Stagehand thinking/tool_choice 参数的适配问题，不一定代表浏览器动作没有执行。
- 用户已明确该异常应作为非阻塞异常处理；实验不应因为这个已知适配异常提前终止。
- 将无变化情况记为 no-op，可以保留诊断信息，又能让探索继续尝试其他候选动作。

影响：
- Practice Automated Testing 这类实验后续不会因为单纯 `Thinking mode does not support this tool_choice` 停在 failed_action。
- 若页面确实没有变化，该动作会进入当前节点的 no-op/avoid 记忆，后续选择器可以尝试其他业务动作。
- 真正的未知执行错误仍保持 `failed_execution`，继续作为实验终止信号。

## 2026-08-02 - 正常探索 source 定位信任执行轨迹

更改：
- `WebKobeExplorer._resolve_current_source_id` 在当前节点指针有效时，不再接受 embedding source match 把 source 拉回其他相似节点。
- source embedding match 保留为 metadata / recovery 信号；正常探索的 source 默认由上一条成功 edge 的 target 维护。
- 更新 overview，明确 source 定位、target matching、recovery 的职责边界。

原因：
- 探索过程中系统自己知道上一条边的 target。只要浏览器没有被外部打断，当前节点指针比每步 embedding 重新定位更可靠。
- 之前实验出现过 embedding 把后续动作 source 拉回相似旧节点，导致 PDDL precondition 和 graph source 错位。
- 现有 GUI exploration 工作通常会在动作后识别/匹配 target，并在回退、恢复或离线审查时做状态匹配；不应让相似度每步覆盖执行轨迹。

影响：
- 常规探索链路变为：current node pointer 决定 source，动作后 target matching 决定是否复用旧节点或创建新节点。
- embedding 的主职责收窄为 target merge、recovery、相似节点动作记忆和后续图审查。
- 后续实现 browser back / DFS recovery 时，可以显式进入 recovery 模式再使用 source embedding relocalization。

## 2026-08-02 - 接入动作后 target matching V1

更改：
- `WebKobeExplorer` 在动作执行后、写入目标节点前，新增 target matching 阶段。
- target matching 使用动作后的 state summary、planning_transition.post_facts、visual summary 和现有 state embeddings 查找相似目标节点。
- 只有 embedding 判断为 `same` 且 planning facts 兼容时，才复用已有目标节点；否则保留原有创建/变体逻辑。
- edge execution metadata 新增 `target_state_match`，用于实验报告审查匹配状态、分数和是否被接受。
- 同步修正无 business profile 的低层探索推进：当普通 observed delta 成功发生且没有 business/planning transition 时，也允许当前节点指针推进，避免后续边持续从起点发出并覆盖起点快照。

原因：
- 之前系统有 source matching，但缺少 target matching，导致不同路径到达同一业务状态时容易重复创建节点。
- “防污染”的 state variant 逻辑只能避免把不兼容 facts 写进旧节点，不能解决“不同 node_id 但同一业务状态”的归并问题。
- 第一版需要保守，避免误合并；因此必须同时满足 embedding 相似和 planning facts 兼容。
- Playwright fixture golden path 暴露了另一个基础图质量问题：无 business profile 场景下当前节点不推进，会污染起点节点快照；这与 target matching 不同，但同属 source/target 定位基本质量。

影响：
- 首页到购物车、商品详情页到购物车等不同路径，后续有机会复用同一个业务节点。
- PDDL 中 `at_xxx_002` / `at_xxx_003` 膨胀有望减少，但需要真实网站实验验证。
- target matching 仍是 V1，不替代后续 UI-KOBE 风格的二次图优化。
- 本地 fixture 探索的 edge source 更接近真实执行轨迹，避免所有低层动作都从 start node 发散。

## 2026-08-02 - 确立 graph 质量评价原则

更改：
- 在 `docs/current-project-overview.zh-CN.md` 和 `docs/current-project-overview.md` 中新增 graph 质量原则。
- 明确 graph 质量优先看业务状态唯一性，而不是只看是否生成了节点、边和 PDDL。
- 将“相同业务状态还没有稳定合并”提升为当前 P0 问题。

原因：
- 最新 Practice Automated Testing Shopping 8 步实验虽然完整生成了 graph 和 domain，但出现多个 planning facts 相近的节点，例如 `product_details_visible + cart_has_items` 被拆成多个 `product_details` / `cart_with_items` 变体。
- 用户确认的方向是：不同来源路径可以指向同一个业务状态节点，例如首页到购物车、商品详情页到购物车都应复用同一个购物车节点。
- 当前问题的关键不是简单降低某些动作权重，而是让 post-action target state 优先匹配并复用已有业务节点。

影响：
- 后续 graph 质量审查至少要检查：节点唯一性、merge-before-create、边表达路径而节点表达状态、PDDL location predicate 可读性、evidence 可追溯性。
- embedding 不应只作为 metadata 记录，还应参与目标节点定位和合并。
- PDDL 中大量 `at_xxx_002` / `at_xxx_003` 应被视为 graph merge 或命名策略的质量信号，而不是单纯 projector 后处理问题。

## 2026-08-02 - 修正通用探索实验入口与动作记忆边界

更改：
- `web-kobe-stagehand-explore` 的默认 Stagehand execution mode 从 `business_milestone` 改为 `observed_action`，让通用探索入口默认不再生成虚拟 milestone 动作。
- `BusinessAffordance` 新增 `expected_change` 字段，并在 VLM 候选解析、graph JSON 序列化和 graph JSON 读取中保留。
- business affordance selector 移除全局 completed action 降权；重复判断回到当前节点或 embedding 命中的相似节点上下文，通过 `tried_action_ids` / `avoid_action_ids` 控制。
- `docs/safesym-bridge.md` 明确：`observed_action` 是通用 bounded exploration 默认路径，`business_milestone` 只作为 legacy fallback 或 checkout benchmark smoke 使用。

原因：
- 通用探索的主线应该是 VLM 提候选、本地 graph/embedding memory 选择和去重、Stagehand 执行选中动作；默认 `business_milestone` 会把实验带回旧任务驱动路径。
- 同名业务动作在不同业务状态下可能合理重复，例如不同商品详情页上的 `add_item_to_cart`，不应被全局 completed action 直接降权。
- `expected_change` 是候选动作排序和人工审查的重要证据，之前只写在 prompt schema 中但没有进入 graph，会丢失信息。

影响：
- 下一轮 `web-kobe-stagehand-explore` 实验更接近当前探索方向。
- embedding-assisted memory 的职责更清楚：定位当前/相似节点，并基于这些节点的 tried actions 做重复控制。
- 旧 `web-kobe-ecommerce-stagehand-smoke` 仍可保留为任务驱动 benchmark，不再代表主探索实验。

## 2026-08-02 - 收紧探索职责边界 prompt

更改：
- `business_affordance` 的 VLM 候选动作 prompt 不再要求或暗示 `create new node`、`already tried` 等 graph memory / 建图判断，只要求返回可见业务动作、证据和预期变化。
- generic Stagehand prompt 改为“执行一个已选中的业务动作并停止”；没有已选动作时才作为 fallback 选择一个明显业务动作。
- exploration memory prompt 改为只给 Stagehand 提供上下文，不再要求 Stagehand 自己选择动作。
- 从 VLM 候选动作生成的 `business_intent` 执行指令明确要求只执行该动作，完成或失败后停止，不继续下一个业务目标。

原因：
- VLM 没有稳定 graph 记忆，不应判断动作是否做过、状态是否新、是否应该建节点。
- Stagehand 属于操作层，不应同时承担探索规划职责，否则会和本地 graph / embedding memory 的选择逻辑冲突。
- embedding-assisted memory 才是重复识别、revisit 定位和动作降权的主机制；prompt 只能提供证据和执行约束。

影响：
- 探索链路职责更清楚：VLM 看，Web-KOBE 选，Stagehand 做。
- graph / PDDL 语义更不容易被 prompt 自由规划污染。
- 下一步需要通过真实网站实验验证：VLM 候选动作是否足够好、本地选择是否真正避开重复、Stagehand 是否仍会越界执行多个业务目标。

## 2026-08-02 - 结构化优化电商 profile facts

更改：
- 在 `ecommerce_checkout_profile()` 中补充更通用的电商状态事实：`product_details_visible`、`checkout_user_info_required`、`payment_info_required`、`cart_total_visible`、`invoice_available`、`out_of_stock_visible`。
- 将 checkout 的“需要填写/选择”和“已经完成”拆开描述，降低 VLM 把表单出现误判为信息完成的概率。
- 将 `product_details_visible` 从 generated fact 候选提升为 ecommerce profile fact；VLM 仍可提出未声明的新 generated facts，但默认不进入 PDDL。

原因：
- 最近实验中商品详情、发票、支付方式等状态反复出现，但 profile 词表覆盖不足，导致 VLM 生成临时 facts 或回落到弱节点命名。
- `checkout_user_info_complete` / `payment_info_complete` 语义过重，如果缺少 required 层，VLM 容易过早打上 complete facts。
- 优化 profile facts 可以提升观察质量、节点命名、planning_transition 和 domain PDDL 的稳定性。

影响：
- 电商 profile 的通用性增强，但 graph policy / PDDL projector 仍只通过 profile 接口读取 facts，没有写入电商专有逻辑。
- `product_details_visible` 现在会被归类为 profile fact，而不是 generated fact；相关 visual delta 测试已同步。
- 后续仍需要通过真实实验验证这些 facts 是否减少误判和 `at_product_list_00x` 膨胀。

## 2026-08-01 - 用执行轨迹约束 source matching，并清理 embedding 摘要

更改：
- `WebKobeExplorer` 增加轻量级当前节点指针：成功产生有效业务状态转移后，下一步默认从上一条 edge 的 target 节点继续。
- embedding source match 仍然保留，但当它想把 source 拉回 planning facts 不兼容的旧节点时，会被拒绝，只作为 metadata 参考。
- `build_state_summary` 对 Stagehand business intent / policy prompt 做摘要清理，embedding 文本优先使用业务动作 label，而不是整段 Stagehand action policy / memory policy。

原因：
- 实验中已经能识别 `checkout_user_info_complete`、`payment_info_complete` 等状态，但后续动作会被 embedding 拉回较早的 `checkout` 节点，导致 PDDL precondition 过宽。
- source edge 表示“动作实际从哪里发生”，不应只由页面相似度决定；页面相似度只能辅助纠偏。
- embedding 应比较页面/业务状态，而不是比较重复的 Stagehand prompt 模板。

影响：
- 业务链路更接近真实执行轨迹，例如 `checkout -> checkout_user_info -> payment_info`，而不是多条边都从 `checkout` 发散。
- PDDL 更有机会生成正确前提，后续 `submit_order` 不应只依赖 `at_checkout`。
- 当前仍未做完整回放/DFS 栈；browser back 后的定位恢复后续还需要单独设计。

## 2026-08-01 - 探索阶段先稳定 domain，并避免同页面状态污染

更改：
- 新增 `compile_web_kobe_graph_to_domain` 和 CLI 命令 `web-kobe-domain-from-graph`，允许从 `WebKobeGraph` 只生成 `domain.pddl`，不要求指定 `goal_node`。
- `WebKobeExplorer` 在目标节点已经存在但 `planning_transition.post_facts` 与该节点已有 `PlanningState` 不兼容时，会生成状态变体节点，而不是把新的 facts 写回旧节点。
- 保留 `web-kobe-pddl-from-graph` 和 `web-kobe-pddl-smoke` 的 problem 生成能力，用作明确 start/goal 后的诊断和 SafeSym smoke。

原因：
- 当前项目仍处于探索建模阶段，主目标是收集网站业务状态、动作和 effects；`problem.pddl` 属于后续规划查询阶段，不应该强行绑定一次探索的临时目标。
- 实验中出现过同 URL/同页面壳被复用后，旧 `shopping` 节点被写入 `cart_has_items` 的污染。页面壳相同不代表业务状态相同。
- domain 可以先作为稳定的、可复用的 planner-facing 模型；problem 应该在用户任务、测试目标或 SafeSym 场景明确后再生成。

影响：
- 探索主产物更清晰：`graph.json`、`state_embeddings.json`、`domain.pddl` 优先；`problem.pddl` 只作为查询/smoke 产物。
- 同页面不同业务 facts 会拆成不同状态节点，降低 PDDL 初始态混入后续 facts 的风险。
- 后续扩大实验步数时，graph 状态边界会更干净，但仍需要继续观察节点数量是否膨胀。

## 2026-07-31 - 将业务节点命名 hint 放回 profile

状态命名方案已由 2026-08-09 的 VLM state label 设计替代：新探索由 Visual Affordance 可选提供 state label，本地仅做技术清洗；profile facts 不再派生节点 label。旧方案的字段和调用链已移除，历史 graph 仍按兼容规则读取。

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

## 2026-08-03 - 删除底层 selector / interactable explored 探索路径

更改：

- 删除旧动作选择模块：
  - `src/ai_web_explorer/grounded_web/llm_action_selector.py`
  - `src/ai_web_explorer/grounded_web/openai_action_selector.py`
- 删除旧 selector 相关测试和本地 fixture golden-path 测试。
- 从 `run_web_kobe_exploration` 中移除 `action_selector` / `selector_trace_path` 参数。
- 从 `WebKobeExplorer` 中移除低层 interactable fallback、`selection_traces` 和 interactable explored 标记调用。
- 从 `WebKobeGraphManager` 中删除 `mark_interactable_explored` / `interactables_for_node`。
- 更新项目结构和 overview 文档，明确低层 DOM interactables 只作为 node evidence / debug 信息，不再作为探索决策或 graph memory 单位。

原因：

- 当前架构已经明确：VLM 生成 business affordances，本地 graph / embedding memory 选择和去重，Stagehand 执行被选中的业务动作。
- 旧 selector 路径会把系统重新带回 selector/locator-driven exploration，与“底层操作交给 Stagehand”的方向冲突。
- `interactable_elements.explored` 会让 graph 层承担操作层细节，和后续业务节点/frontier 记忆模型不一致。

影响：

- 主探索链路不会在没有 business affordances 时回退去点击 DOM interactables。
- 旧 Web-KOBE Playwright selector smoke 能力被移除；如需恢复，可从 Git 历史找回。
- `interactable_elements` 不再输出到 canonical `graph.json` node；运行时 DOM interactables 如需保留，应进入 state summary、embedding matching 或 trace/debug artifacts。

## 2026-08-03 - 固定业务节点候选 frontier，停止 revisit 累积

更改：

- `WebKobeExplorer._record_source_business_affordances` 在当前业务节点已有 `business_affordances` 时直接复用旧 frontier，不再调用 VLM 重新生成候选。
- `WebKobeGraphManager` 在同一 node revisit / target merge 时不再追加新的 `business_affordances`；已有候选非空时保留第一次写入的候选，只有旧节点没有候选时才接收 incoming 候选。
- 新增回归测试，覆盖“已有节点候选不被 revisit 追加”和“已有 frontier 时不再次调用 VLM provider”两个行为。

原因：

- Practice Automated Testing Shopping 实验中，`cart_with_items` 节点因多次 revisit / target merge 从单轮候选累计到 12 个动作，导致 frontier 变成多次访问路径上的动作合集。
- business node 的 frontier 应表示首次观察到该业务状态时的稳定候选清单；后续探索应消费这张清单里的未尝试动作，而不是继续贴新动作。
- 如果同一页面壳下出现真正不同的业务能力，应由 planning facts / target matching 形成不同业务节点，而不是污染已有节点的 frontier。

影响：

- 单个业务节点的候选集合不会随 revisit 继续膨胀。
- `frontier_metrics.candidate_count` 更接近节点首次观察到的业务候选数量，后续 tried / no-op / failed 会在稳定清单上累积。
- checkout 推进排序仍需要后续单独优化；本次只修复候选累计问题，不改变排序策略。

## 2026-08-04 - 收紧 VLM 候选生成上限语义

更改：

- `business_affordance` prompt 明确 `max_actions` 是 upper bound，不是 quota；如果当前页面真实可执行业务动作少于上限，应返回更少动作。
- prompt 明确要求聚焦当前 active business surface；如果 modal、dialog、drawer、form、details view、table row、selected object 等 focused surface 打开，只返回该 surface 内动作和显式离开动作，不为了凑数加入背景页面控件。
- VLM 候选生成 prompt 不再携带 `profile` 和 `current_planning_facts`；profile facts / stages 后续只由本地 selector / policy 用于打分、去重和 planner-facing 语义对齐。
- 本地解析层对 VLM 返回的 `business_affordances` 强制按 `request.max_actions` 截断，防止模型超额返回。
- 新增测试覆盖 prompt 合同和解析层上限。

原因：

- Practice Automated Testing Shopping 实验中，商品详情 modal 状态实际强相关业务动作主要是 `add_to_cart` 和 `close_product_details`，但 VLM 仍返回满 5 个候选，把背景页的 `search_for_items`、`filter_products` 也放入该节点 frontier。
- 候选数量上限应防止候选池过大，而不是暗示 VLM 必须凑满数量。
- VLM 没有稳定 graph memory，不应消费 profile facts 或根据 profile stage 判断动作优先级；否则容易把“典型业务流程”误当成当前可见动作。
- frontier 质量应先由候选生成阶段控制；排序策略不应该承担过滤明显不属于当前业务上下文动作的全部压力。

影响：

- 新实验中商品详情等窄上下文节点可能只生成 2-3 个候选，而不是固定接近 5 个。
- 即使 VLM 超额返回，本地 graph frontier 也不会超过配置上限。
- 后续候选排序应在本地完成：如果业务动作预期变化或执行结果命中 profile facts / stages，再由本地 policy 给予更高分；同时继续加入 action family / no-op / repeated target 惩罚。
