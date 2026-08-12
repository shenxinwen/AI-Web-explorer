# 位置、普通能力与业务事实 PDDL 验收设计

日期：2026-08-12
状态：已与用户对齐，作为当前阶段正式验收标准

## 1. 决策摘要

当前阶段的目标产物不再是 DOM 状态复刻，也不是预设的电商阶段流水线，而是一份面向 SafeSym 的最小语义 PDDL：

```text
规划状态 = 一个当前业务位置
         + 若干普通能力完成标志
         + 若干必要业务事实
```

三类信息必须分开：

1. **位置事实**描述当前活跃的粗粒度业务界面，例如 `at-shopping`、`at-checkout`。位置不是 URL；页面上的 modal、drawer 或嵌入式工作区也可以成为位置。
2. **普通能力完成标志**描述筛选、排序、搜索等页面能力已经成功执行并观察到结果，例如 `products-filtered`、`products-sorted`、`products-found`。
3. **业务事实**描述会成为后续动作必要前提的持久语义，例如 `cart-has-items`、`checkout-info-complete`、`payment-info-complete`。

动作的 effect 必须显式包含动作后的位置信息，并包含该动作新增、删除或确认的关键状态信息。普通外观变化不创建新的 planning location；同一位置上的业务进展优先用业务事实表达。

## 2. 为什么采用这个模型

只使用页面跳转图无法表达“仍在商品页，但购物车已经非空”；把每个视觉差异都做成节点又会产生筛选、排序的虚假线性依赖和状态爆炸。

本设计保留两者的必要部分：

- 位置用于说明动作在哪里可执行；
- 普通能力事实使筛选、排序、搜索不再是无效果动作；
- 业务事实只表达真正约束后续步骤的条件；
- Raw Graph 仍保存完整观察和重放证据，PDDL 只消费抽象后的规划语义。

这是一份语义丰富但规模受控的 PDDL，不要求理解完整网站业务。

## 3. 核心状态模型

### 3.1 位置事实

任一可规划状态必须恰好有一个活跃位置：

```lisp
(at-shopping)
(at-product-detail)
(at-checkout)
(at-confirmation)
```

位置采用“当前活跃业务 surface”语义，而不是 URL 或 DOM 页面身份。例如 checkout modal 覆盖在 shopping URL 上时，活跃位置可以从 `at-shopping` 变为 `at-checkout`。

当位置改变时，动作删除旧位置并添加新位置；当位置不变时，effect 仍显式重申当前位置，方便审计动作后状态。

### 3.2 普通能力完成标志

普通能力动作不创建新位置，但要产生可规划效果：

```lisp
(products-filtered)
(products-sorted)
(products-found)
```

这些事实表示“该能力已经成功执行并观察到相应结果”，不是后续业务动作的默认前提。除非网站证据证明存在真实依赖，否则 `open-product`、`add-to-cart`、`open-checkout` 不得要求先完成筛选、排序或搜索。

完成标志采用累计验收语义，而不是精确 UI 配置语义。例如 `products-sorted` 表示本轮已成功验证过排序能力，并不记录当前是升序还是降序；`products-found` 只在搜索成功且观察到匹配商品时成立。若未来需要表达精确排序方向、搜索参数或空结果，应增加独立参数化模型，不能悄悄改变这些 V1 标志的含义。

### 3.3 业务事实

只保留确实会约束后续动作的事实：

```lisp
(cart-has-items)
(checkout-info-complete)
(payment-info-complete)
(order-submitted)
```

事实词表可以由站点 profile 提供，也可以由受控的事实晋升流程产生；PDDL projector 不按动作名猜测事实。

## 4. 动作建模规则

每个动作至少包含：

- 一个来源位置前提；
- 仅在确有证据时加入的业务前提；
- 一个明确的动作后位置；
- 动作新增、删除或确认的普通能力/业务事实。

effect 不要求枚举整个世界中所有保持不变的事实，只要求包含唯一的动作后位置和与该动作相关的关键状态。这样既满足位置可审计性，也避免把无关事实复制到每个动作中。

### 4.1 普通能力动作

```lisp
(:action sort-products
  :precondition (at-shopping)
  :effect (and
    (at-shopping)
    (products-sorted)
  )
)

(:action filter-products
  :precondition (at-shopping)
  :effect (and
    (at-shopping)
    (products-filtered)
  )
)

(:action search-products
  :precondition (at-shopping)
  :effect (and
    (at-shopping)
    (products-found)
  )
)
```

### 4.2 同一位置上的业务变化

```lisp
(:action add-to-cart-from-shopping
  :precondition (at-shopping)
  :effect (and
    (at-shopping)
    (cart-has-items)
  )
)
```

这里不生成 `shopping-with-cart` 组合位置。当前位置保持不变，购物车状态由独立事实表达。

### 4.3 跨位置业务变化

```lisp
(:action open-checkout
  :precondition (and
    (at-shopping)
    (cart-has-items)
  )
  :effect (and
    (not (at-shopping))
    (at-checkout)
    (cart-has-items)
  )
)
```

### 4.4 需要必要业务条件的动作

```lisp
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
    (cart-has-items)
    (checkout-info-complete)
    (payment-info-complete)
    (order-submitted)
  )
)
```

敏感动作可以建模，但真实站点探索默认不得为了补齐图而执行支付、下单、发送或其他不可逆操作。未经实际验证的敏感 outcome 必须在证据报告中标明，不能伪装成已验证 transition。

## 5. PracticeAutomatedTesting 站点验收实例

目标站点：<https://practiceautomatedtesting.com/shopping>

2026-08-12 的实际页面核对结果：

- shopping surface 直接提供搜索、筛选、排序、分页及加入购物车；
- 商品详情是可选 modal，不是加入购物车的必要路径；
- 加入商品后购物车计数变化，但活跃位置仍是 shopping；
- 购物车非空时点击购物车，直接打开 Checkout modal；
- Checkout modal 同时包含订单汇总、账单信息、付款信息和 Place Order；
- 当前观察不支持虚构独立的 cart page 或 order-review page。

因此，当前站点的最小安全规划路径应为：

```text
at-shopping
  -- add-to-cart-from-shopping --> at-shopping + cart-has-items
  -- open-checkout ------------> at-checkout + cart-has-items
```

对应动作：

```lisp
(:action add-to-cart-from-shopping
  :precondition (at-shopping)
  :effect (and
    (at-shopping)
    (cart-has-items)
  )
)

(:action open-checkout
  :precondition (and
    (at-shopping)
    (cart-has-items)
  )
  :effect (and
    (not (at-shopping))
    (at-checkout)
    (cart-has-items)
  )
)
```

安全验收 problem：

```lisp
(define (problem reach-checkout)
  (:domain practice-shopping)
  (:init
    (at-shopping)
  )
  (:goal
    (at-checkout)
  )
)
```

SafeSym 预期返回：

```text
add-to-cart-from-shopping
open-checkout
```

筛选、排序、搜索可以作为单独能力目标或组合能力目标验证，但不得被注入上述结算路径的前提。

## 6. VLM 与确定性代码的职责

VLM 负责基于动作前后观察提取有限结构：

```json
{
  "location_before": "shopping",
  "location_after": "shopping",
  "preserved_facts": [],
  "added_facts": ["cart_has_items"],
  "removed_facts": [],
  "evidence": ["The cart count changed from 0 to 1."]
}
```

或：

```json
{
  "location_before": "shopping",
  "location_after": "checkout",
  "preserved_facts": ["cart_has_items"],
  "added_facts": [],
  "removed_facts": [],
  "evidence": ["A checkout modal with billing and payment fields opened."]
}
```

确定性代码负责：

1. 规范化位置、动作和事实 ID；
2. 检查每个后状态恰好有一个位置；
3. 位置改变时生成旧位置删除效果；
4. 把已验证的 facts 编译为前提和效果；
5. 保持输出顺序和命名稳定；
6. 生成 PDDL 到 Raw/Planning evidence 的映射报告。

VLM 不直接决定 PDDL 语法，也不根据全局任务目标选择探索动作。

## 7. 泛化边界

生成器不得硬编码 `shopping`、`cart`、`checkout`、`sort` 等名称。这些只是当前站点数据。通用实现只理解：

```text
location
capability completion fact
business fact
action preconditions/effects
evidence status
```

另一个网站如果确实存在独立 cart 页面，探索与抽象层可以产生 `at-cart`；当前练习网站没有观察到该位置，就不能因为电商常识虚构它。

同样，文档系统可以产生 `at-document-list`、`document-found`、`document-selected`、`permission-granted`，而无需修改 PDDL 编译器。

## 8. 与探索主线的关系

探索仍然是开放式、无任务目标的：

```text
开放式候选发现
  -> 单动作执行
  -> 动作后观察
  -> Raw Graph 与 checkpoint
  -> 离线规划抽象
  -> PDDL
  -> 事后选择 problem goal 并交给 SafeSym
```

PDDL goal 和 SafeSym plan 不得反向进入候选生成或探索排序。普通能力完成事实可以支持事后的覆盖率规划，但本设计不把探索器改造成完成预设任务的 agent。

## 9. 当前阶段验收标准

### 9.1 形式合法性

- 生成的 domain/problem 能被 SafeSym parser 接受。
- 对已探索且结构可达的 goal，SafeSym 能返回计划。
- PDDL 名称规范化、顺序稳定，相同语义输入生成相同输出。

### 9.2 状态语义

- 每个可规划状态恰好包含一个活跃位置。
- 每个 action effect 显式包含动作后的位置信息。
- 普通能力完成标志与业务事实独立于位置存储。
- 同一位置上的业务事实变化不强制生成组合 location。
- 只有 active business surface 发生变化时才改变位置。

### 9.3 必要条件

- 普通能力默认只要求其来源位置。
- 排序产生 `products-sorted`，筛选产生 `products-filtered`，搜索产生 `products-found`。
- 普通能力事实默认不作为其他业务动作的前提。
- 购物车、表单、付款等依赖只有在观察或验证支持时才进入前提。
- 不从动作名称、行业常识或预设模板虚构必要条件。

### 9.4 当前站点实例

- 能表达 `at-shopping + products-sorted`，且不产生 sorted-shopping 新位置。
- 能表达 `at-shopping + cart-has-items`，且不产生 shopping-with-cart 新位置。
- 能从 `at-shopping` 规划到 `at-checkout`。
- 预期最短计划为 `add-to-cart-from-shopping`、`open-checkout`。
- 不要求经过 product detail。
- 不虚构独立 cart page 或 order-review page。
- 不实际提交订单作为默认实验验收步骤。

### 9.5 泛化性与可审计性

- PDDL 编译器不包含站点或领域动作名称分支。
- 所有动作、位置和事实均可追溯到 Planning Graph 与 Raw evidence。
- 证据不足的事实不得静默进入已验证 PDDL。
- 即使事实提取失败，系统仍可降级生成位置级 PDDL，而不是伪造业务语义。

## 10. 非目标

当前阶段不要求：

- 精确表达商品 ID、排序方向、过滤参数或购物车数量；
- 完整建模所有表单字段；
- 覆盖网站全部分支；
- 自动执行敏感或不可逆业务动作；
- 让 PDDL 目标反向指导开放式探索；
- 为所有网站共享固定的业务事实词表。

参数化、覆盖率目标、更细的对象模型和敏感动作策略均可在该最小模型跑通后继续演进。

## 11. 与现有 Location PDDL V1 的关系

现有 Location PDDL V1 只表达位置可达性，并主动排除 planning self-loop 与业务 facts。它仍然是永久可用的兼容和降级层，但不再代表当前阶段的最终验收形态。

本设计定义其上的最小语义层：

```text
Location PDDL V1
  只表达跨位置可达性
  事实识别失败时仍可生成

Minimal Semantic PDDL（本设计）
  = 位置
  + 普通能力完成标志
  + 必要业务事实
  作为当前阶段主验收目标
```

实施时不得破坏现有 location-only 输出。新语义投影可以是显式新模式或新 artifact；当事实证据不足时应降级到 Location PDDL V1，并在 projection report 中说明降级原因。
