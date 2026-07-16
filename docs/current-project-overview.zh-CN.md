# 当前项目说明

这份文档用于中文审阅。它说明当前项目在做什么、主线 pipeline 是什么、各模块怎么分工、哪些内容仍然是 SauceDemo/MVP 专用，以及下一阶段应该优先推进什么。

对应英文版：

```text
docs/current-project-overview.md
```

以后英文版主要用于代码上下文和 AI 接力，中文版主要用于人工审查项目方向。

## 项目目标

原始 `ai-web-explorer` 项目做的是：

```text
用浏览器和 LLM 辅助探索网站
-> 输出网页状态和动作构成的图
```

我们当前项目在这个基础上，把目标推进到 SafeSym 需要的“网页环境理解层”：

```text
真实网站
  -> 浏览器观察
  -> 抽象网页状态和动作
  -> 构建图结构
  -> 转换成 PDDL
  -> SafeSym 注入安全约束
  -> 规划器生成安全动作计划
```

更具体地说，我们不是要从零实现一个通用 web agent，而是要让 SafeSym 能理解未知网页环境：网页现在处于什么状态、有哪些动作可以做、动作会导致什么状态变化、哪些动作后续需要安全检查。

当前阶段优先使用 `local_checkout` 作为低噪音 golden-path fixture，并保留 SauceDemo 作为应用级回归和未来安全规则场景。它们都不是最终目标，而是用于证明端到端链路的受控目标。

核心研究问题是：

```text
如何观察一个网页应用，
把它的状态和可执行动作抽象成图，
再把这张图转换成 SafeSym 可以使用的规划模型？
```

## 当前主线 Pipeline

项目已经不再以旧的 FSM 路线为主。当前有一条新主线，以及一条应用级回归路线。

```text
当前通用主线：
  DOM-grounded Web-KOBE exploration
  -> 页面结构观察
  -> 状态事实和 typed delta
  -> ActionIntent / ActionExecutionResult / OutcomeEvaluation
  -> WebKobeExplorer
  -> WebKobeGraph
  -> WebKobeGraph-to-PDDL 投影
  -> 面向 SafeSym/PDDL 的 artifact

SafeSym 回归路线：
  SauceDemoAdapter
  -> GraphExplorer
  -> WebObservedGraph
  -> graph-derived PDDL
  -> SafeSym
```

新的通用探索代码应该通过下面这个包进入：

```text
src/ai_web_explorer/grounded_web/
```

`grounded_web` 是现在的核心探索边界，负责：

- DOM-grounded 网页观察；
- 浏览器动作抽象；
- 状态记录；
- WebKobeGraph 构建；
- ActionIntent 到具体浏览器动作的执行边界。

`safesym_bridge` 不应该再承载通用探索逻辑。它现在应该专注于：

- 消费 `grounded_web` 生成的图和数据结构；
- 做 SafeSym/PDDL 投影；
- 保留 SauceDemo 这类端到端回归适配；
- 保留必要的历史路线作为参考，但不扩展成新主线。

这个边界很重要。它让我们以后可以替换底层 web agent、Playwright backend、LLM/VLM 辅助模块，而不会推翻 SafeSym 对接层。

当前主线已经收束到 WebKobeGraph-to-PDDL 投影：使用 grounded Web-KOBE 探索得到的状态图，将成功且有观察意义的转移投影成简单 STRIPS `domain.pddl`，并通过显式 start/goal 节点生成具体 `problem.pddl`。这保持了 `grounded_web` 作为网页探索/观察层、`safesym_bridge` 作为面向规划器投影层的边界。

## 近期已经完成的进展

目前已经完成了几件关键整理工作：

1. 新主线已经抽到 `grounded_web`。

   `grounded_web` 现在包含 DOM 观察、动作提取、自动化后端、探索器、图结构、图管理器、Playwright backend、语义辅助和简单 agent。

2. `grounded_web` 与 `safesym_bridge` 已经解耦。

   `grounded_web` 不依赖 `safesym_bridge`；`safesym_bridge` 反过来消费 `grounded_web` 的结果。

3. 删除了 `safesym_bridge` 中一批纯兼容 shim。

   这些文件以前只是把 `grounded_web` 的类型重新导出，容易让模块边界变模糊。现在测试也已经迁移为直接依赖 `grounded_web`。

4. 当前验证状态良好。

   最近一次桥接层测试结果：

   ```text
   tests/safesym_bridge: 133 passed, 2 skipped
   ```

   当前测试套件已经做过一次主线收束：删除旧 `WebObservedGraph -> PDDL`
   单元测试、experimental capability graph sidecar 测试、legacy executor
   测试和 simple-agent facade 测试。默认保留 Web-KOBE/PDDL 主线测试，以及
   仍可能服务后续安全规则场景的 SauceDemo adapter/resolver/catalog 回归测试。

## Web-KOBE 风格探索主线

当前通用探索方向已经收束到 Web-KOBE 风格图结构。

它的目标不是记录网页里“有什么内容”，而是记录：

- 当前页面/状态能做什么；
- 哪些对象可以触发状态变化；
- 执行动作前后状态如何变化；
- 这些观察来自哪些 DOM/浏览器证据。

当前 CLI 示例：

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-from-graph \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl \
  --goal-node <goal_node_id>
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl_smoke \
  --goal-node <goal_node_id>
```

`web-kobe-pddl-smoke` 现在会检查探索得到的 WebKobeGraph 是否能生成非空、图上可达、内部一致的 PDDL artifact。smoke report 会包含 `pddl_static_consistency_ready` 和 `undeclared_predicates` 等字段，避免 action effect 静默引用 domain 中未声明的 predicate。这是 planning-readiness 验证，不是 SafeSym 安全规则触发验证。

更重要的是实际探索命令：

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6
```

这条路线会：

```text
读取真实页面
-> 提取 DOM 中真实可交互元素
-> 转换成 grounded browser actions
-> 用 Playwright locator 执行动作
-> 记录动作前后的状态变化
-> 写入 WebKobeGraph
```

LLM/VLM 后续可以参与动作选择、语义标注和验证，但 selector 和基础事实应尽量来自 DOM-grounded candidates，而不是让模型凭空生成。

当前 `grounded_web` 新增了动作闭环边界：

```text
ActionIntent
-> BrowserAction
-> Playwright 执行
-> before/after state
-> typed delta
-> OutcomeEvaluation
-> ActionExecutionResult
```

这个边界是正式接入 LLM 前的关键工程层。它会记录上层原本想做什么、最终选中了哪个具体 `BrowserAction`、Playwright 执行是否成功、观察到了哪些 typed state delta，以及结果是否符合预期。未来 LLM planner 应该输出 `ActionIntent`，由 `grounded_web` 负责解析、执行、观察和评估结果；LLM 不应该直接生成 selector，也不应该拥有浏览器执行细节。

如果动作执行成功但第一次观察没有发现 delta，动作闭环会在有限时间窗口内继续轮询观察状态，然后才返回 `no_observed_change`。这是观察等待策略，不是动作重试；默认不会再次执行浏览器动作。

## 当前自动化边界

我们希望复用现有 web agent 或浏览器自动化能力，但自己掌控探索目标和数据结构。

当前边界是：

```text
Reusable automation backend
  -> 负责操作浏览器
  -> click / fill / scroll / wait / navigate
  -> locator resolution
  -> browser/session handling

Web-KOBE / SafeSym explorer
  -> 负责探索策略
  -> 记录 before/after observation
  -> 推断状态 delta
  -> 构建 Web-KOBE / capability graph
  -> 后续导出 SafeSym/PDDL 可用 artifact
```

自动化后端接口位于：

```text
src/ai_web_explorer/grounded_web/automation_backend.py
```

当前具体实现是：

```text
src/ai_web_explorer/grounded_web/playwright_backend.py
```

它提供 Playwright-backed 浏览器操作能力，但不拥有探索策略。探索策略属于 `WebKobeExplorer`。

这样设计的好处是：以后如果我们接入现成 web agent，只需要把它封装成新的 `AutomationBackend`，不需要重写图结构和 SafeSym 对接。

## SimpleGroundedWebAgent

当前不依赖 LLM 的 baseline agent 位于：

```text
src/ai_web_explorer/grounded_web/simple_agent.py
```

它组合了：

- `AutomationBackend`
- `WebKobeExplorer`
- `WebKobeExplorationController`

它的作用是跑通最小闭环：

```text
观察页面
-> 找到 grounded candidates
-> 按简单策略执行尚未探索的动作
-> 记录 before/action/after delta
-> 写入 WebKobeGraph
```

它不是最终智能体，而是一个可测试的 baseline。后续 LLM/VLM 或现成 web agent 可以替换它的动作选择部分。

## 本地测试页面

当前推荐的第一个 golden-path target 是本地 checkout fixture：

```bash
python -m http.server 8000 --directory tests/fixtures/local_checkout
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6
```

选择本地 fixture 的原因：

- 不需要登录；
- 不受第三方网站变化影响；
- 没有 cookie banner 等干扰；
- 可以稳定测试商品、购物车、结账表单、订单完成等状态变化；
- 便于验证 DOM 提取、Playwright 执行、表单填写、状态观察、状态节点区分、PDDL smoke 是否连通。

这个 fixture 不是站点专用适配器，而是低噪音 shopping benchmark。它提供清楚的 DOM 和 `data-state` 证据，但 explorer 仍然走通用 grounded Web-KOBE 路径。

SauceDemo 仍然是重要的真实网站 smoke target，但它有登录门槛，所以应该在本地 fixture 稳定后再使用。

SauceDemo 示例：

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url https://www.saucedemo.com/ \
  --output outputs/saucedemo_web_kobe_graph.json \
  --app-name saucedemo \
  --steps 4
```

对于 `--app-name saucedemo`，当前 adapter 会复用已有 SauceDemo state observer 和 action profile，从而记录 login、add-to-cart、cart open、checkout start 等更有意义的步骤。

## 核心数据结构

### WebObservation

`WebObservation` 表示一个浏览器状态下的观察结果。

文件：

```text
src/ai_web_explorer/safesym_bridge/web_observation.py
```

它包含：

- `PageIdentity`：页面抽象身份、URL、标题；
- `ObservedFact`：页面上的结构化事实；
- `ObservationEvidence`：事实来自哪里；
- `interactables`：DOM-backed 可交互候选元素。

它的作用是把浏览器原始信息转换成规划系统能理解的稳定事实。

### StateSnapshot

`StateSnapshot` 是面向规划的紧凑状态快照。

文件：

```text
src/ai_web_explorer/grounded_web/models.py
```

它包含：

- `page_id`
- `url`
- `title`
- `signature`

`signature` 是当前状态事实和值的集合。它不是 PDDL 本身，而是项目内部的网页状态表示。

### DOM Interactable Candidate

DOM observer 会提取可见、可用的交互元素。

文件：

```text
src/ai_web_explorer/grounded_web/dom_observer.py
```

扫描对象包括：

```text
button
a[href]
input
textarea
select
[role="button"]
[role="link"]
[onclick]
[data-test]
```

候选元素会记录：

- 元素类型；
- locator；
- locator strategy；
- 可见名称；
- metadata。

注意：candidate 只是“可能可操作的控件”，还不是语义规划动作。

### WebKobeGraph

`WebKobeGraph` 是当前通用探索主线的核心图结构。

相关文件：

```text
src/ai_web_explorer/grounded_web/graph.py
src/ai_web_explorer/grounded_web/graph_manager.py
```

它用于记录：

- 页面/状态节点；
- 浏览器 grounded actions；
- 动作目标；
- before/after observation；
- observed deltas；
- evidence；
- 后续可用于 PDDL 的 hints。

长期看，未知网页应该优先通过 `WebKobeGraph` 进入 SafeSym/PDDL 投影；当前已经有文件级入口可以把探索得到的 `WebKobeGraph` JSON 转成简单 PDDL。

### WebObservedGraph

`WebObservedGraph` 是目前 SauceDemo 回归路线中的图结构。

文件：

```text
src/ai_web_explorer/safesym_bridge/observed_graph.py
```

它包含：

- 抽象网页状态节点；
- 语义动作边；
- 状态事实值；
- 动作前置条件；
- 推断 effects；
- 可交互元素。

它当前仍然是 SauceDemo `Graph -> PDDL -> SafeSym` 回归链路的重要部分。

### Effects

Effects 的历史 SauceDemo 路线通过比较动作前后的 state signature 推断；当前 Web-KOBE 主线则把观察到的 typed delta 和 schema delta 直接记录在 `WebKobeGraph` edge 上，再由 PDDL projector 投影成动作 effect。

文件：

```text
src/ai_web_explorer/safesym_bridge/effect_inferer.py
```

例子：

```text
before: cart_count = 0
after:  cart_count = 1
effect: set cart_count to 1
```

这很重要，因为长期目标是从真实观察中学习动作效果，而不是完全手写。

## SafeSym 如何接入

SafeSym 不负责探索网页。它接收规划模型，并在其中加入安全约束或安全检查动作。

当前 SauceDemo MVP 中的重要敏感动作是：

```text
order_place_confirm
```

这个动作表示确认下单。SafeSym 可以在这个动作前插入人工确认。

当前端到端链路是：

```text
Graph PDDL
  -> SafeSym compile_safe_pddl
  -> Fast Downward
  -> safe plan found
```

safe plan 中会包含类似下面的检查动作：

```text
check_information_verification_checkout_info_submit
check_human_confirmation_order_place_confirm
```

## 仍然是 SauceDemo 专用的部分

目前项目已经有端到端 MVP，但还不是通用 web planner。

以下内容仍然偏 SauceDemo：

- `login`、`inventory`、`checkout_overview` 等页面 ID；
- `cart_count`、`order_created` 等状态事实；
- `product_add_to_cart` 等语义动作；
- 动作前置条件；
- PDDL object list 和最终目标；
- rule-based resolver。

这是当前阶段可以接受的。我们的策略是先跑通链路，再逐步泛化。

## 历史路线

早期工作生成过 SafeSym-compatible FSM 输出。相关内容仍然会出现在旧设计文档和 artifact 中，但已经不是当前主线。

当前主线：

```text
WebKobeGraph -> PDDL artifact -> SafeSym / planner 消费
```

保留的应用级回归路线：

```text
WebObservedGraph -> SauceDemo PDDL / 回归支持 -> SafeSym 场景
```

历史路线：

```text
observed transitions -> FSM JSON -> SafeSym loader compatibility
```

旧的 `fixed` / `observed` FSM CLI 命令已经不是重点。现在图结构才是核心数据结构。

## 当前技术边界与不足

目前系统还有一些明确限制：

- 通用状态事实仍然有意保持简单，本地 fixture 依赖 `[data-state]` 降低早期验证噪音；
- DOM candidate extraction 已经比较通用，但动作选择和语义命名仍然偏规则；
- WebKobeGraph-to-PDDL projector 目前只输出很小的 STRIPS 子集；
- `web-kobe-pddl-smoke` 已经检查图上可达性和基础 PDDL 静态一致性，但还不是完整 PDDL parser，也没有真正调用外部 planner；
- 还没有对生成的 Web-KOBE PDDL artifact 跑最小 SafeSym planning smoke；
- 浏览器探索能力还比较窄，主要围绕 checkout-style 路径；
- 状态去重、恢复、泛化能力还没有成熟；
- 安全保证只适用于已观察并编译出的模型。

这些不是失败，而是下一阶段要解决的问题。

## 下一阶段方向

短期目标应该聚焦：

```text
让 PDDL artifact 更稳定地被 SafeSym / planner 消费
```

具体闭环是：

```text
local_checkout / 受控页面
-> grounded Web-KOBE 探索
-> WebKobeGraph
-> PDDL projector
-> PDDL smoke report
-> 最小 SafeSym / planner smoke
```

不要急着把它扩成能力全面的 web agent。当前更重要的是让“观察到的状态图 → PDDL artifact → SafeSym/planner 消费”这条主线站稳。更复杂的状态去重、恢复、PDDL 完整泛化和真实网站复杂度可以后置。

LLM/VLM 的建议使用位置：

- 用于动作语义理解；
- 用于从 DOM 候选中选择更有意义的动作；
- 用于给页面状态和能力命名；
- 用于辅助判断两个状态是否语义相近。

不建议让 LLM/VLM：

- 凭空生成 selector；
- 单独决定事实真值；
- 隐式掌控图结构；
- 替代可验证的浏览器观察。

## 重要文件

```text
src/ai_web_explorer/grounded_web/
  当前通用探索主线包。

src/ai_web_explorer/grounded_web/automation_backend.py
  浏览器自动化后端接口。

src/ai_web_explorer/grounded_web/playwright_backend.py
  当前 Playwright-backed 自动化实现。

src/ai_web_explorer/grounded_web/dom_observer.py
  DOM 可交互候选元素提取。

src/ai_web_explorer/grounded_web/graph.py
  WebKobeGraph 数据结构。

src/ai_web_explorer/grounded_web/explorer.py
  Web-KOBE 风格探索器。

src/ai_web_explorer/grounded_web/simple_agent.py
  当前无 LLM baseline agent facade。

src/ai_web_explorer/safesym_bridge/web_observation.py
  观察数据模型：facts、evidence、page identity。

src/ai_web_explorer/safesym_bridge/state_observer.py
  SauceDemo-specific 状态事实提取。

src/ai_web_explorer/safesym_bridge/observed_graph.py
  SauceDemo 回归路线中的 WebObservedGraph。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
  当前主线的 WebKobeGraph 到 PDDL 投影器。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
  WebKobeGraph PDDL artifact 的 planning-readiness 和静态一致性 smoke report。

docs/safesym-bridge.md
  SafeSym bridge 使用说明和命令参考。
```

## 给下一次对话的接力说明

如果开启新对话，建议先让 AI 阅读：

```text
docs/current-project-overview.md
docs/current-project-overview.zh-CN.md
```

然后要求它复述：

- 项目最终目标；
- 当前主线 pipeline；
- `grounded_web` 与 `safesym_bridge` 的边界；
- 最近完成的清理；
- 下一阶段要优先解决的问题。

默认工作方式：

```text
单智能体
省 token
不要使用 subagent / 多智能体，除非用户明确允许
```
