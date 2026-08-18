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
  -> VLM 生成少量主要候选动作
  -> 按语义位置建立候选池
  -> 本地选择该位置尚未完成的动作
  -> Stagehand 执行一个动作
  -> 比较动作前后的 DOM、结构化签名和截图
  -> 记录普通能力事实、业务事实或位置变化
  -> 业务事实变化时做一次定向候选扫描
  -> 新位置第一次到达时生成该位置的候选池
  -> 当前路径耗尽时，通过 reset + stored actions 重放到其他 frontier
  -> 达到有界终止条件后投影 Minimal Semantic PDDL
```

PDDL goal 或 SafeSym plan 不会反向传入候选生成和动作排序。探索仍然不是一条固定任务脚本。
但当前实现会把完整 experiment profile context 传给候选扫描和动作后 Visual Delta，且 profile
包含位置、事实、动作示例和动作契约。它虽然没有规定执行顺序，却会向 VLM 暗示预期能力；
这是当前阶段已确认的泛化性限制，不能继续表述为“profile 只做无偏的统一命名”。

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

业务前提只来自已经验证的 profile/structured facts。候选动作的
`supporting_facts`、普通完成事实或全部 active facts 不能自动升级成 PDDL 前提。

## 位置内动作去重

去重单位是：

```text
(semantic location, canonical action)
```

同一位置内成功执行过的动作不会再次选择。失败或无明显变化的动作可以按配置重试，
达到上限后不再占用探索预算。相同动作如果真实存在于另一个位置，仍然可以在那里探索。

动作后若位置未变，系统继承当前位置的候选池，不进行完整重新扫描。只有以下情况会扫描：

- 第一次到达一个新位置时进行 initial scan；
- 业务事实发生变化时进行 targeted scan，询问是否出现新动作；
- 候选池确实需要补充时进行有界 supplement scan。

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
  -> 执行图中保存的动作序列
  -> 在目标端做一次截图语义位置和必要业务事实校验
  -> 恢复临时 current-node 指针
  -> 继续探索未完成动作
```

重放本身不允许：

- 新增或修改节点、边和 planning facts；
- 修改候选池、扫描状态或动作尝试次数；
- 作为新的探索发现写入 PDDL。

checkpoint 保存图、候选记忆、累计正式动作预算和 replay 指标。实验中断后可以从最近断点继续，
无需清空已有图重新运行。

## 有界终止

当前实验通过参数化限制避免死循环。Practice Shopping 可行性实验的当前约定是：

- 正式探索动作硬上限：20；
- 连续无语义进展上限：3；
- 单 frontier 重放次数上限：2；
- 总 replay 次数上限：4，候选动作重试也有独立上限；
- 所有可达候选耗尽时正常结束。

这些是实验参数，不属于特定网站的语义规则，可以通过 CLI 或 `ExplorationLimits` 调整。

## 当前 PDDL 验收标准

理想产物同时表达位置和事实。例如：

```lisp
(:action add_to_cart
  :precondition (and (at_shopping))
  :effect (and (at_shopping) (cart_has_items))
)

(:action open_checkout
  :precondition (and (at_shopping) (cart_has_items))
  :effect (and
    (not (at_shopping))
    (at_checkout)
  )
)
```

`cart_has_items` 在 STRIPS frame semantics 下会自然保持，除非动作明确删除它；不需要把已成立
事实再次写成动作 effect。

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
3. 当前 profile 是闭集且会进入候选 prompt，因而既承担统一表述，又部分承担能力提示和
   约束答案；这不符合下一阶段对“真正探索”的要求。
4. 无 profile 的 SauceDemo 登录 smoke 能自主读取公开测试凭据并成功进入商品页，证明候选发现
   和 Stagehand 执行具备跨站能力；但登录页和商品页都被粗略命名为 `swag_labs`，说明开放语义
   归纳尚不足以直接生成高质量 PDDL。

本轮正式产物位于
`outputs/experiments/practice_automated_testing/latest/`。实验目录不提交为产品代码，但它是当前
阶段结论的本地证据来源。

## 泛化性与现有硬编码

当前实现不是完全无硬编码。准确定位是：

```text
通用探索框架 + 可选领域/实验 profile + 少量电商结构化捷径
```

已经通用化的部分包括：

- 位置候选池、位置内动作去重和候选重试；
- frontier 选择、reset + stored-action replay 和断点恢复；
- 动作前后观察、图持久化和累计预算；
- SemanticPlanningGraph 与 Minimal Semantic PDDL 编译器；
- 普通能力和业务事实的分离规则。

当前仍存在的显式硬编码包括：

- `practice_shopping_feasibility` profile 的位置、动作和事实词表；
- `cart_count` / `item_count` 等字段到 `cart_has_items` 的结构化映射；
- state summary 中的 `cart_non_empty` 提示；
- profile 名称在 CLI/registry 中的注册；
- 最终下单只允许受控 PracticeAutomatedTesting URL 的安全门；
- 旧 ecommerce benchmark 入口中的固定 checkout 实验步骤。

测试数据和受控下单 URL 属于实验配置或安全边界，可以保留。profile 中用于统一语言的分层
词表也可以保留，但当前把完整词表、动作示例和契约交给候选发现的做法会产生答案提示。
真正需要后续泛化的不只是把 `cart_count -> cart_has_items` 迁入外部配置，还包括把“自由发现”
与“动作后归一化”明确拆开。

当前开放探索主路径没有写死“排序 -> 筛选 -> 加购 -> 结账”的执行顺序，
也没有在 PDDL 编译器中根据 `shopping`、`cart` 或 `checkout` 名称分支。

## 下一阶段已确认的设计（尚未实现）

下一阶段不再让 VLM 同时承担完整事实归纳和规划建模，而采用更小的“动作及依赖观察”闭环：

- 候选发现只观察当前页面，不接收具体 profile facts、动作契约、预期流程或离线 PDDL goal；
- 每个新语义位置只做一次初始扫描，返回明确动作及同位置 `requires`；
- 本地候选池根据前置动作是否成功推导可执行性，并优先调度依赖链动作；
- 动作后观察只返回 `outcome`、`location_change` 和简短可见 `evidence`；
- 稳定的动作完成 predicate 由本地根据成功动作生成，不再要求 VLM 输出；
- 只有真实执行成功的动作和依赖关系进入 planner-facing graph 与 PDDL；
- 新路径绕开 profile 驱动的 targeted scan、supplement scan 和当前多职责 Visual Delta 事实结构。

这套方案已经完成设计对齐，但尚未成为当前 runtime。详细实现边界和验收标准见
`docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`。

## 当前阶段判断

截至 2026-08-13：

- location-scoped 开放探索的实现和回归测试已经合并；
- 可恢复图、候选池、累计预算和 non-mutating replay 已建立；
- Practice Shopping 真实实验已经跑通探索、业务事实验证、PDDL、SafeSym 和 planner；
- 当前产物证明 pipeline 可行，但同时证明“profile 辅助验证”的阶段尚未等同于真正开放的
  语义探索；
- 下一步不应立即增加第二个网站的专属答案 profile，而应先在 Practice Shopping 实现最小
  动作依赖闭环，验证去掉答案提示后仍能发现正确能力并生成因果正确、可求解的 PDDL。

## 相关文档

- `docs/project-structure.zh-CN.md`：active 模块与数据流；
- `docs/project-decisions.zh-CN.md`：关键决策记录；
- `docs/safesym-bridge.md`：SafeSym bridge 使用方式；
- `docs/superpowers/specs/2026-08-12-location-capability-business-fact-pddl-acceptance-design.zh-CN.md`：PDDL 验收语义；
- `docs/superpowers/specs/2026-08-12-location-scoped-open-exploration-feasibility-design.zh-CN.md`：本轮探索设计；
- `docs/experiments/`：历史实验与证据。
