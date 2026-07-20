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
- 旧的自研通用动作执行层已经移除；
- Playwright 仍用于受控 fixture 和 fallback 操作；
- Stagehand 已作为真实站点动作发现/执行后端接入；
- WebKobeGraph 可以投影成 PDDL；
- PDDL 投影当前会把 candidate 和 verified planning-delta facts 都视作可信 effects，
  用于先跑通 VLM/LLM-to-PDDL 端到端链路；
- 当状态转移证据支持时，PDDL 投影层可以把低层浏览器动作名翻译成 SafeSym-facing
  业务动作名；例如，产生 `order_created` 的边会投影成 `order_place_confirm`。
- 生成的 PDDL 可以做图可达性和静态一致性检查；
- Fast Downward 可以求解生成的 base plan；
- SafeSym 可以在 smoke 场景中 parse、注入安全动作，并求解 safe plan。

最近一次保留测试的状态：

```text
all retained tests: 183 passed, 2 skipped
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

当前使用 Stagehand 的方式是单步 transition loop：

```text
observe before state
  -> Stagehand observe/act 一个受约束动作
  -> observe after state
  -> compute project-owned deltas
  -> append WebKobeGraph edge
```

不要把主实现替换成一次不透明的 Stagehand `agent()` 整任务运行。`agent()` 后续可以
作为外部 baseline，但 SafeSym 需要 transition-level evidence。

## 状态观察与 Planning Facts

状态观察是当前最大的短板。

系统现在能收集 URL、title、可见控件、DOM 文本、表单字段、`[data-state]` 值，以及
SauceDemo 应用专用 facts。这些都是有用证据，但它们本身不一定是好的 PDDL 输入。

PDDL 应该消费 planning-level facts，例如：

```text
logged_in
product_list_visible
cart_empty
cart_nonempty
checkout_started
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

项目应该引入业务类型 profile，而不是盲目收集网页上的所有状态。
`BusinessFlowProfile` 定义某一类网站需要让规划器理解什么，但不绑定某个具体网站的
selector 或精确 URL。

例如，电商 checkout profile 可以描述 `cart_nonempty`、
`checkout_info_complete`、`order_place_pending_sensitive` 这类 facts 的语义和
证据线索：

```text
fact: cart_nonempty
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
- 当前 PDDL 投影仍是较小的 STRIPS 子集；
- 部分 action name 仍太底层，难以稳定匹配 SafeSym safety-rule patterns；
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
  SauceDemo-specific 观察和回归支持。

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
