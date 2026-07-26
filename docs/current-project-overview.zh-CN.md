# 当前项目说明

这份文档用于人工审阅项目方向。英文版
`docs/current-project-overview.md` 用于代码上下文和 AI 接力。每次项目方向变化时，
两份文档都要同步更新。

## 项目目标

这个项目不是要做一个能力全面的通用 web agent。

项目目标是服务 SafeSym：把真实网页交互转成规划器可以消费的模型。

```text
真实网站
  -> 浏览器观察和动作执行
  -> WebKobeGraph
  -> Web-KOBE PDDL 投影
  -> SafeSym parser / safety injection / planner artifacts
```

核心研究问题是：

```text
如何探索一个网页应用，
观察动作会导致什么变化，
把这些变化抽象成 planning facts，
再编译成 SafeSym 可以注入安全检查的规划模型？
```

项目真正有价值的部分是状态图和规划模型，而不是底层网页操作能力。现有浏览器自动化
或 web-agent 工具能帮上忙时应该复用，但状态抽象、图构建、PDDL 投影和 SafeSym 语义
必须由本项目掌控。

## 主线 Pipeline

当前主线是：

```text
真实网页
  -> grounded observation
  -> candidate action discovery/selection
  -> 通过 AutomationBackend 执行浏览器动作
  -> before/after observation
  -> schema_delta / typed_delta / planning_delta
  -> WebKobeGraph
  -> PDDL artifacts
  -> SafeSym / planner 消费
```

当前图应该被视为 task-guided partial website model，而不是完整网站模型。短期探索
策略是 business-flow-guided：

```text
login 或 session setup
  -> product selection
  -> cart
  -> checkout information
  -> order review
  -> pending sensitive order placement
```

推进主任务时，explorer 应记录当前节点上可用但没有执行的动作，作为未来的 frontier
actions。通过 replay、snapshot 或 backtracking 执行这些 frontier 的能力暂时延后，
等状态观察更可靠之后再做。

## 架构边界

### grounded_web

`src/ai_web_explorer/grounded_web/` 是通用网页探索层。

它负责：

- DOM 和浏览器 grounded observation；
- candidate action 表示；
- 自动化后端接口；
- before/after 状态记录；
- typed delta 和 schema delta；
- WebKobeGraph 构建；
- 运行时稳定的图身份，以及人类可读的语义命名；
- LLM/Stagehand 辅助选择或执行时的 trace 边界。

它不应该包含 SafeSym-specific 规划逻辑，也不应该包含 SauceDemo-only 业务规则。

### safesym_bridge

`src/ai_web_explorer/safesym_bridge/` 消费图和观察产物。

它负责：

- WebKobeGraph-to-PDDL 投影；
- SafeSym smoke 集成；
- planner-facing artifacts；
- local checkout 和 SauceDemo 回归；
- 必要的应用专用 adapter、observer 和 action catalog。

它不应该生长成通用探索 runtime。

### AutomationBackend

浏览器操作通过这个接口进入：

```text
src/ai_web_explorer/grounded_web/automation_backend.py
```

当前具体后端：

```text
src/ai_web_explorer/grounded_web/playwright_backend.py
src/ai_web_explorer/grounded_web/stagehand_backend.py
```

backend 负责操作浏览器。Web-KOBE 层负责图，以及这次状态转移的意义。

## 图身份与命名

图身份和人类可读命名要分开处理。

运行时身份由确定性代码负责：

```text
node_id
edge_id
BrowserAction.semantic_id
BrowserAction.locator
```

这些字段可以驱动节点合并、动作执行、trace 对齐和 PDDL 投影。LLM/VLM provider
不应该重写它们。

人类可读命名是带来源的辅助注释：

```text
WebKobeNode.node_label
WebKobeNode.state_summary
BrowserAction.action_label
BrowserAction.canonical_action_name
naming_provenance
```

这些字段用于让图更容易审阅，也可以在后续帮助 PDDL 映射层选择 planner-facing
动作名。它们不是图身份。启用 DeepSeek semantic naming 时，它只写这些可读字段。

## 当前完成情况

项目已经有端到端 MVP，但还不是成熟的通用网页状态建模系统。

已经完成并验证：

- `WebKobeGraph` 是新工作的主图结构；
- `BusinessFlowProfile` 和 `PlanningDelta` schema 已经存在，用于 profile-guided
  planning-state abstraction；
- `WebKobeEdge` 可以承载 candidate 和 verified planning deltas；
- 最小版 structured `PlanningFactVerifier` 可以从已有 state signature 中推导
  verified planning deltas；
- 当提供 business profile 时，`WebKobeExplorer` 可以把 profile-verified
  `PlanningDelta` 记录到已执行 edge 上；
- 当自动化后端支持截图时，`WebKobeExplorer` 可以可选采集 before/after screenshots；
- 模型无关的 visual delta summarizer 可以把截图证据转成 candidate planning facts，
  但不会验证这些 facts；
- OpenAI visual delta provider 已通过独立 OpenAI vision 配置接入；它属于观察层，
  与 Stagehand 隔离；
- Stagehand SauceDemo smoke 可以通过 `--openai-visual-delta`、
  `--visual-delta-model` 和 `--screenshot-dir` 可选启用 OpenAI visual delta；
- `WebKobeNode` 和 `BrowserAction` 已经把运行时身份与可读命名分开。
  `node_id`、`edge_id`、`semantic_id` 和 locator 仍然是确定性的执行/投影锚点；
  `node_label`、`state_summary`、`action_label`、`canonical_action_name` 和
  `naming_provenance` 是可选的诊断或投影辅助字段；
- DOM 和 Stagehand candidates 会提供轻量级基础命名证据。Stagehand SauceDemo smoke
  可以通过 `--deepseek-semantic-naming` 和 `--semantic-naming-model` 可选启用
  DeepSeek semantic naming；它使用已配置的 DeepSeek/OpenAI-compatible 文本接口，
  不改变运行时 ID、selector、状态 facts 或 PDDL effects；
- business-milestone 边现在可以基于 VLM 的 `visual_change_summary` 做 transition-level
  LLM 命名。这是通用命名步骤，不是电商 action mapping 表。它只要求输出简洁的
  lower_snake_case 业务转移名，并只影响可读 action 字段和 PDDL action 命名优先级；
- DOM/HTML 抽取仍然属于通用证据层。它应当用于支持或质疑 profile facts，而不是被
  站点专用 observer 取代；
- 旧的自研通用动作执行层已经移除；
- Playwright 仍用于受控 fixture 和 fallback 操作；
- Stagehand 已作为真实站点动作发现/执行后端接入；
- 主线 Stagehand benchmark 路径现在使用通用 grounded Playwright adapter 和电商级
  任务指导，不应自动启用 SauceDemo-specific observer 或静态 action catalog；
- Stagehand 电商任务 prompt 已拆成 domain guidance、benchmark context、
  action policy 和 safety boundary。SauceDemo 凭据和 checkout 数据属于 benchmark
  context，可以通过 smoke 命令配置，不应写进可复用的 domain guidance；
- 电商 Stagehand smoke 现在默认采用 business-milestone 执行边界：每个图 step
  要求 Stagehand 推进一个有意义的 checkout 业务里程碑，低层 click/fill 只留在
  edge trace 中，不直接成为 planner-facing graph edge；
- 推荐使用 benchmark-driven 的电商 Stagehand smoke 入口：
  `web-kobe-ecommerce-stagehand-smoke --benchmark saucedemo`。旧的
  `web-kobe-saucedemo-stagehand-smoke` 命令保留为兼容 wrapper，方便已有脚本继续使用；
- WebKobeGraph 可以投影成 PDDL；
- PDDL 投影当前会把 candidate 和 verified planning-delta facts 都视作可信 effects，
  用于先跑通 VLM/LLM-to-PDDL 端到端链路；
- PDDL 投影现在会区分唯一的 planner action identity 和可读业务标签。投影出的 action
  name 由代码生成，采用稳定的 `edge_###_<business_suffix>` 形式，避免 LLM 可读标签重复
  导致 PDDL action 重名；
- PDDL 投影默认只使用 planner-facing facts：图位置 predicates 和来自 `PlanningDelta`
  的 profile/planning facts。DOM/control `observed_delta` facts 保留为图上的证据，不再
  默认成为 PDDL predicates；
- planning delete effects 会保守投影：被删除的 planning facts 会同时作为 action
  precondition，从而让生成模型保持在当前 Fast Downward smoke 期望的 STRIPS 片段内；
- 生成的 PDDL 可以做图可达性和静态一致性检查；
- PDDL smoke diagnostics 现在会报告 projected action names、duplicate action names、
  observed/control fact projection，以及没有匹配 precondition 的 delete effects；
- SafeSym 可以 parse/inject 生成的 PDDL。下一次实验应在这轮投影层 hardening 后重新跑
  Fast Downward base/safe solve。

最近一次保留测试的状态：

```text
all retained tests: 192 passed, 2 skipped
```

Playwright browser tests 在 restricted sandbox 中可能因为浏览器 spawn 权限失败。
在这种环境里运行时需要外部执行权限。

## 已验证链路

### SauceDemo LLM Checkout Smoke

应用专用的 SauceDemo LLM smoke 完成过五步 checkout 路径：

```text
product_add_to_cart
  -> cart_open
  -> cart_checkout_start
  -> checkout_info_submit
  -> order_place_confirm
```

图到达 `checkout_complete`，投影出的 PDDL 可以被求解，SafeSym 会在下面两个动作前
插入安全检查：

```text
checkout_info_submit
order_place_confirm
```

插入的检查动作是：

```text
check_information_verification_checkout_info_submit
check_human_confirmation_order_place_confirm
```

### Stagehand SauceDemo Graph Smoke

Stagehand 已经作为本地浏览器操作后端验证过。它通过 CDP 连接到 Web-KOBE 正在观察的
同一个 Playwright browser。

在 `.env` 配置好本地 Stagehand 和用户模型 key 后，真实 SauceDemo run 用 10 个
Stagehand-backed 低层动作到达 `checkout_overview`：

```text
fill username
  -> fill password
  -> click Login
  -> add Sauce Labs Backpack to cart
  -> open cart
  -> click Checkout
  -> fill first name
  -> fill last name
  -> fill postal code
  -> click Continue
```

得到的 WebKobeGraph 有 11 个节点和 10 条边。PDDL smoke 报告
`planning_ready=True`，没有 undeclared predicates；Fast Downward 能求出与真实动作
序列一致的计划。

对于 SauceDemo 测试站点，Stagehand smoke 现在还有显式的 `--allow-final-order`
模式。该模式允许 runner 点击 `Finish` 并到达 `checkout_complete`，用于验证完整的
订单确认安全注入链路。默认模式仍停在 checkout overview。

当前已验证的 final-order run 用 11 个 Stagehand-backed 状态转移到达
`checkout_complete`。生成的 PDDL 会把最后的低层点击投影成 `order_place_confirm`；
SafeSym 使用 `configs/constraint_rules.json` 时会插入：

```text
check_human_confirmation_order_place_confirm
```

注入 smoke 应使用 `constraint_rules.json`。`safety_rules.json` 主要用于风险标注，
不包含 check action 注入配置。

这说明真实站点链路已经验证到图构建、PDDL 投影和外部 planner 消费。但它还不能证明
我们已经有鲁棒的通用网页状态理解能力。

### Stagehand Business-Milestone Smoke

当前电商 Stagehand 实验使用 `business_milestone` backend 模式。每个图 step 都通过
bounded `agentExecute` 要求 Stagehand 推进一个有意义的 checkout 业务里程碑，Web-KOBE
只在里程碑前后各观察一次。

最新 SauceDemo final-order run 产生了更接近业务流程的图：

```text
login/product listing
  -> add product to cart
  -> open cart
  -> start checkout
  -> submit checkout information / reach order review
  -> place order / reach checkout complete
```

这次 run 到达了 `checkout_complete`，有 6 条 projectable business transitions。在
planner-facing projection hardening 之前，SafeSym parse/inject 可以消费生成的 PDDL，
但 Fast Downward solve 暴露了投影层问题：可读 action name 重复，以及 delete effect
删除了 precondition 中没有建立为真的 fact。

这次 run 暴露的注意点：

- Stagehand `agentExecute` 实际完成了有用的浏览器操作，但返回 `success=false`，错误为
  `Thinking mode does not support this tool_choice`。Web-KOBE 现在会把 backend 原始
  返回保存在 metadata 中，同时允许明确的状态变化决定图 transition 是否成功；
- planner-facing action identity 现在由代码唯一化；LLM transition naming 只作为可读
  suffix；
- PDDL 投影现在优先使用 profile/planning facts，并把低层 DOM/control predicates 保留为
  证据，而不是默认 planner-facing facts；
- runner 在 `order_completed` 后还需要更强的终止条件，避免在完成页多尝试一次无变化动作。

## Stagehand 接入定位

Stagehand 应该被理解为：

```text
Stagehand = 动作发现 / 动作执行证据
Web-KOBE observer = 状态事实和 before/after delta
WebKobeGraph/PDDL/SafeSym = 项目自己掌控的规划模型
```

Stagehand 的描述可以作为“它尝试做了什么”的证据，但它不是以下内容的真相来源：

- 状态身份；
- 状态变化；
- 安全触发规则；
- PDDL predicates 或 effects；
- 节点合并；
- 任务是否成功。

同样，Stagehand 的低层动作标签不一定是 planner-facing action name。PDDL 投影层可以
把类似“点击 Finish 且 `order_created` 变为 true”的状态转移映射为业务动作
`order_place_confirm`，因为 SafeSym 规则匹配的是规划语义，而不是某个工具自己的
click 标签。

当前 Stagehand 电商 benchmark 正在从低层 `observe()`/单动作执行，转向
business-milestone 边界：

```text
observe before state
  -> 要求 Stagehand 推进一个有意义的业务里程碑
  -> Stagehand 内部可以执行多个低层 click/fill 交互
  -> observe after state
  -> compute project-owned deltas
  -> append one WebKobeGraph business edge
```

低层 Stagehand 动作不应成为最终图边或 PDDL action。它们是挂在业务边上的
trace/evidence。benchmark runner 现在有 `business_milestone` Stagehand backend
模式用于这个实验。该模式优先使用 Stagehand 的 bounded `execute`/agentExecute 路径，
并设置较小 step limit，让 Stagehand 可以在内部完成一个里程碑；旧的 observed-action
模式保留为诊断 baseline。

不要把主实现替换成一次不透明的 Stagehand `agent()` 整任务运行。`agent()` 后续可以
作为外部 baseline，但 SafeSym 需要 milestone-level transition evidence。

Stagehand 真实站点 benchmark 仍然可以从 SauceDemo URL 开始，但它的任务 prompt 应描述
通用电商行为，而不是站点专用脚本。prompt 不应编码 SauceDemo 用户名、密码、商品名、
精确按钮文案或固定步骤序列。测试数据应通过 benchmark 配置或任务上下文提供，而不是
写在通用 prompt 里。

代码中，这个边界由 Stagehand prompt builder 表达：

```text
domain guidance = 可复用的电商 checkout 先验
benchmark context = 当前测试站点凭据和 checkout 数据
action policy = 每次图 transition 推进一个业务里程碑
safety boundary = 是否允许最终订单确认
```

命令边界也应保持同样形状：

```text
web-kobe-ecommerce-stagehand-smoke
  --benchmark saucedemo
  --start-url 可选覆盖
  --test-username / --test-password / checkout data
```

这样 SauceDemo 是 benchmark 配置，而不是主线架构路径的名字。

日常实验只保留最新生成产物，统一写入 `outputs/latest/`。标准 SauceDemo 测试站点命令
形状是：

```text
web-kobe web-kobe-ecommerce-stagehand-smoke
  --benchmark saucedemo
  --output outputs/latest/ecommerce_stagehand_graph.json
  --stagehand-trace outputs/latest/ecommerce_stagehand_trace.json
  --screenshot-dir outputs/latest/screenshots
  --clean-output-dir
  --allow-final-order
```

如果某次历史输出需要长期保留，应先复制到别处，再使用 `--clean-output-dir`。

## 状态观察与 Planning Facts

状态观察是当前最大的短板。

系统现在能收集 URL、title、可见控件、DOM 文本、HTML/DOM 结构、表单字段和
`[data-state]` 值。这些都是有用证据，但它们本身不一定是好的 PDDL 输入。
legacy SauceDemo-specific facts 可以保留在回归模块中，但不应作为客观 Stagehand 探索
的主 observer。

PDDL 应该消费 planning-level facts，例如：

```text
logged_in
product_list_visible
cart_has_items
checkout_started
required_info_missing
checkout_info_complete
order_review_ready
order_place_pending_sensitive
order_completed
error_visible
```

预期抽象栈是：

```text
raw browser evidence
  -> structured observation facts
  -> candidate planning facts
  -> verified planning facts
  -> PDDL predicates/effects
```

图里应该保留证据和不确定性。模型或启发式规则可以提出某个动作成功了，但只有经过验证
的 planning facts 才能影响 planner-facing model。

图里的状态归属应当拆开。`node.planning_state` 是 node/page/context 层面的 profile
facts 聚合摘要，用于分析、终止状态判断，以及未来 context-aware frontier 选择。
`edge.planning_transition` 记录某一次具体动作的 transition-local 前后事实。
PDDL action prediction 应优先使用 `edge.planning_transition.pre_facts`、
`added_facts` 和 `removed_facts`；只有历史 graph 缺少该字段时，才回退到旧的
`planning_delta`/source-node state 路径。

项目应该引入业务类型 profile，而不是盲目收集网页上的所有状态。
`BusinessFlowProfile` 定义某一类网站需要让规划器理解什么，但不绑定某个具体网站的
selector 或精确 URL。

例如，电商 checkout profile 可以描述 `cart_has_items`、
`checkout_info_complete`、`order_place_pending_sensitive` 这类 facts 的语义和
证据线索：

```text
fact: cart_has_items
meaning: the user has at least one item selected for purchase
evidence hints:
  - cart badge or item count indicates one or more items
  - cart page lists at least one product
  - product card indicates the item is selected or removable
```

边界应该是：

```text
BusinessFlowProfile = 规划器需要理解什么
observers/verifiers = 如何在当前页面寻找证据
site adapters = 可选的 benchmark-specific 稳定化
```

这样既比 SauceDemo 专用规则更通用，又比盲目收集所有状态高效得多。

## 当前不足

已知限制：

- 通用状态抽象仍然偏浅；
- 当前 PDDL 投影仍是较小的 STRIPS 子集。它现在默认使用干净的 planner-facing facts，
  但语义质量仍取决于 `PlanningDelta` 的质量；
- 虽然 PDDL action identity 已经唯一化，但部分 action name 作为 safety trigger 仍可能
  难以稳定匹配 SafeSym safety-rule patterns；
- 当前 visual-delta 路径是让 VLM provider 直接返回 profile 内的 candidate facts，
  还没有拆成“纯视觉变化总结 -> 独立 LLM/parser normalizer 映射 facts”两步；
- structured verifier 仍主要基于 signature diff。DOM、URL、控件、表单值和截图
  已经是证据来源，但还没有被一个通用的 profile-driven verifier 综合校验；
- SauceDemo 仍是真实站点 benchmark，不是任意网站泛化证明；
- 当前图是 task-guided partial graph，不是完整网站模型；
- frontier actions 目前主要是记录概念，replay/backtracking 暂缓；
- 节点去重和重复结构抽象还不成熟；
- 安全保证只适用于已观察并编译出的模型。

这些是研究阶段的正常限制。下一阶段应该优先补状态抽象。

## 下一阶段：AI 辅助的状态变化抽取

下一阶段主题是：

```text
VLM/LLM-assisted planning-state delta extraction
```

目标是在可控范围内积极使用大模型，同时保留项目自己的验证和图真相。

建议流程：

```text
before screenshot
  + after screenshot
  + executed action
  + task goal
  + before/after structured observation
  -> VLM visual delta summary
  -> LLM/parser normalized candidate planning delta
  -> structured verification
  -> verified planning facts/effects
  -> WebKobeGraph edge
  -> PDDL projection
```

截图采集只是本地 evidence collection，不表示当前配置的 Stagehand 文本模型可以处理
图片。后续如果启用视觉分析，应通过单独的 VLM provider/config 接入，并把 VLM 输出作为
candidate planning facts 交给 structured verification。

当前实现显式保持这个隔离：

```text
Stagehand = operation backend
visual_delta / OpenAIVisualDeltaProvider = observation-side VLM support
PlanningFactVerifier = structured verification before graph/PDDL truth
```

重要的当前状态区分：

```text
现在已经实现：
  before/after screenshots
  + profile fact set
  -> VLM provider 返回 visible_change_summary
     + candidate_added_facts / candidate_removed_facts
  -> 代码拒绝 profile 外的未知 facts
  -> WebKobeGraph edge metadata 记录 visual_change_summary，方便人工审阅
  -> 轻量 signature verifier 补充结构化 verified facts

短期实验：
  保持单次 VLM 调用
  要求同时输出 human-readable visual_change_summary 和 profile-bounded
  candidate facts
  先跑 SauceDemo final-order，检查每条边的 candidate delta 是否足够支撑
  PDDL/SafeSym 实验

后续方向：
  before/after screenshots
  -> VLM 只总结视觉变化
  -> LLM/parser 把总结映射到预设 profile fact 集合
  -> structured verifier 用 DOM/URL/控件/表单证据校验候选 facts，
     再决定哪些可以成为 planner-facing truth
```

职责划分：

```text
VLM = 视觉证据和任务相关变化假设
LLM/parser = schema 规整和 predicate 选择
structured verifier = DOM/URL/控件/表单证据校验
WebKobeGraph/PDDL/SafeSym = verified planning model
```

VLM 不能直接写入 PDDL facts。LLM 不应该自由发明 predicates。verifier 应该保留
不确定性，例如：

```text
candidate_success = true
verified_success = false or uncertain
reason = cart badge/button/URL evidence did not support the claim
```

这样系统既能利用大模型做语义压缩，又不会把规划模型变成不透明的模型输出记录。

当前 `PlanningDelta` 结构有意同时保留 candidate facts 和 verified facts，但近期链路
先假设 profile-level planning facts 足够可信，可以直接投影到 PDDL。这样能优先验证
VLM/LLM-to-PDDL 的完整路径。structured verifier 后续再作为稳定性和可信度增强，
负责判断哪些 candidate facts 应该升级为 verified facts。

## 近期路线图

建议下一步：

1. 先在 SauceDemo final-order 上运行简单单 VLM visual delta 实验，并审阅每条边的
   `visual_change_summary` 和 candidate facts。
2. 用同样的 profile-bounded visual delta 方法尝试另一个电商网站和一个论坛类网站，
   观察抽象在哪里失效。
3. 如果单调用路径难诊断或不稳定，再把 visual-delta 拆成 VLM 视觉总结和 LLM/parser
   fact normalization 两步。
4. 增加 LLM/parser normalizer，把总结映射到 profile predicate 集合。
5. 扩展 structured verifier，让它能结合模型候选、DOM、URL、控件、表单值和已知状态信号。
6. 先用 `local_checkout` 验证 profile-verified planning deltas，再用 SauceDemo 和额外
   benchmark 网站验证。

暂缓事项：

- 完整 frontier replay/backtracking；
- 鲁棒节点合并和模板级页面抽象；
- 商品卡片重复结构抽象；
- 参数化动作；
- checkout 之外的网站类型 profile；
- Stagehand `agent()` baseline 对比。

## 重要文件

```text
src/ai_web_explorer/grounded_web/
  通用探索和图构建包。

src/ai_web_explorer/grounded_web/automation_backend.py
  浏览器自动化后端接口。

src/ai_web_explorer/grounded_web/stagehand_backend.py
  Stagehand-backed AutomationBackend wrapper。

src/ai_web_explorer/grounded_web/stagehand_prompt.py
  Stagehand task prompt builder。它把可复用 domain guidance 与 benchmark context、
  safety mode 分开。

src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py
  Stagehand SDK 设置、模型 key 加载、本地 server/CDP 接线。

src/ai_web_explorer/grounded_web/explorer.py
  Web-KOBE 探索循环。

src/ai_web_explorer/grounded_web/graph.py
src/ai_web_explorer/grounded_web/graph_manager.py
  WebKobeGraph 数据结构和管理。

src/ai_web_explorer/grounded_web/state_facts.py
src/ai_web_explorer/grounded_web/typed_delta.py
  通用状态事实和 delta 提取。

src/ai_web_explorer/grounded_web/business_profile.py
  BusinessFlowProfile 和 planning-delta schema，用于 profile-guided 状态抽象。

src/ai_web_explorer/grounded_web/planning_fact_verifier.py
  structured verifier，把观察到的状态变化映射成 profile-guided PlanningDelta。

src/ai_web_explorer/grounded_web/visual_delta.py
  模型无关的 visual delta summarizer，用截图证据生成 candidate planning facts。

src/ai_web_explorer/grounded_web/openai_visual_delta.py
  OpenAI vision provider，用于 visual delta summarization。它属于观察层，不属于
  Stagehand 操作层。

src/ai_web_explorer/safesym_bridge/
  SafeSym/PDDL 投影和应用级回归包。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
  当前主线 WebKobeGraph-to-PDDL projector。

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
  PDDL planning-readiness smoke。

src/ai_web_explorer/safesym_bridge/state_observer.py
src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
  legacy SauceDemo-specific 观察和回归支持。它们不是通用 Stagehand 探索 observer。

docs/safesym-bridge.md
  SafeSym bridge 命令参考。
```

## 接力说明

新会话中，先阅读英文版 overview。中文版主要用于人工审阅，但两份文档必须同步。

开始新的架构或实现工作前，先复述这些点：

- 项目服务 SafeSym，不是通用 web-agent 产品；
- `grounded_web` 负责探索和构建 WebKobeGraph；
- `safesym_bridge` 负责投影和验证 planner-facing artifacts；
- Stagehand 是 action backend/evidence source，不是图真相来源；
- 下一阶段优先解决 verified planning-state delta extraction。

默认工作方式：

```text
单智能体
省 token
不要使用 subagent，除非用户明确允许
```
