# 基于语义位置的开放探索可行性实验设计

日期：2026-08-12

状态：已与用户逐项确认；等待用户审阅书面规格后进入实施计划

## 1. 目标

在 `https://practiceautomatedtesting.com/shopping` 上验证以下结构能够真实跑通：

```text
新位置完整发现候选
-> 同位置继承候选并连续验证普通能力
-> 业务事实变化触发定向候选扫描
-> 进入新位置后重新完整发现候选
-> 形成位置事实、普通能力事实和必要业务事实
-> 生成 SafeSym 可消费、可求解的 PDDL
```

本轮不以覆盖率、跨网站泛化或参数化商品/筛选条件为主要验收目标。探索仍然开放、无预设任务：SafeSym goal 只在探索与 PDDL 生成完成后用于事后验收，不进入候选生成或动作排序。

## 2. 已固定的基础决策

动作去重遵循已提交规格：

```text
docs/superpowers/specs/2026-08-12-semantic-location-action-dedup-design.zh-CN.md
```

去重键为：

```text
(semantic_location, canonical_action)
```

相同语义位置中的同一规范化动作只作为新能力探索一次；相同动作在另一位置仍可独立探索。Replay 是状态恢复，不受新能力去重限制，也不产生图节点、图边、事实或候选记录。

## 3. 状态与 PDDL 语义

Planning State 只包含三类信息：

```text
一个当前语义位置
+ 累计的普通能力完成事实
+ 当前必要业务事实
```

### 3.1 位置事实

本轮实验允许的位置词表：

```text
shopping
product_detail
checkout
confirmation
```

位置代表 active business surface，不代表 URL 或 Raw Node。只有主要操作界面发生明确变化时才生成新位置，例如商品详情 modal、Checkout modal 或订单确认界面成为活跃操作区域。

页面没有明显变化时必须继承原位置。页面发生变化也不自动改变位置：排序、筛选、搜索、分页、选中状态、计数和购物车内容变化仍可属于 `shopping`。位置证据不足时保守继承来源位置。

### 3.2 普通能力完成事实

本轮允许的普通事实词表：

```text
products_sorted
products_filtered
products_found
products_paginated
product_details_viewed
```

这些事实表示“本轮已经成功观察并验证过该能力”，不是当前 UI 精确配置。它们采用累计验收语义，不要求 replay 恢复，也不能默认成为其他业务动作的前提。

### 3.3 业务事实

本轮允许的业务事实词表：

```text
cart_has_items
checkout_info_complete
payment_info_complete
order_submitted
```

业务事实表示会影响后续动作可执行性的持久业务状态。增加、删除或要求经过验证的业务事实时，动作具有业务语义。动作可以同时是位置转换和业务动作。

Checkout 字段不逐项建模。账单、联系方式和地址统一抽象为 `checkout_info_complete`；支付字段统一抽象为 `payment_info_complete`。

### 3.4 PDDL 边界

每个 PDDL action 至少包含来源位置前提和显式动作后位置，并只包含与该动作相关的普通或业务事实。候选池、已尝试动作、扫描状态、去重、重放和终止预算不得生成 `can_*`、`action_tried` 等 PDDL 谓词。

## 4. 候选池

候选池属于语义位置，而不是 Raw Node。

### 4.1 新位置首次扫描

首次进入一个可靠的新语义位置时，VLM 对当前页面进行一次完整候选扫描。单个位置的初始候选上限默认为 8；每个功能族最多保留一个代表动作。

### 4.2 同位置继承

动作后位置不变时，默认继承该位置现有候选池，不重新完整扫描。已经完成、无变化、失败耗尽或失效的候选不会再次成为新探索动作。

执行继承候选前先做轻量页面检查。若对应控件已不可见或不可执行，将候选标记为 `stale/disabled` 并继续，不立即调用 VLM。

### 4.3 候选耗尽补充扫描

一个位置的候选池耗尽后，最多允许一次补充扫描。补充扫描没有返回新的 canonical action，或只返回当前位置已经探索过的动作时，将该位置标记为耗尽，不再扫描。

### 4.4 同一控件的语义变化

canonical action 表达业务能力，不表达控件身份。同一个可见控件在业务事实变化后可以被定向扫描解释为新的动作身份。例如：

```text
cart empty     -> open_empty_cart
cart_has_items -> open_checkout
```

因此先前探索 `open_empty_cart` 不会阻止后来探索 `open_checkout`。

## 5. 动作执行与结果观察

每次正式动作后都必须比较动作前后观察，至少判断：

- 是否发生稳定可见变化；
- active business surface 是否改变；
- 新增了哪些普通能力完成事实；
- 增加或删除了哪些业务事实；
- 是否存在候选业务前提及其证据。

### 5.1 低门槛动作成功

本轮只要观察到稳定页面变化就认为动作执行成功。变化可以是顺序、集合、选中状态、文本、数量、价格、提示、modal、主要区域或 URL 的变化。

Stagehand 或模型返回 `tool_choice` 等错误时，只要动作后页面确实发生变化，仍按成功处理；错误只保留为诊断证据。

### 5.2 动作成功不等于事实成立

动作成功与事实验证必须分离。任意页面变化足以完成当前位置的动作去重，但只有与事实相符的观察证据才能把普通事实或业务事实写入 Planning Graph 和 PDDL。

例如 `add_to_cart` 后只观察到 modal 关闭，可以判动作成功；若未观察到购物车计数、`In cart` 或订单摘要中的商品证据，则不得生成 `cart_has_items`。

### 5.3 无变化与重试

正式候选最多尝试 2 次。第一次没有观察到变化时允许再执行一次；第二次仍无变化则记录 `no_observable_change`，不生成事实，并在当前位置停止重复探索该动作。

每次正式 Stagehand 动作尝试均计入全局探索步数，无论最终成功、失败或无变化。

## 6. 事实变化后的候选策略

### 6.1 只有普通事实变化

直接继承剩余候选池并继续探索，不触发 VLM 候选扫描。先前累计的普通事实不得被注入后续动作的前提，因此连续执行 `sort -> filter -> search` 不会制造虚假线性依赖。

### 6.2 业务事实增加或删除

保留现有候选池，并触发一次定向 VLM 扫描。定向扫描只回答刚刚验证的业务变化是否导致：

```text
newly_enabled
semantically_changed
disabled
```

定向扫描可以返回空结果，不得为了满足格式虚构能力。它只发现候选，不直接确认新的业务事实；新候选仍需执行和观察。

定向扫描去重键为：

```text
(semantic_location, added_business_facts, removed_business_facts)
```

相同业务事实变化只扫描一次，记录必须随断点保存并在 resume 后保持。

### 6.3 位置变化

进入新的语义位置时为该位置进行首次完整候选扫描，不继承旧位置候选池。

## 7. Prompt/Profile 的实验性硬编码

本轮允许在实验 Prompt/Profile 中固定：

- 第 3 节的位置、普通事实和业务事实词表；
- 对应事实的最低可见证据；
- 典型 action role 与事实变化示例；
- 统一输出 JSON 合同；
- canonical action 命名示例。

Prompt 必须允许返回空事实和不确定结果。词表是允许范围，不是强制输出；不得规定 `add_to_cart` 执行后必然返回 `cart_has_items`。

不得硬编码：

- CSS、XPath、DOM ID 或固定控件索引；
- 商品名称或具体输入值；
- 动作执行顺序或固定探索轨迹；
- SafeSym goal；
- selector、通用探索器或 PDDL 编译器中的站点专用分支。

本轮采用“强词表、强输出格式、弱事实强制、无固定轨迹”，验证结构而非脚本。

## 8. Replay 与恢复

Replay 只用于把浏览器恢复到历史 frontier 或实验断点，本身不影响图。普通动作之间默认连续探索，不为隔离排序、筛选和搜索而重放。

恢复完成后至少验证：

```text
目标语义位置
+ frontier 后续动作所需业务事实
```

普通累计能力事实不要求恢复。验证通过后才恢复正式探索。

## 9. 测试数据与完整业务通路

当前站点是受控测试网站，本轮允许使用生成的虚构数据填写 Checkout 并执行 `place_order`。不得使用用户真实姓名、联系方式、地址或支付信息。

成功提交并看到确认结果后：

```text
location = confirmation
business fact added = order_submitted
```

本轮不要求精确判断订单提交后购物车是否清空。

期望 SafeSym 事后验收路径至少包含：

```text
add_to_cart
open_checkout
complete_checkout_information
complete_payment_information
place_order
```

排序、筛选、搜索和分页不得成为该业务路径的必要步骤。

## 10. 正常终止

开放探索不因达到 `confirmation` 目标而立即终止。正常终止条件为：

```text
所有可恢复语义位置的候选池均已耗尽
+ 每个耗尽位置的补充扫描已完成且无新动作
+ 没有待处理的业务事实定向扫描
+ 没有待首次扫描的新位置
+ 没有可恢复并继续探索的 frontier
```

正常 stop reason 为：

```text
frontier_exhausted
```

## 11. 参数化保护性终止

所有预算必须是运行参数，不得散落为流程硬编码。

| 参数 | 本轮默认值 | 语义 |
|---|---:|---|
| `max_exploration_steps` | 20 | 正式 Stagehand 动作尝试总数 |
| `max_consecutive_no_progress` | 3 | 连续无新位置、新事实或新候选的正式动作数 |
| `max_action_attempts_per_candidate` | 2 | 同一正式候选最大执行次数 |
| `max_replay_attempts_per_frontier` | 2 | 单个 frontier 最大 replay 失败次数 |
| `max_total_replays` | 4 | 整轮 replay 开始次数，成功和失败均计数 |
| `max_vlm_scan_attempts` | 2 | 每次完整、补充或定向扫描的最大调用次数 |
| `max_candidates_per_location` | 8 | 每个位置首次扫描候选上限 |

正式动作尝试达到 20 后保存断点并以 `max_exploration_steps_reached` 终止。VLM 扫描、轻量候选检查和 replay 不计入这 20 步。

“有进展”至少满足一项：新位置、新普通事实、业务事实增加/删除或扫描发现新 canonical action。连续 3 个正式动作均无进展时以 `consecutive_no_progress_limit_reached` 终止；出现进展后计数归零。

单个 frontier replay 失败 2 次后本轮暂时屏蔽该 frontier，保留证据并继续其他 frontier。全局 replay 达到 4 次后不再恢复新 frontier；当前页面仍有候选时可继续，否则以 `total_replay_limit_reached` 终止。所有 frontier 均不可恢复时使用 `no_recoverable_frontier`。

一次 VLM 扫描允许首次调用和一次重试。两次均超时、格式错误或失败后保存原始响应和错误，不再触发同一扫描，并继续使用现有候选。

无论正常或保护性终止，都必须保存断点、图、trace、投影报告和明确 `stop_reason`。

## 12. 返回时间与超时

VLM 和 Stagehand 可能返回较慢。实验必须使用明确且宽松的可配置超时时间，不能因短暂等待或 `tool_choice` 模型异常直接终止。只有超过配置超时且重试预算耗尽后，才按对应失败规则处理。

## 13. 实验产物

必须保存：

```text
Raw Graph
位置候选池及去重/扫描状态
动作执行与前后观察 traces
业务事实定向扫描结果
replay 与恢复验证记录
Semantic Planning Graph
domain.pddl
problem.pddl
semantic projection report
SafeSym 求解结果
stop reason 与预算统计
```

每个 PDDL action 必须能追溯到对应的真实动作、前后观察和事实证据。Replay 记录可审计，但不得作为新的规划边来源。

## 14. PDDL 与 SafeSym 验收

至少生成以下语义：

```lisp
(:action sort-products
  :precondition (at-shopping)
  :effect (and (at-shopping) (products-sorted))
)

(:action add-to-cart
  :precondition (at-shopping)
  :effect (and (at-shopping) (cart-has-items))
)

(:action open-checkout
  :precondition (and (at-shopping) (cart-has-items))
  :effect (and
    (not (at-shopping))
    (at-checkout)
    (cart-has-items)
  )
)

(:action place-order
  :precondition (and
    (at-checkout)
    (cart-has-items)
    (checkout-info-complete)
    (payment-info-complete)
  )
  :effect (and
    (not (at-checkout))
    (at-confirmation)
    (order-submitted)
  )
)
```

事后 problem 使用：

```text
init: at_shopping
goal: at_confirmation + order_submitted
```

SafeSym 必须能返回包含第 9 节业务动作的完整计划；普通能力动作不得成为这条计划的必要步骤。

## 15. 最小通过条件

本轮结构验收通过需要同时满足：

1. 新位置首次完整生成候选，同位置继承候选；
2. 至少两个普通能力连续验证，不因 Raw Node 变化重复探索；
3. 普通事实不触发候选扫描，也不进入业务动作前提；
4. 加购产生有证据的 `cart_has_items` 并触发定向扫描；
5. 定向扫描发现或重新解释 `open_checkout`；
6. Checkout 形成新位置并生成新候选池；
7. 使用生成数据完成两类表单事实并提交测试订单；
8. 看到确认后形成 `at_confirmation + order_submitted`；
9. 生成合法、可追溯的 domain/problem；
10. SafeSym 能从 `at_shopping` 规划到 `at_confirmation + order_submitted`；
11. 实验自然耗尽或由参数化保护条件安全停止，不发生无限循环。

## 16. 非目标

本轮不要求：

- 穷举商品、筛选值、搜索词或排序方向；
- 参数化 action target；
- 完全动态发现位置和业务事实词表；
- 跨网站泛化实验；
- 精确 DOM 差异因果分析；
- 用 SafeSym goal 指导探索；
- 将 replay 结果写成新的规划边；
- 将测试网站的词表和流程写入通用编译器。
