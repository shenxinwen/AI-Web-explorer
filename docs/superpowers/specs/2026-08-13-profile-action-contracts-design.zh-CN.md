# Profile 动作契约小型设计

## 目标

修正真实实验中业务事实过度晋升和提交动作过早执行的问题，同时保持通用探索器不感知购物网站、购物车、付款或订单等站点概念。

本次只增加 profile 配置型领域知识，不改造探索架构，不增加并行实现，也不引入新的测试模块。

## 配置边界

`SemanticExperimentProfile` 增加可选的 `action_contracts`。每项契约声明：

- `required_facts`：动作执行前必须已验证的业务事实；
- `added_facts`：动作成功且存在相符可见证据后允许新增的业务事实；
- `removed_facts`：必要时允许移除的业务事实，当前购物实验可为空。

通用代码只解释上述字段，不包含站点 URL、CSS/XPath、购物动作名或事实名判断。契约来源在语义产物中标记为 `profile_contract`，与实际观察证据区分。

## Practice Shopping 契约

```text
add_to_cart
  required_facts: []
  added_facts: [cart_has_items]

view_cart
  required_facts: [cart_has_items]
  added_facts: []

complete_checkout_information
  required_facts: []
  added_facts: [checkout_info_complete]

complete_payment_information
  required_facts: []
  added_facts: [payment_info_complete]

place_order
  required_facts:
    - cart_has_items
    - checkout_info_complete
    - payment_info_complete
  added_facts: [order_submitted]
```

位置条件继续由现有 semantic location 机制表达：两个表单动作和提交动作位于 `checkout`，成功提交后目标位置为 `confirmation`。

## 数据流

1. VLM仍然开放地提出当前页面候选动作。
2. 候选选择器读取当前已验证业务事实和 profile 契约。
3. 前提未满足的候选保留在候选池，但本次不执行；事实满足后自动恢复为可选。
4. Stagehand按现有 Agent 模式执行被选动作。
5. Visual Delta继续判断是否发生与动作相符的可见变化。
6. 事实晋升器只接受该动作契约允许产生或移除的业务事实；仅在词表内、页面有变化但不属于该动作契约的事实不得晋升。
7. Minimal Semantic PDDL从同一契约补充动作前提和允许效果，避免运行时门控与规划模型不一致。

## 失败与兼容边界

- 没有 `action_contracts` 的 profile 和无 profile 模式保持原行为。
- 未知动作没有契约时，不凭动作名推断业务规则，继续使用现有观察路径。
- 动作失败或没有相符可见变化时，不生成契约中的 `added_facts`。
- 导航到包含表单的页面不等于完成表单；`view_cart`不得产生 `checkout_info_complete` 或 `payment_info_complete`。
- 测试网站即使允许空表单提交，实验仍按已声明的正常业务流程建模。

## 验收

使用现有 Practice Shopping 实验链路进行短验证，预期得到：

```text
add_to_cart
-> view_cart
-> complete_checkout_information
-> complete_payment_information
-> place_order
-> confirmation
```

生成的 PDDL 至少满足：

- `view_cart`要求 `cart_has_items`，且不产生两个表单完成事实；
- 两个表单动作分别产生自己的完成事实；
- `place_order`要求购物车非空及两个表单完成事实；
- `place_order`产生 `order_submitted` 并进入 `confirmation`；
- SafeSym能够解析生成的 domain/problem。

本次按用户要求不新增测试；实现后使用现有测试集的相关部分和一轮短实验验证，不扩大修改范围。
