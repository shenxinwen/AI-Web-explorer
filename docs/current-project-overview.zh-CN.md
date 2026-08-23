# 当前项目概览

这份文档是项目当前主线的高层接力说明。模块职责见
`docs/project-structure.zh-CN.md`，关键决策及其原因见
`docs/project-decisions.zh-CN.md`。历史 specs、plans 和 experiments 仅用于追溯演进，
不覆盖本文描述的当前行为。

## 一句话目标

本项目不是让 agent 完成一个预设网页任务，而是探索真实网站、发现其基本功能，
并生成合法、可审查、可供 SafeSym 求解的 PDDL：

```text
开放式网站探索
  -> 观察动作前后变化
  -> 构建可恢复的 WebKobeGraph
  -> 抽象位置、普通能力和业务事实
  -> 生成 Minimal Semantic PDDL
  -> 交给 SafeSym 解析和规划
```

当前阶段的三个验收目标是：

1. 能够探索网站，而不是执行一条写死的任务脚本；
2. 能生成合法、可供 SafeSym 消费和求解的 PDDL；
3. 核心探索、图和 PDDL 逻辑具备一定泛化性。

## 当前主线

当前 active pipeline 是 location-scoped bounded open exploration：

```text
观察当前页面
  -> VLM 生成明确动作及同位置 requires
  -> 新语义位置首次到达时建立一次候选池
  -> 本地选择前提已成功的尚未完成动作
  -> Stagehand 执行一个动作
  -> VLM 观察 outcome、location_change 和可见 evidence
  -> 本地记录位置限定完成事实及可选位置变化
  -> 当前路径耗尽时，通过 reset + stored actions 重放到其他 frontier
  -> 达到有界终止条件后投影 Minimal Semantic PDDL
```

PDDL goal 或 SafeSym plan 不会反向传入候选生成和动作排序。探索仍然不是一条固定任务脚本。
当前主路径不向候选发现传入 experiment profile 或 action contract；可选的
`BusinessFlowProfile` 只供本地结构化事实 verifier 和 planner-facing 投影使用。

## 三类规划状态

当前 PDDL 把状态分成三类。

### 位置事实

位置表示粗粒度业务页面或 surface，例如：

```text
at_shopping
at_product_detail
at_checkout
at_confirmation
```

只有出现明显业务位置变化时才创建新位置。排序、筛选、搜索、购物车角标变化等，
通常不会单独制造组合位置。

### 普通能力事实

普通能力表示网站确实支持某项功能，例如：

```text
products_sorted
products_filtered
products_found
product_details_viewed
```

它们用于描述网站能力，但默认不会自动成为其他动作的前提。

### 业务事实

业务事实会解锁或约束后续动作，例如：

```text
cart_has_items
checkout_info_complete
payment_info_complete
order_submitted
```

当前最小依赖路径只把 initial scan 明确给出的同位置 `requires` 投影为动作前提，并且对应
前置动作必须真实执行成功。无关完成事实、`supporting_facts` 或全部 active facts 不能自动
升级成 PDDL 前提。本地 verifier 可以读取可选 `BusinessFlowProfile` 的结构化事实；独立的
semantic experiment profile 和 action contract 运行时路径已删除。

## 位置内动作去重

去重单位是：

```text
(semantic location, canonical action)
```

同一位置内成功执行过的动作不会再次选择。失败或无明显变化的动作可以按配置重试，
达到上限后不再占用探索预算。相同动作如果真实存在于另一个位置，仍然可以在那里探索。

动作后若位置未变，系统继承当前位置的候选池，不进行完整重新扫描。当前最小动作依赖路径在
第一次到达新位置时只做一次 initial scan，返回动作及同位置 `requires`；不再因业务事实变化
触发 targeted scan，也不做 supplement scan。旧扫描机制仍为兼容路径保留在代码中。

## 动作结果与节点规则

当前阶段对动作成功的要求较低：只要动作后观察到可靠变化，就可记录为有效尝试。

- 普通变化：位置保持不变，增加普通能力完成事实；
- 业务变化：位置可保持不变，增加或移除业务事实；
- 明显业务页面变化：创建或复用新的语义位置；
- 没有可观察变化：不创建新位置，按候选重试策略处理；
- Stagehand `tool_choice` 异常：继续执行动作后观察，不能仅凭模型错误终止实验。

Raw Graph 可以保留细粒度观察和执行证据；planner-facing SemanticPlanningGraph
只保留位置、普通能力、必要业务事实和可投影动作。

## 重放与断点恢复

重放只用于恢复到可继续探索的 frontier：

```text
reset 到起始 URL
  -> 执行 semantic-location 路径中的位置变化动作
  -> 在需要时先执行路径动作显式依赖的已完成同位置动作
  -> 全部动作成功后恢复目标 node、semantic location 和既有候选池
  -> 继续探索未完成动作
```

当前默认不在 replay 末端重新调用 VLM，也不要求匹配 raw node。只要保存路径中的动作全部成功，
就假定目标位置已恢复；旧的 checkpoint validator 仅作为可选兼容开关保留。这样可以避免恢复阶段
产生新的语义判断并与历史位置冲突。

replay 路径不是 raw graph 的最短动作路径。它按 semantic location 收缩：保留实际改变位置的动作，
跳过与恢复无关的同位置历史动作；如果某个保留动作声明了同位置 `requires`，则把已经完成的依赖动作
补入路径。例如恢复购物车时，不会仅因为历史上执行过 `add_to_cart` 就自动再次加购；只有
`view_cart` 明确依赖它时才会重放它。

重放本身不允许：

- 新增或修改节点、边和 planning facts；
- 修改候选池、扫描状态或动作尝试次数；
- 作为新的探索发现写入 PDDL。

checkpoint 保存图、候选记忆、累计正式动作预算和 replay 指标。实验中断后可以从最近断点继续，
无需清空已有图重新运行。

恢复后的第一次正式探索动作完成后，runner 可用唯一匹配的历史 URL pattern 做一次性位置交接，
将浏览器落点重新关联到已有 semantic location 和候选池。该机制只服务 replay 后的上下文恢复；
普通探索仍以 VLM 语义位置为主，不使用 URL 替代语义发现。

## 有界终止

当前实验通过参数化限制避免死循环。真实 Stagehand runner 当前采用候选级重试和步数上限：

- 正式探索动作硬上限由实验参数决定；最近一轮 SauceDemo 实验为 25；
- 同一候选动作最多尝试 2 次，仍失败则标记为失败并切换候选；
- 真实 Stagehand runner 不再使用全局连续无进展阈值作为提前终止条件；
- 单 frontier 重放次数上限：2；
- 总 replay 次数上限：4；
- 所有可达候选耗尽时正常结束。

这些是实验参数，不属于特定网站的语义规则，可以通过 CLI 或 `ExplorationLimits` 调整。

## 当前 PDDL 验收标准

当前最小依赖路径同时表达位置和位置限定的动作完成事实。例如：

```lisp
(:action add_product_to_cart
  :precondition (and (at_shopping))
  :effect (and
    (at_shopping)
    (completed_shopping_add_product_to_cart)
  )
)

(:action open_checkout
  :precondition (and
    (at_shopping)
    (completed_shopping_add_product_to_cart)
  )
  :effect (and
    (not (at_shopping))
    (at_checkout)
    (completed_shopping_open_checkout)
  )
)
```

`completed_shopping_add_product_to_cart` 来自已验证成功动作，并且只因为 `open_checkout` 的
显式同位置 `requires` 才成为其前提。其他已完成动作不会自动进入该动作的 precondition。

`domain.pddl` 描述已经探索并验证的动作、前提和效果；`problem.pddl` 描述起始位置、
初始业务事实和目标。排序、筛选等可以出现在 domain 中，但如果它们不是结账必要条件，
就不应出现在最短结账计划中。

当语义图不可用时，CLI 仍可生成 location-only 降级产物，并在
`semantic_projection_report.json` 中明确说明原因；降级结果不能冒充语义验收成功。

## 当前产物

一轮实验应保留：

- compact/raw WebKobeGraph 与 evidence sidecar；
- Stagehand execution trace 和截图；
- location candidate memory 与累计 runtime state；
- SemanticPlanningGraph 和 projection report；
- `domain.pddl`、`problem.pddl`；
- SafeSym parse/solve report；
- 实验摘要，包括停止原因、正式动作数和 replay 指标。

实验默认覆盖 `outputs/experiments/<site>/latest/`，只有明确需要历史对比时才归档，
避免重复产物无限堆积。

## 2026-08-23 当前执行粒度、终止边界与投影进度

当前 active path 已完成从“高层语义动作直接交给执行器”到“按动作策略展开”的最小改动：

- `single_instance` 表示一个候选只需要一个代表性 UI 操作；backend 只执行 Stagehand
  `observe` 返回结果中的第一个原子 Action，因此像加购这类动作不会因同一截图中返回多个重复目标而连续执行；
- `composite` 表示一个高层动作需要多个相关字段或步骤；backend 接受并按顺序执行 `observe` 返回的全部
  Action，任一步失败则高层动作失败，全部完成后才进入后续 outcome 观察；
- `execution_policy` 已保存在 `BrowserAction` 和图数据中，并随序列化、恢复和语义投影传递；当前只使用
  `single_instance` 与 `composite`，暂不启用 batch 语义；
- initial scan Prompt 已加入上述策略字段，但仍保持站点无关，不把商品页、购物车或固定按钮流程写成候选规则。

最近一轮 SauceDemo 无 profile 开放探索使用 GPT-4o、`observe_act`、25 步上限和每候选 2 次尝试，实际完成
13 个正式动作后以 `current_state_exhausted` 结束，并非达到最大步数。结果为 9 个语义进展、0 次 replay：

- `enter_credentials` 为组合动作，观察到并执行 2 个原子 Action；
- `add_to_cart` 被识别出 6 个重复目标，但按 `single_instance` 只执行 1 个；
- `complete_checkout_information` 为组合动作，观察到并执行 3 个原子 Action；
- `sort_products`、`filter_products` 的失败或无变化结果没有进入 planner-facing 成功动作集合；
- 结账概览同时返回 `cancel_checkout` 和 `complete_checkout`，当前调度器按发现顺序先执行了取消，`complete_checkout`
  仍留在 pending 状态。因此“没有点击 Finish”是候选排序/调度问题，不是 backend 无法执行组合动作。

当前实验没有启用语义 experiment profile 或 action contract，因此不能把 `cart_has_items` 当作本轮
`view_cart` 候选的前置条件。

随后从该 checkpoint 继续运行的 `resume_url_handoff_v1` 实验已经通过 replay 验收：4 次 replay 尝试全部成功，
路径使用 `enter_credentials -> submit_login -> view_cart` 恢复购物车，没有把无依赖关系的 `add_to_cart`
重新加入路径。恢复后正常探索继续完成 `continue_shopping`、`cancel_checkout`、`complete_checkout` 和
`navigate_home`；`continue_shopping` 回到商品页后，一次性 URL handoff 正确复用既有 `product_catalog`
候选池，没有创建 `product_listing_page` 别名或重复执行已完成商品动作。

该实验还暴露出 frontier selector 会从 raw node affordance 复活位置级已终止候选并触发一次多余 replay；
现已改为以 location candidate memory 的状态为准，并加入回归测试。replay 失败记录包含失败动作 ID、
目标位置和原因，选择器随后可以尝试其他 frontier；每个 frontier 2 次、总计 4 次的限制保持不变。

最新恢复实验图已投影到 `resume_url_handoff_v1/minimal_semantic_pddl`：13 条成功边进入语义图，
`filter_products` 因不可投影、`sort_products` 因执行失败被排除。以 `login_form` 为起点、
`checkout_complete_page` 为目标生成的 domain/problem 已通过 SafeSym 解析、安全动作注入、基础规划和安全规划；
安全计划在提交结账信息前插入了信息验证动作。当前仍缺少跨位置持久业务事实 `cart_has_items`，因此最短计划
会跳过 `add_to_cart`；这属于业务因果质量缺口，不影响本轮 replay 与 PDDL/SafeSym 链路验收。

## 2026-08-13 真实可行性实验结果

Practice Shopping 已完成一轮使用当前主线的真实有界实验，不再只是离线或 fixture 验证：

- 20 步硬上限下执行了 11 个正式动作，因连续 3 次无进展正常停止；
- 前向路径直接到达结账和确认阶段，本轮 replay 次数为 0；
- 实际验证了 `cart_has_items`、`checkout_info_complete`、
  `payment_info_complete` 和 `order_submitted`；
- 成功生成 SemanticPlanningGraph、`domain.pddl` 和 `problem.pddl`；
- SafeSym 解析、安全动作注入和 Fast Downward 求解均成功。

因此三个阶段目标已达到“可行链路”水平：系统能够真实探索、生成合法 PDDL，并被 SafeSym
消费和求解。但“求解成功”不等于业务模型已经正确，当前还存在以下重要问题：

1. `place_order` 的页面结果又被识别成独立 `order_submitted` 动作，形成绕过结账信息和支付
   信息动作的规划捷径；动作与动作结果的因果归属仍不稳定。
2. `filter_products` 的前后截图明确显示商品从 10 个变为 5 个，但 Visual Delta 同时把
   `products_filtered` 写入 added/removed，且没有写入 `completion_facts`，最终产生无效果的
   PDDL action；普通能力完成标志仍受模型字段稳定性影响。
3. 当时使用的旧 profile 路径是闭集且会进入候选 prompt，因而既承担统一表述，又部分承担能力提示和
   约束答案；这不符合下一阶段对“真正探索”的要求。
4. 无 profile 的 SauceDemo 登录 smoke 能自主读取公开测试凭据并成功进入商品页，证明候选发现
   和 Stagehand 执行具备跨站能力；但登录页和商品页都被粗略命名为 `swag_labs`，说明开放语义
   归纳尚不足以直接生成高质量 PDDL。

本轮正式产物位于
`outputs/experiments/practice_automated_testing/latest/`。实验目录不提交为产品代码，但它是当前
阶段结论的本地证据来源。

## 泛化性与硬编码边界

截至 2026-08-20，当前最小语义主链中的“站点答案硬编码”问题已经解决。准确定位是：

```text
无站点答案提示的 active semantic path + 保留但不参与 initial scan 的旧兼容/实验代码
```

已经通用化的部分包括：

- 位置候选池、位置内动作去重和候选重试；
- frontier 选择、reset + stored-action replay 和断点恢复；
- 动作前后观察、图持久化和累计预算；
- SemanticPlanningGraph 与 Minimal Semantic PDDL 编译器；
- 普通能力和业务事实的分离规则。

以下站点或领域相关内容仍保留在代码库中，但不等同于当前候选发现被写死：

- targeted/supplement scan 仍保留给后续实验；当前 initial scan 不调用它们；semantic experiment
  profile、profile registry 和 action contract 运行时路径已删除；
- `cart_count` / `item_count` 到 `cart_has_items` 的结构化映射和 `cart_non_empty` summary，属于旧业务
  事实归一化能力，当前最小动作完成 predicate 不依赖它们；
- SauceDemo benchmark 的公开测试凭据、结账表单测试数据和起始 URL，属于执行实验输入，不是候选
  动作答案；
- 最终下单只允许受控 PracticeAutomatedTesting URL，属于安全边界；
- 旧 ecommerce benchmark 的固定 checkout 步骤，以及当前静态实验脚本中的固定截图对、动作别名
  和 source/target 映射，属于历史入口或验收夹具，不参与产品 initial scan。

当前 initial scan 只根据截图提出动作及同位置 `requires`，不会收到站点 profile、完整动作词表、
动作契约、预期业务流程、外部任务 goal 或 PDDL goal；代表性动作 few-shot 也使用领域中立表达。
SauceDemo 静态验收复用了同一 prompt、parser、候选记忆、语义图和 PDDL 投影，没有增加
SauceDemo 专属动作表、按钮文本分支或固定流程。因此，“移除候选发现中的站点答案硬编码”不再是
下一步任务。后续若增强跨位置业务状态，应继续通过通用观察和归一化机制完成，不能把站点答案
重新放回候选 prompt。

当前开放探索主路径没有写死“排序 -> 筛选 -> 加购 -> 结账”的执行顺序，
也没有在 PDDL 编译器中根据 `shopping`、`cart` 或 `checkout` 名称分支。

## 当前最小动作依赖闭环

当前 active path 不再让 VLM 同时承担完整事实归纳和规划建模，而采用更小的“动作及依赖观察”闭环：

- 候选发现只观察当前页面，不接收具体 profile facts、动作契约、预期流程或离线 PDDL goal；
- 每个新语义位置只做一次初始扫描，返回明确动作及同位置 `requires`；
- 本地候选池根据前置动作是否成功推导可执行性，并优先调度依赖链动作；
- 动作后观察只返回 `outcome`、`location_change` 和简短可见 `evidence`；
- 候选观察、动作后结果观察与 Stagehand 执行统一默认使用 `gpt-4o`；三者仍可分别通过
  `OPENAI_VISUAL_DELTA_MODEL`、`OPENAI_ACTION_OUTCOME_MODEL` 与 `STAGEHAND_MODEL` 显式覆盖；
- 稳定的动作完成 predicate 由本地根据成功动作生成，不再要求 VLM 输出；
- 只有真实执行成功的动作和依赖关系进入 planner-facing graph 与 PDDL；
- 新路径不调用 targeted/supplement scan；这两个机制仍保留给后续实验。semantic experiment
  profile 和 action contract 已不再是运行时依赖。

这套方案已接入 location-scoped active path，并通过离线回归；去掉答案提示后的 SauceDemo 动态 VLM
实验和语义投影也已完成。SafeSym 仍可对提供显式 goal 的投影产物做离线验收，但本轮没有生成
`problem.pddl`。详细实现边界和验收标准见
`docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`。

## 探索执行与语义提取的验收边界

项目在能力上可以拆成两条相对独立的链：

```text
探索执行：当前页面 -> 候选调度 -> 执行动作 -> 获得下一页面观察
语义建模：截图观察 -> 动作及 requires -> 结果/位置判断 -> 本地记忆 -> 语义图 -> PDDL
```

Stagehand 属于探索执行链。候选解析、动作后观察、位置候选记忆、依赖解锁、
SemanticPlanningGraph、Minimal Semantic PDDL 和 SafeSym 验收可以在已有真实截图上独立测试。
静态实验把已有截图序列视为外部执行器提供的观察，不据此宣称系统能够自动到达这些状态。

当前代码尚未把两条链实现为完全独立的顶层 pipeline：`WebKobeExplorer` 仍在同一运行循环中
编排执行器、截图、结果观察、Raw Edge 写入和新位置扫描。因此当前准确表述是“能力与核心数据
结构可独立验收，但运行编排仍有耦合”。短期不为此重构 Explorer；静态实验使用薄的离线编排，
复用现有 VLM 合同、本地候选记忆、语义投影和 PDDL 编译器。

近期静态验收主要回答：如果执行器持续提供正确页面观察，系统能否自主提取真实动作、避免给
独立动作虚构 `requires`、识别明显操作依赖和位置变化、允许无动作页面返回空候选，并最终生成
无明显因果捷径且可被 SafeSym 消费和求解的 PDDL。它不验收元素定位、真实交互约束、reset、
frontier replay、断点恢复或自动到达截图状态的能力。

### 2026-08-20 静态语义验收结果

Practice Shopping 和 SauceDemo 的真实截图实验已经证明语义 MVP 主链可用。候选扫描改用
`gpt-4o` 后，重复对象上的同类动作、筛选维度和排序方式能够合并为代表性语义动作；登录提交和
结账信息提交的同位置 `requires` 能正确进入本地完成状态。SauceDemo 的十组严格动作前后截图中，
动作后 `outcome` 全部判断为成功，同页动作和跨页动作的 `location_change` 均与真实观察一致；
登录页、商品列表、购物车、结账信息、结账总览和成功页也被稳定区分。

十个成功动作均进入 `SemanticPlanningGraph`，没有投影排除项。Minimal Semantic PDDL 能正常
生成，SafeSym 解析、安全动作注入、基础规划和安全规划均成功。该结果只证明：假设执行器持续
提供正确观察，当前语义结构能够形成合法、可求解的 planner-facing 产物；不证明执行器能够自动
到达这些状态。

当前保留一个明确的非阻塞语义缺口：`open_cart` 本身不应依赖 `add_to_cart`，但空购物车不能继续
结账。现有最小动作完成 predicate 尚未自动形成跨位置持续业务事实
`add_to_cart -> cart_has_items -> proceed_to_checkout`，因此规划器可能跳过加购。该问题记录为
后续跨位置业务状态增强，不阻塞当前主线转向执行端。

执行层最初在 Practice Shopping 上完成了一个 `observe -> act` 原子动作探针：Stagehand
`observe` 正确返回 Category 下拉框的 `selectOptionFromDropdown("Electronics")` 动作，随后将该
Action 对象直接交给 `act` 成功执行。`observe` 约 1.24 秒，确定性 `act` 约 0.03 秒。后续
SauceDemo 开放探索实验已显式使用 `observe_act` 模式；通用 CLI 的默认执行模式仍是
`observed_action`，因此不能把实验脚本选择表述为全局默认切换。跨运行 Action 缓存尚未实现。

### 2026-08-21 VLM Prompt 恢复与执行粒度实验（历史对照）

提交 `fe257bc` 已将 2026-08-20 对齐的完整 initial scan Prompt 接入 active path。当前合同明确
区分 active surface、稳定位置命名、语义动作粒度、代表性动作合并、可见/阻塞动作、直接依赖、
结果页面和精度优先规则。Practice Shopping 同一商品页三次独立 GPT-4o 扫描稳定返回
`search_items`、`filter_results`、`sort_results` 和 `add_to_cart`，重复商品、筛选维度和排序方式
均合并为代表性动作。

纯截图观察在 Practice Shopping 和 SauceDemo 中都曾漏掉无文字的购物车图标。当前 Prompt 因此
加入一个有限的购物场景视觉提示：商品或目录页面中明显的购物车图标可以提出
`open_cart`/`view_cart` 候选，数量角标是支持证据但不是必要条件。该规则只提高候选召回，不提供
完整流程或依赖，也不直接进入 PDDL；动作仍须经过真实执行和截图 outcome 验证。加入提示的一次性
对照中，SauceDemo 加购前和加购后截图都返回了 `view_cart`。

最新动态实验位于
`outputs/experiments/saucedemo/open_exploration_full_prompt_gpt4o_v2`。实验使用 GPT-4o、显式
`observe_act`、12 步上限且未启用 frontier replay。候选扫描正确把登录页归并为
`enter_credentials` 和 `submit_login requires [enter_credentials]`，但执行没有通过登录：
Stagehand 对组合动作只返回并执行了用户名字段，SauceDemo 专用凭据覆盖又因同一指令同时包含
password 而把用户名值替换为 `secret_sauce`，密码字段没有填写。`submit_login` 两次收到密码必填
错误后进入 `failed_retry_exhausted`，实验以 `current_state_exhausted` 结束。

该结果把当前执行端主问题收敛为：语义图希望保留一个粗粒度高层动作，但 `observe -> act` 执行层
需要把它展开为多个原子 UI 操作，并在所有必要原子步骤成功后才将高层动作记为 success。这个问题
同时适用于登录凭据、联系信息、地址和支付表单。当前未启用 replay 时，当前位置耗尽会直接终止；
只有显式启用 frontier replay 后，Controller 才会 reset 并重放已验证路径到其他 pending frontier。

本节记录的是 2026-08-21 的失败基线；组合动作展开、候选级重试和后续实验结果见上方
“2026-08-23 当前执行粒度、终止边界与投影进度”。

## 当前阶段判断

截至 2026-08-23：

- location-scoped 开放探索的实现和回归测试已经合并；
- 可恢复图、候选池、累计预算和 non-mutating replay 已建立，候选级两次重试已成为真实 runner 的终止边界；
- Practice Shopping 真实实验已经跑通探索、业务事实验证、PDDL、SafeSym 和 planner；
- SauceDemo 无 profile 动态实验已验证单动作去重、组合动作展开、候选结果记录和语义投影；
- 25 步初始实验在 13 个正式动作后因当前候选耗尽结束；随后从 checkpoint 恢复的实验继续完成了
  `complete_checkout` 等剩余候选；
- 最新恢复图已生成带显式 goal 的 `domain.pddl` 和 `problem.pddl`，并通过 SafeSym 与 planner 验收；
- 最新断点恢复实验的 4 次 replay 全部成功，能够回到尚有候选的 frontier 并继续正常探索；
- 当前产物证明语义 MVP 可行，但跨位置持续业务状态仍不完整，不能表述为完整网站因果模型；
- 最小动作依赖闭环的静态验收已通过，候选发现中的站点答案硬编码已从 active path 移除；
- 主线继续验证给定语义动作能否稳定定位、按策略完成原子执行，并把真实下一页面观察交回现有语义链；
- 当前剩余重点是跨位置业务事实（尤其 `cart_has_items`）和更广泛网站上的 replay 泛化验证。

## 相关文档

- `docs/project-structure.zh-CN.md`：active 模块与数据流；
- `docs/project-decisions.zh-CN.md`：关键决策记录；
- `docs/safesym-bridge.md`：SafeSym bridge 使用方式；
- `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`：PDDL 验收语义；
- `docs/superpowers/specs/2026-08-12-location-scoped-open-exploration-feasibility-design.zh-CN.md`：本轮探索设计；
- `docs/experiments/`：历史实验与证据。
