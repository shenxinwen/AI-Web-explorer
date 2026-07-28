# 当前项目概览

这份文档用于项目接力和阶段性决策。英文版
`docs/current-project-overview.md` 用于代码上下文和 AI 接力，中文版用于人工审阅。
当项目方向、架构边界或实验结论变化时，两份文档需要同步更新。

## 一句话目标

这个项目不是要做通用 web agent 产品，而是要服务 SafeSym：

```text
真实网站交互
  -> 观察动作前后的状态变化
  -> 构建 WebKobeGraph
  -> 抽象为 profile planning facts
  -> 投影成 planner-facing PDDL
  -> 交给 SafeSym 做解析、安全检查注入和规划验证
```

项目真正要解决的问题是：如何把网页交互变成稳定、可验证、可规划的状态图。
Stagehand、Playwright、VLM/LLM 和 embedding 都是工具或证据来源，不是图真相本身。

## 当前阶段判断

项目已经从“证明 task-guided checkout 链路可跑通”进入下一阶段：

```text
task-guided benchmark baseline
  -> bounded exploration V1
  -> profile-fact state modeling
  -> PDDL/SafeSym semantic consumption
```

我们不应该继续把主要时间花在让某个 checkout prompt 更会完成任务上。
下一阶段重点是：让系统真的具备基础探索能力，同时保持 PDDL/SafeSym 链路可消费。

当前最准确的定位是：

```text
有真实浏览器执行能力；
有 graph/PDDL/SafeSym 端到端链路；
有初步 embedding memory；
但还没有稳定的自由探索策略；
也还没有可靠的 profile fact verifier。
```

## 架构边界

### grounded_web

`src/ai_web_explorer/grounded_web/` 是通用网页探索层，负责：

- 浏览器观察和 DOM/截图/表单等证据采集；
- `AutomationBackend` 接口；
- Playwright 和 Stagehand 后端；
- before/after 状态记录；
- visual delta、structured delta 和未来 verifier；
- `WebKobeGraph` 的节点、边、planning state 和 transition 管理；
- exploration memory、embedding、frontier 相关能力。

它不应该包含 SafeSym-specific 规划逻辑，也不应该包含 SauceDemo-only 规则。

### safesym_bridge

`src/ai_web_explorer/safesym_bridge/` 是 planner/SafeSym 侧桥接层，负责：

- WebKobeGraph-to-PDDL 投影；
- PDDL smoke；
- SafeSym parser / safety injection / planner smoke；
- 必要的本地 fixture 和回归测试。

它不应该继续生长成通用探索 runtime。SauceDemo 应被视为 benchmark config，
不是主架构路径。

### Stagehand

Stagehand 的定位是：

```text
Stagehand = 候选动作发现 / 低层动作执行 / interaction trace
Web-KOBE = 状态观察 / 图结构 / planning facts / memory
SafeSym bridge = PDDL 投影 / 安全规则消费
```

Stagehand 可以辅助选择和执行动作，但不能直接决定：

- node identity；
- planning facts；
- PDDL predicates/effects；
- safety triggers；
- 探索是否完成。

## 图结构原则

当前图结构继续遵守这些原则：

1. `node` 表示可回到、可继续探索的页面/上下文状态。
2. `node.planning_state` 记录该节点已知的 profile facts，用于分析、frontier 和终止判断。
3. `edge` 表示一次动作或业务里程碑。
4. `edge.planning_transition` 记录动作前后的 profile fact 变化，是 PDDL action prediction 的主要来源。
5. PDDL 默认只能消费 graph location predicates 和预设 profile facts。
6. DOM/UI/schema facts 只能作为证据，不能默认进入 PDDL。
7. readable names 只是审阅辅助，不能作为运行时 identity。
8. embedding memory 只能辅助判断重复状态和动作选择，不能直接进入 PDDL。

已经完成的关键修正：

- PDDL action identity 由代码生成，避免 readable action name 重复导致 PDDL action 重名。
- PDDL 默认不再投影 `region_N_visible` 等 UI/schema facts。
- `planning_transition.added_facts` 已收紧，只记录相对 `pre_facts` 真正新增的 profile facts。
- `edge.planning_transition.pre_facts/added_facts/removed_facts` 已成为 PDDL action 映射的优先输入。
- 电商 profile 已区分 `checkout_user_info_complete` 和 `payment_info_complete`，
  同时保留 `checkout_info_complete` 作为 checkout flow 的 summary fact。
- embedding 配置已改成通用 `EMBEDDING_*`，不再依赖 Qwen-specific fallback。
- 初版 state summary、state embedding、exploration index 已加入。

## 当前实验结论

### SauceDemo task-guided baseline

SauceDemo 仍然是主要回归 benchmark。它验证过：

- Stagehand 可以作为真实浏览器动作后端；
- milestone-level graph 可以被构建；
- PDDL 可以生成；
- SafeSym 可以 parse/inject；
- 在允许 final order 的 benchmark 模式下，可以验证订单提交前的人类确认安全检查。

这个 baseline 证明的是受控 checkout 链路可跑通，不证明任意网站泛化能力。

### SauceDemo generic exploration latest

最新 generic exploration 实验路径：

```text
outputs/experiments/saucedemo/latest/
```

结果摘要：

- 使用 `web-kobe-stagehand-explore`；
- Stagehand 模型需要 `deepseek/deepseek-v4-flash`，裸 `deepseek-v4-flash` 会被 Stagehand v3 拒绝；
- 运行步数 `--steps 8`；
- graph 有 7 个节点、8 条边；
- 页面走到 `checkout-complete`；
- embedding records 有 6 条，维度 1024；
- PDDL smoke ready；
- SafeSym parse/inject/base/safe smoke ready。

但这次实验没有证明“真正自由探索”已经完成：

- 停止原因实际是达到 `max_steps=8`，不是 coverage 达成；
- 底层执行仍是 `business_milestone` 模式，每步只有一个虚拟动作 `advance_business_milestone`；
- Stagehand 是按“选择一个有用站点功能动作”的 generic prompt 推进了一条业务路径；
- 没有显式枚举几十个页面候选动作，也没有分支扩展或回溯；
- embedding 已触发，但只用于 prompt memory，没有触发 embedding-based node merge；
- 当未启用 visual delta 时，`planning_state.facts` 和 `planning_transition.added/removed_facts` 仍可能为空；
- PDDL/SafeSym 可以结构性消费，但语义上主要是 location/action path，不是 business-state transition。

客观结论：

```text
浏览器探索链路：可运行
embedding 存储：可运行
PDDL/SafeSym 结构消费：可运行
profile facts 语义链路：不足
自由探索能力：尚未成立
```

### Practice Automated Testing

站点：

```text
https://practiceautomatedtesting.com/shopping
```

最新有效结果是 partial checkout-flow success，并且 SafeSym 可以消费生成产物。

结果摘要：

- graph 有 1 个节点、5 条边；
- 4 条边可投影；
- 最终 facts 包含 `cart_has_items`、`checkout_started`、`checkout_info_complete`；
- PDDL smoke 可用；
- SafeSym parse/inject/base/safe smoke 可用；
- 没有到达 `order_review_ready` 或 `order_completed`。

暴露问题：

- payment 表单没有完全填完，但 VLM 过早判断 `checkout_info_complete`；
- Stagehand 后续动作选择不稳定；
- profile 粒度和 verifier 缺失会直接影响 PDDL 语义质量。

### TestDino Store

站点：

```text
https://storedemo.testdino.com/
```

实验结果是 partial success：

- 一轮实验能得到 `product_list_visible`、`cart_has_items` 并被 SafeSym 消费；
- guided prompt 反而可能更浅，出现 products 节点重复；
- 暴露出节点去重、状态抽象和 Stagehand 执行稳定性问题。

这个实验说明：更明确的 prompt 不一定带来更好的图结构，底层状态抽象仍是主要瓶颈。

## 当前主要问题

### P0：generic exploration 没有接上 profile facts

这是当前最大问题。

`web-kobe-stagehand-explore` 已经可以显式接入 `ecommerce_checkout` profile，
并可以复用已有 visual delta/VLM 链路。下一步要验证的是：在 generic / bounded
exploration 模式下，VLM candidate facts 能否稳定进入 `planning_state` 和
`planning_transition`，从而让 PDDL 表达 `cart_has_items`、`checkout_started`、
`payment_info_complete` 等业务状态变化。

下一阶段必须让 generic exploration 路径接入 profile-bounded state observation：

```text
before profile facts
  -> action
  -> after profile facts
  -> edge.planning_transition
  -> target node.planning_state
```

### P1：当前探索仍偏单路径任务推进

最新 SauceDemo generic run 的 prompt 是探索式的，但执行机制仍是 milestone-like：

```text
每步生成一个虚拟 business_intent 动作
  -> Stagehand 内部决定低层动作
  -> Web-KOBE 记录一个 edge
```

这还不是 OpenMobile/SEE 风格的探索，因为系统没有显式管理：

- 候选动作集合；
- 动作优先级；
- 重复惩罚；
- frontier；
- 回溯；
- coverage stop condition。

### P1：embedding memory 已接入，但能力还浅

embedding 已经能生成和保存状态向量。
当前用途是：

- 当前状态 summary 与历史 embedding 做相似检索；
- 如果判断为 revisit，把“已尝试动作/避免动作”写入 Stagehand prompt。

但目前它不负责：

- 直接合并节点；
- 修改 GraphManager 的 node identity；
- 进入 PDDL；
- 判断探索完成。

这符合“先低耦合接入”的原则，但后续需要明确 embedding memory 和 graph merge 的边界。

### P2：终止条件还是步数，不是覆盖率

generic exploration 当前主要靠 `max_steps` 停止。
这适合 smoke，但不适合作为真正探索系统。

后续至少需要基本终止指标：

- 当前 frontier 为空；
- 最近 N 步都是 no-op 或重复状态；
- 达到业务状态覆盖目标；
- 达到预算上限。

### P2：Stagehand 成功信号不可靠

trace 中可能出现 `backend_reported_success=false`，但页面确实发生变化。
当前更可靠的判断应该是 before/after observation，而不是 Stagehand 返回值。

短期保留原始 trace，长期需要对 Stagehand result 做归一化解释。

### P2：DeepSeek/Stagehand responseFormat warning

`deepseek/deepseek-v4-flash` 可以执行，但会出现：

```text
responseFormat setting is not supported by this model
```

短期可记录为非阻塞异常。长期如果依赖结构化 Stagehand 输出，需要重新评估模型/接口。

### P3：Verifier 还没有真正建立

目前 profile facts 仍主要来自轻量结构规则或 VLM/LLM candidate。
未来 verifier 应该综合：

- DOM；
- URL；
- visible controls；
- form values；
- screenshot/VLM summary；
- profile evidence hints；
- before/after facts。

Verifier 的目标不是替代 profile，而是判断 candidate facts 是否能升级为 planner-facing truth。

## 下一阶段方向

### 目标：bounded exploration V1

下一阶段不是继续优化 checkout task prompt，而是实现一个最小可用的探索闭环：

```text
观察当前状态
  -> 生成候选动作
  -> 用 graph memory / embedding memory / 重复惩罚选择一个动作
  -> 执行动作
  -> 观察 before/after profile facts
  -> 更新 node / edge / planning_transition
  -> 根据 frontier 或预算决定是否继续
```

第一版不追求完整覆盖率，只要具备基本功能：

- 每步从多个候选动作中选一个；
- 避免明显重复和 no-op；
- 记录为什么选择这个动作；
- 能从 graph 中看出哪些动作已尝试；
- 保持 PDDL/SafeSym 可消费；
- 保持各模块低耦合。

### 设计取向

我们可以贴近 OpenMobile/SEE 的思想，但不要过度复刻论文系统：

- 用 graph 作为主记忆；
- 用 embedding 做相似状态索引；
- 用候选动作和 frontier 控制探索；
- 用 profile facts 作为 planner-facing 状态；
- 用失败/no-op edge 作为诊断和负样本；
- 先做单站点短链路，再扩展多网站。

### 短期优先级

1. 验证 generic exploration 的 visual delta/profile facts 链路。
2. 把 Stagehand 从单个虚拟 milestone 推向候选动作模式，优先评估 `observed_action` 是否可用。
3. 明确 embedding memory 的职责：相似检索和重复惩罚，不直接进入 PDDL。
4. 给每轮 experiment report 增加 stop reason、prompt mode、memory hit、facts count。
5. 再跑 SauceDemo、Practice Automated Testing、TestDino，比较 task-guided 和 bounded exploration 的差异。

## 实验管理规则

每个网站只保留最新一次有效实验结果：

```text
outputs/experiments/<site_name>/latest/
```

每轮实验报告至少记录：

- 命令和模型；
- prompt mode；
- stop reason；
- 是否是 task-guided / generic / bounded exploration；
- graph 节点/边数量；
- node merge/visit_count 情况；
- embedding records 和 memory hit 情况；
- final planning facts；
- PDDL smoke 是否 ready；
- SafeSym 是否可消费；
- 异常和失败边；
- 截图上可人工验证的状态变化；
- 客观结论：结构链路、语义链路、探索能力分别是否成立。

## 当前判断

项目完成得不错，但不能高估。

已经成立的是：

- 真实网页到 graph 的工程链路；
- embedding 配置和存储；
- PDDL 投影；
- SafeSym smoke；
- 多网站 partial success 的实验管理方式。

尚未成立的是：

- 稳定的 profile fact state observation；
- 真正的候选动作探索策略；
- 基于 coverage/frontier 的终止条件；
- embedding-based revisit 对探索行为的显著影响；
- verifier-backed planner truth。

下一阶段的核心不是“让模型更聪明”，而是把探索控制权逐步拿回到 Web-KOBE：

```text
Stagehand 负责看见和执行；
Web-KOBE 负责记忆、选择、状态和规划语义；
SafeSym 负责消费 PDDL 并验证安全约束。
```

## 重要文件

```text
src/ai_web_explorer/grounded_web/
  通用网页观察、动作执行抽象、图构建和 planning state 管理。

src/ai_web_explorer/grounded_web/business_profile.py
  BusinessFlowProfile 和 planning facts 定义。

src/ai_web_explorer/grounded_web/experiment_plan.py
  ExperimentPlan 和 ExperimentStep，用于配置化 business-step 实验。

src/ai_web_explorer/grounded_web/graph.py
src/ai_web_explorer/grounded_web/graph_manager.py
  WebKobeGraph、node、edge、planning_state、planning_transition。

src/ai_web_explorer/grounded_web/explorer.py
  主探索循环，负责 before/after、edge、planning delta 和 memory context。

src/ai_web_explorer/grounded_web/stagehand_backend.py
src/ai_web_explorer/grounded_web/stagehand_prompt.py
  Stagehand 后端和 prompt。generic exploration 可选择 business_milestone 或 observed_action 执行模式。

src/ai_web_explorer/grounded_web/state_summary.py
src/ai_web_explorer/grounded_web/state_embedding.py
src/ai_web_explorer/grounded_web/embedding_provider.py
src/ai_web_explorer/grounded_web/exploration_index.py
  状态摘要、embedding provider、相似状态查询和探索记忆。

src/ai_web_explorer/grounded_web/visual_delta.py
src/ai_web_explorer/grounded_web/openai_visual_delta.py
  before/after 截图变化总结和候选 planning facts。

src/ai_web_explorer/grounded_web/planning_fact_verifier.py
  当前轻量 verifier，后续需要扩展。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
  WebKobeGraph-to-PDDL 投影主逻辑。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py
  PDDL 和 SafeSym smoke。

docs/safesym-bridge.md
  SafeSym bridge 命令和实验参考。
```

## 接力注意事项

新会话开始前，应先确认这些点：

- 项目服务 SafeSym，不是通用 web-agent 产品；
- 当前阶段正在从 task-guided benchmark 转向 bounded exploration；
- PDDL 只能消费 node identity 和 profile planning facts，不能消费 UI/schema facts；
- Stagehand 是候选动作/执行/trace 来源，不是状态真相；
- 最新 generic exploration 已能接入 business profile、VLM visual delta 和 `observed_action` 模式；
- 当前最大风险是 bounded exploration 策略还未成型、verifier 缺失、候选动作质量仍需实验验证；
- 下一步优先做 bounded exploration V1 的最小闭环。
