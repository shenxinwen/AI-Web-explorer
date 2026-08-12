# 基于语义位置的动作去重设计

日期：2026-08-12
状态：已与用户对齐，作为后续探索策略设计的固定前提

## 1. 决策

开放式探索中的动作去重采用以下最小身份：

```text
(semantic_location, canonical_action)
```

同一个规范化动作在同一个语义位置中只作为新候选探索一次。动作在其他语义位置中仍可独立探索。

例如：

```text
(shopping, sort_products)
(shopping, filter_products)
(shopping, add_to_cart)
(product_detail, add_to_cart)
```

`shopping` 中成功探索过 `add_to_cart`，不会屏蔽 `product_detail` 中的 `add_to_cart`。

## 2. 语义位置

去重使用 active business surface 对应的粗粒度语义位置，不使用 URL、截图路径、DOM 节点 ID 或 Raw Graph node ID。

页面没有明显变化时，动作后的语义位置默认继承动作前的位置。页面发生视觉变化也不必然产生新位置：搜索、筛选、排序、分页、购物车数量变化等仍可属于 `shopping`。只有主要操作界面发生变化，例如商品详情 modal 或 Checkout modal 成为活跃界面时，才产生新的语义位置。

因此多个 Raw Graph 节点可以共享同一个 `semantic_location`，并共享该位置的动作去重记忆。

## 3. 动作身份

动作身份使用规范化后的 `canonical_action`，不依赖网站 URL、按钮文案、CSS/XPath、商品名称或执行顺序。

当前阶段不参数化具体商品、排序方向或筛选值。例如多个排序参数统一视为 `sort_products`，多个商品的列表加购统一视为 `add_to_cart`。更细粒度的 `(location, action, target)` 去重属于后续覆盖率优化，不在本设计范围内。

## 4. 去重状态

探索器至少区分：

- `success`：动作已执行并获得可接受的结果证据；
- `no_observable_change`：动作确实被执行并完成观察，但没有产生可规划变化；
- `failed`：执行或观察没有可靠完成。

`success` 和 `no_observable_change` 都表示该动作已在当前位置完成一次探索，后续新 Raw Node 即使仍提出相同候选，也应由本地 selector 过滤。`failed` 是否重试继续沿用独立的失败与重试策略，不得伪造成成功。

位置去重记忆必须写入可恢复的本地图产物；实验 resume 后不得遗忘已经完成的 `(semantic_location, canonical_action)`。

## 5. 与图和 PDDL 的边界

Raw Graph 保留每次真实执行的动作、前后观察、截图、错误和证据。位置去重不会删除这些审计信息。

Planning Graph 继续使用现有验收模型：

```text
planning state
= 一个位置事实
+ 普通能力完成事实
+ 必要业务事实
```

同位置动作可以形成位置 self-loop，并增加普通事实或业务事实。例如：

```text
at_shopping --sort_products--> at_shopping + products_sorted
at_shopping --add_to_cart----> at_shopping + cart_has_items
```

最终 PDDL 只包含位置事实、普通能力完成事实和必要业务事实。去重记忆是探索器内部控制信息，不得生成 `can_*`、`action_tried` 或其他一次性控制谓词。

## 6. PracticeAutomatedTesting 示例

在 `https://practiceautomatedtesting.com/shopping` 上：

```text
shopping
├─ search_products       只探索一次
├─ filter_products       只探索一次
├─ sort_products         只探索一次
├─ paginate_products     只探索一次
├─ open_product          只探索一次
├─ add_to_cart           只探索一次
└─ open_checkout         只探索一次

product_detail
├─ add_to_cart           可再独立探索一次
└─ close_product_detail  只探索一次

checkout
├─ complete_checkout_information
├─ complete_payment_information
└─ place_order（只建模，默认真实实验不提交）
```

排序或筛选形成新的 Raw Node 后，只要位置仍为 `shopping`，相同规范化动作就不再成为新探索候选。

## 7. 泛化边界

通用实现只理解：

```text
semantic location
canonical action
attempt outcome
persisted exploration memory
```

它不得包含 `shopping`、`cart`、`checkout`、`sort` 等站点或领域名称分支。以上名称仅是当前真实网站产生的数据。

## 8. 暂不决定的内容

本设计只固定“按语义位置进行动作去重”，不决定同一位置的兄弟动作应直接连续执行、每次回到基线，还是按变化程度选择性重放。

恢复路径中的 replay 是状态恢复行为，不自动等同于一次新的探索；其执行、验证和成本策略将在下一份探索方案中单独讨论。

## 9. 验收标准

1. 两个不同 Raw Node 具有相同可靠 `semantic_location` 时，共享动作去重记忆。
2. 同一位置的同一 `canonical_action` 在完成一次 `success` 或 `no_observable_change` 探索后，不再被 selector 选为新探索动作。
3. 同一 `canonical_action` 在不同位置仍可被选择。
4. resume 后去重结果与中断前一致。
5. PDDL 中不出现探索控制谓词，仍符合“位置事实 + 普通能力事实 + 必要业务事实”的现有验收标准。
6. 编译器和 selector 不包含站点名称、URL、按钮文案或领域动作名称硬编码。
