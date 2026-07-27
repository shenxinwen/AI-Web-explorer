# 当前项目概览

这份文档用于项目接力和阶段性决策。英文版
`docs/current-project-overview.md` 用于代码上下文和 AI 接力，中文版用于人工审阅。
当项目方向、架构边界或实验结论变化时，两份文档需要同步更新。

## 一句话目标

这个项目不是要做一个通用 web agent 产品，而是要服务 SafeSym：

```text
真实网站交互
  -> 观察动作前后的状态变化
  -> 构建 WebKobeGraph
  -> 投影成 planner-facing PDDL
  -> 交给 SafeSym 做解析、安全检查注入和规划验证
```

项目真正有价值的部分是：

- 如何把网页交互抽象成稳定的状态图；
- 如何把动作造成的变化表示成 profile planning facts；
- 如何把图和状态变化投影到 PDDL；
- 如何让 SafeSym 消费这些模型并插入安全检查。

Stagehand、Playwright、VLM/LLM 都是工具和证据来源，不是最终的图真相来源。

## 当前主线

当前主线是 task-guided partial website modeling：

```text
真实网页
  -> grounded observation
  -> Stagehand/Playwright 执行动作
  -> before/after observation
  -> visual/structured delta
  -> profile planning facts
  -> WebKobeGraph
  -> PDDL
  -> SafeSym
```

短期我们不追求自由探索整个网站，而是先用业务目标引导探索，验证完整链路是否稳定。
以电商 checkout 为例，当前目标路径是：

```text
session setup / login
  -> product selection
  -> cart
  -> checkout information
  -> order review
  -> pending sensitive order placement
```

未来会逐步向探索式覆盖扩展，但现在必须先把状态抽象、图结构和 PDDL 映射做稳。

## 架构边界

### grounded_web

`src/ai_web_explorer/grounded_web/` 是通用网页探索层，负责：

- 浏览器观察和 DOM/截图/表单等证据采集；
- `AutomationBackend` 接口；
- Playwright 和 Stagehand 后端；
- before/after 状态记录；
- visual delta 和 structured delta；
- `WebKobeGraph` 的节点、边和 planning state 管理；
- LLM/VLM/Stagehand trace 的证据边界。

它不应该包含 SafeSym-specific 规划逻辑，也不应该包含 SauceDemo-only 规则。

### safesym_bridge

`src/ai_web_explorer/safesym_bridge/` 是 planner/SafeSym 侧桥接层，负责：

- WebKobeGraph-to-PDDL 投影；
- PDDL smoke；
- SafeSym parser / safety injection / planner smoke；
- 必要的本地 fixture 和回归测试。

它不应该继续生长成通用探索 runtime。之前残留的 SauceDemo-specific adapter/catalog/resolver
已经移除，SauceDemo 现在应被视为 benchmark config，而不是主架构路径。

### Stagehand

Stagehand 的定位是：

```text
Stagehand = 动作发现 / 动作执行 / 低层交互 trace
Web-KOBE = 状态观察 / 图结构 / planning facts
SafeSym bridge = PDDL 投影 / 安全规则消费
```

Stagehand 返回的自然语言描述可以作为证据，但不能直接决定：

- node identity；
- planning facts；
- PDDL predicates/effects；
- safety triggers；
- 任务是否真正成功。

我们现在已经把 `Thinking mode does not support this tool_choice` 视为后端异常：
如果页面或 planning facts 发生了可观察变化，边可以被标记为
`succeeded_with_observed_change`，同时保留 Stagehand 原始失败信息。

## 图结构原则

当前图结构需要遵守以下原则：

1. `node` 表示可回到、可继续探索的页面/上下文状态。
2. `node.planning_state` 记录该节点聚合看到过的 profile facts，用于分析、终止判断和未来 frontier 选择。
3. `edge` 表示一次具体动作或业务里程碑。
4. `edge.planning_transition` 记录这次动作开始前后的事实变化，是 PDDL action prediction 的主要来源。
5. PDDL 默认只能消费 graph location predicates 和预设 profile facts。
6. DOM/UI/schema facts 只能作为证据留在图里，不能默认进入 PDDL。
7. readable names 只是辅助审阅，不能作为运行时 identity。

目前已经完成的关键修正：

- PDDL action identity 由代码生成，避免 LLM-readable action name 重复导致 PDDL action 重名。
- PDDL 默认不再投影 `region_N_visible` 等 UI/schema facts。
- `planning_transition.added_facts` 已收紧，只记录相对 `pre_facts` 真正新增的 profile facts。
- `edge.planning_transition.pre_facts/add_facts/remove_facts` 已成为 PDDL action 映射的优先输入。

## 当前实验状态

### SauceDemo

SauceDemo 仍然是主要回归 benchmark。它验证过：

- Stagehand 可以作为真实浏览器动作后端；
- milestone-level graph 可以被构建；
- PDDL 可以生成；
- SafeSym 可以 parse/inject；
- 在允许 final order 的 benchmark 模式下，可以验证订单提交前的人类确认安全检查。

注意：SauceDemo 证明的是受控 benchmark 链路可跑通，不证明任意网站泛化能力。

### Practice Automated Testing

站点：

```text
https://practiceautomatedtesting.com/shopping
```

最新有效实验结果是 partial checkout-flow success，并且 SafeSym 可以消费生成产物。

结果摘要：

- graph 有 1 个节点、5 条边；
- 4 条边可投影；
- 最终 facts 包含 `cart_has_items`、`checkout_started`、`checkout_info_complete`；
- PDDL smoke 可用；
- SafeSym parse/inject/base/safe smoke 可用；
- 没有到达 `order_review_ready` 或 `order_completed`。

没有完成支付/下单的原因：

- 实验安全边界要求不要 place final order，最多停在 order review / checkout overview；
- 页面上 payment 表单没有完全填完，但 VLM 过早判断了 `checkout_info_complete`；
- 第 5 步 Stagehand 选择点击购物车按钮，没有继续填写支付字段或进入 review；
- before/after 截图无变化，所以该边被记录为 `failed_execution`。

这个实验说明跨站链路已有价值，但也暴露出 checkout profile 粒度太粗。

### TestDino Store

站点：

```text
https://storedemo.testdino.com/
```

实验结果是 partial success：

- 一轮实验能得到 `product_list_visible`、`cart_has_items` 并被 SafeSym 消费；
- 另一轮 guided prompt 反而更浅，出现 products 节点重复；
- 暴露出节点去重、状态抽象和 Stagehand 执行稳定性问题。

这个实验说明 prompt 更明确不一定带来更好图结构，底层状态抽象仍是主要瓶颈。

## 当前主要问题

### 1. Profile facts 粒度仍然不够好

当前 `checkout_info_complete` 过粗，把联系信息、地址信息和支付信息混在一起。
这会导致系统以为 checkout 信息已完成，但网页实际还不能进入 order review。

短期建议把电商 profile 拆得更清楚，例如：

```text
checkout_contact_info_complete
checkout_shipping_info_complete
payment_info_complete
order_review_ready
order_place_pending_sensitive
order_completed
```

这不是为了设计通用 schema，而是为了让 profile facts 更符合 SafeSym/PDDL 需要理解的业务状态。

### 2. Verifier 还没有真正建立

目前我们暂时信任 profile-bounded VLM/LLM candidate facts，用来跑通链路。
这适合 MVP，但不能长期作为图真相。

未来 verifier 应该综合：

- DOM；
- URL；
- visible controls；
- form values；
- screenshot/VLM summary；
- profile evidence hints；
- before/after facts。

Verifier 的目标不是替代 profile，而是判断哪些 candidate facts 可以升级为 planner-facing truth。

### 3. 节点去重和状态身份仍然偏弱

当前 node identity 仍偏页面/上下文级别，不足以稳定地区分：

- 同一页面上 cart 空/非空；
- checkout 表单填了一半/填完；
- 产品列表不同交互后的等价状态；
- modal 打开/关闭。

我们暂时不做大改。原则上：

- `node.planning_state` 保留当前上下文已知 profile facts；
- `edge.planning_transition` 表示动作引发的变化；
- 后续需要在 node merge 策略中更明确哪些 facts 会影响节点等价性。

### 4. 重复动作和 no-op edge 还需要处理

现在可能出现：

- 同一个动作重复尝试；
- Stagehand 选择无效动作；
- 页面无变化但仍产生 trace；
- 已经存在的 fact 被重复加入 transition。

我们已经先修了最后一项：`planning_transition.added_facts` 不再记录已经存在的 facts。
后续还需要讨论：

- 是否在 graph 层跳过 no-op edge；
- 是否在 frontier 层避免重复动作；
- 是否保留 failed/no-change edge 作为负样本。

### 5. 探索覆盖率还不是当前重点

自由探索很容易状态爆炸。当前更合理的阶段目标是：

```text
先用 task-guided benchmark 验证多网站链路
  -> 丰富 profile facts
  -> 稳定 verifier 和 PDDL projection
  -> 再考虑 frontier/replay/backtracking 提升覆盖率
```

提高覆盖率时，应优先考虑业务状态覆盖，而不是点击所有 DOM 元素。

## 近期方向

### P0：继续多网站 task-guided 实验

目标是验证图结构、profile facts 和 PDDL/SafeSym 链路是否能在不同网站上工作。

每个网站要单独保存实验结果，不覆盖历史目录：

```text
outputs/experiments/YYYY-MM-DD/<site_name>/run_XXX/
```

每轮实验结束后记录：

- 是否到达目标状态；
- graph 节点/边数量；
- projectable edges；
- final planning facts；
- PDDL smoke 是否 ready；
- SafeSym 是否可消费；
- 异常和失败边；
- 截图上可人工验证的状态变化。

### P1：收紧电商 profile facts

优先解决 `checkout_info_complete` 过粗的问题。
这会直接影响 Practice Automated Testing 这类网站能否正确到达 order review。

### P2：设计 verifier 接口

Verifier 可以在多网站实验之后引入，但现在设计时要给它留位置。
它应该接收 candidate facts 和多源证据，输出 verified/uncertain/rejected。

### P3：处理重复动作和 no-op transition

先保留失败边作为实验诊断证据。
等我们确认哪些 no-op 对 SafeSym 有价值后，再决定是否在图层过滤。

### P4：探索覆盖率

短期不做完整探索系统。
后续方向是 business-state coverage，而不是 raw click coverage。

## 当前判断

项目现在处在一个不错但不成熟的阶段：

- 已经有从真实网站到 SafeSym 的完整链路；
- 已经能在不止一个网站上产生可消费产物；
- 已经清理掉部分站点耦合和 PDDL 泄露问题；
- 但状态理解仍然浅，profile facts 和 verifier 是最大风险；
- Stagehand 能提供行动能力，但不能替代项目自己的状态建模。

换句话说：链路已经打通，接下来重点不是“让 agent 更会点网页”，而是让图结构和状态事实更可信、更可规划、更能被 SafeSym 稳定消费。

## 重要文件

```text
src/ai_web_explorer/grounded_web/
  通用网页观察、动作执行抽象、图构建和 planning state 管理。

src/ai_web_explorer/grounded_web/business_profile.py
  BusinessFlowProfile 和 planning facts 定义。

src/ai_web_explorer/grounded_web/graph.py
src/ai_web_explorer/grounded_web/graph_manager.py
  WebKobeGraph、node、edge、planning_state、planning_transition。

src/ai_web_explorer/grounded_web/explorer.py
  主探索循环。

src/ai_web_explorer/grounded_web/stagehand_backend.py
src/ai_web_explorer/grounded_web/stagehand_prompt.py
  Stagehand 后端和业务里程碑 prompt。

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
- 当前阶段是 task-guided partial graph，不是完整网站探索；
- PDDL 只能消费 node identity 和 profile planning facts，不能消费 UI/schema facts；
- Stagehand 是执行器和 trace 来源，不是状态真相；
- 当前最大风险是 profile facts 粒度和 verifier 缺失；
- 下一步优先做多网站实验和电商 profile facts 收紧。
