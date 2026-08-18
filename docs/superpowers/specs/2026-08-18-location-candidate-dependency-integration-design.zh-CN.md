# 位置候选池与动作依赖集成 MVP 设计

日期：2026-08-18

## 1. 目标

本阶段验证一个最小闭环：探索器在不提前获得网站完整功能答案、动作契约或目标流程的情况下，根据当前页面自主提出动作及可见的操作依赖，通过真实执行验证动作，最终生成 SafeSym 和 Fast Downward 可以消费、求解且不存在明显因果捷径的 PDDL。

本阶段优先保证：

1. 识别出的动作真实；
2. 记录的动作依赖可信；
3. 成功执行的动作能够形成可规划的 PDDL。

本阶段不追求动作召回完整、动态界面覆盖完整或网页探索器的最终完备性。

## 2. 核心假设与边界

网站可以暂时建模为多个语义位置。每个位置包含若干可执行动作，其中一部分相互独立，另一部分形成操作依赖链。

位置是所有动作的共同前提。操作依赖只表达同一语义位置内明确动作之间的先后关系。跨位置关系由位置转移表达，不用 `requires` 跨位置连接。

VLM 可以在首次观察页面时主动识别明显的操作顺序，例如登录前填写凭据、提交订单前填写必要信息。执行失败后的错误信息只用于补充证据，不是发现依赖的主要机制。

当前 MVP 每个新语义位置只做一次候选扫描。因此，依赖链的目标动作必须在首次扫描时可见，或可由当前界面合理推断。只有完成前置动作后才出现、且首次扫描无法推断的新动作，属于当前已知限制，不引入 supplement scan 解决。

## 3. 硬编码边界

候选发现 prompt 不得包含：

- 网站完整功能清单；
- 具体网站的动作契约答案；
- 预期业务流程；
- PDDL goal；
- 要求模型逐项验证的事实词表。

允许提供有限的通用领域知识和 few-shot，帮助模型理解操作依赖与位置边界。例如：登录通常需要凭据；最终提交通常需要必填信息；筛选、排序、搜索和分页通常仍属于同一位置。

Practice Shopping 是首个验收网站，但实现中不得按其固定按钮文本、动作 ID 或完整流程编写专用分支。

## 4. 端到端流程

### 4.1 新位置首次扫描

进入一个尚未建立候选池的语义位置后，VLM 根据当前截图提出明确动作，以及动作之间当前可观察或可合理推断的直接依赖。

扫描结果按以下规则进入本地候选池：

- `requires=[]`：候选状态为 `pending`，可以直接调度；
- `requires` 非空：候选状态仍为 `pending`，但只有全部依赖成功后才可调度；
- 模型无法确认的动作：不进入正式候选池，只保留原始 VLM trace。

候选扫描不再要求模型永久分类“普通动作”或“业务动作”。是否参与依赖关系由 `requires` 表达，最终是否进入规划模型由真实执行结果决定。

### 4.2 本地调度

候选可调度的条件是：候选尚未到达终态，并且其全部 `requires` 对应的同位置候选均为 `success`。

调度顺序为：

1. 依赖链中当前可执行的动作；
2. 依赖解除后的目标动作；
3. 不参与依赖链的独立动作。

同一优先级沿用现有 `discovery_order`。独立动作仍保留在候选池中，可供后续探索或 frontier replay 使用。

### 4.3 执行和动作后观察

Stagehand 根据候选的自然语言描述和目标执行动作。动作完成后，VLM 比较执行前后截图，只判断：

- 动作是否成功；
- 当前是否仍为同一个语义位置；
- 支持判断的简短可见证据。

若位置未改变，系统只更新本地候选状态和由依赖派生的可调度性，不重新扫描整个页面。

若位置改变，系统切换或恢复目标位置的候选池。首次出现的目标位置执行一次初始扫描；已经访问过的位置恢复已有候选池。

### 4.4 失败传播

如果前置动作到达不可重试的失败终态，依赖它的动作进入 `blocked_by_failed_requirement`。该依赖链停止，但其他独立候选继续探索。

### 4.5 图与 PDDL 固化

只有经过真实执行且动作后观察确认成功的动作，才进入 planner-facing SemanticPlanningGraph。

只有当依赖目标动作也成功时，其候选阶段的依赖关系才通过显式字段 `required_action_ids` 固化到成功边。未执行、失败或仍被阻塞的候选及其依赖不得进入最终 Domain。

## 5. 最小 VLM API 协议

### 5.1 候选扫描响应

```json
{
  "actions": [
    {
      "action_id": "fill_billing_information",
      "description": "Fill the required billing information",
      "target": "billing information form",
      "requires": []
    },
    {
      "action_id": "place_order",
      "description": "Submit the order",
      "target": "Place Order button",
      "requires": [
        "fill_billing_information",
        "fill_payment_information"
      ]
    }
  ]
}
```

没有明确动作的页面返回：

```json
{"actions": []}
```

字段含义：

- `action_id`：同一位置内稳定且唯一的动作标识；
- `description`：供 Stagehand 执行的明确动作描述；
- `target`：截图中可见或明确指向的操作目标；
- `requires`：当前扫描结果中必须先成功的动作 ID。

响应校验必须拒绝或隔离悬空依赖、自依赖和循环依赖。模型可以漏识别动作，但不得为独立动作随意添加依赖，也不得把结果状态识别为动作。

### 5.2 动作后观察响应

```json
{
  "outcome": "success",
  "location_change": false,
  "evidence": "The required billing fields now contain values."
}
```

字段含义：

- `outcome`：`success | failed | uncertain`；
- `location_change`：严格 JSON 布尔值，表示活动语义界面是否改变；
- `evidence`：简短的可见判断依据，只用于审计和调试。

筛选、搜索、排序、分页、表单值、计数和样式变化默认属于同一位置。新的稳定页面、模态界面、抽屉、工作流步骤或结果界面成为活动界面时，视为位置改变。

本地根据成功动作的 `action_id` 生成完成事实，不再要求 VLM 返回完成事实、候选事实、动作角色、保留事实、业务事实或语义置信度。

### 5.3 DeepSeek 与 Stagehand

DeepSeek 当前主要通过 Stagehand SDK 执行动作。该链路沿用 Stagehand 的响应，只读取 `success`、`message` 和 `actionDescription` 等执行结果，不给 DeepSeek 增加候选扫描或语义观察的复杂返回协议。

候选扫描和动作后观察使用上述最小 JSON 协议。候选扫描默认使用
`gpt-4o-mini`，动作后观察默认使用 `gpt-4o`，二者通过
`OPENAI_VISUAL_DELTA_MODEL` 和 `OPENAI_ACTION_OUTCOME_MODEL` 独立配置；协议本身不绑定模型供应商，后续可以用其他兼容模型做独立对比。Stagehand 执行模型仍由 `STAGEHAND_MODEL` 独立配置。

## 6. 本地数据模型

现有 `LocationCandidateRecord` 只新增：

```text
requires: list[action_id]
```

不新增以下持久字段：

- `observed_readiness`；
- `successful_actions`；
- `remaining_requires`。

这些信息均可由候选状态和 `requires` 派生。`requires` 只能引用同一语义位置候选池中的动作。

新增候选终态：

```text
blocked_by_failed_requirement
```

候选池、依赖和动作状态继续随现有 checkpoint 持久化，以支持断点恢复和 frontier replay。

## 7. PDDL 表达

MVP 使用位置限定的零元完成谓词，不引入对象、类型或参数化谓词。例如：

```lisp
(at_checkout)
(completed_checkout_fill_billing_information)
(completed_checkout_fill_payment_information)
```

独立动作只需要位置前提：

```lisp
(:action filter_products
  :precondition (at_products)
  :effect (and
    (at_products)
    (completed_products_filter_products)))
```

依赖动作需要位置和前置动作完成事实：

```lisp
(:action place_order
  :precondition (and
    (at_checkout)
    (completed_checkout_fill_billing_information)
    (completed_checkout_fill_payment_information))
  :effect (and
    (not (at_checkout))
    (at_order_confirmation)
    (completed_checkout_place_order)))
```

同位置动作不删除位置事实。只有确认发生位置改变的动作才删除源位置并增加目标位置。

## 8. 旧路径处理

新路径绕开以下旧设计：

- profile 驱动的候选答案提示；
- business delta 触发的 targeted scan；
- supplement scan；
- 十四字段动作后语义观察协议；
- 由 VLM 直接生成 planner-facing 完成事实和业务事实。

本阶段不要求立即删除旧代码。实施时优先局部接入新路径，避免无意义的大重构；确认新链路稳定后，再单独评估旧路径清理。

## 9. MVP 验收标准

### 9.1 候选和依赖

- 返回的每个动作都对应真实、明确的网页操作；
- 无动作的成功页面允许返回空数组；
- 不把结果状态识别为独立动作；
- 登录、结账等明显顺序能够在首次观察时提出依赖；
- 独立筛选、排序等动作不产生错误 `requires`；
- `requires` 不包含悬空、自引用或循环关系；
- 不要求识别全部动作，但识别出的动作和依赖必须正确。

### 9.2 调度和状态

- 依赖未满足的目标动作不会提前执行；
- 前置动作成功后，目标动作自动解锁；
- 前置动作终态失败后，目标动作变为 `blocked_by_failed_requirement`；
- 单条依赖链失败不阻止独立动作继续探索；
- checkpoint 恢复后候选状态和依赖保持一致。

### 9.3 位置和观察

- 每次动作后都返回合法的 `outcome`、布尔 `location_change` 和证据；
- 同位置动作只更新本地状态，不重复扫描；
- 新位置首次进入时建立候选池，旧位置重访时恢复候选池；
- 筛选等同位置操作不应被当作位置跳转。

### 9.4 图、PDDL 和规划

- 只有真实执行成功的动作进入最终图和 PDDL；
- 成功依赖关系通过 `required_action_ids` 固化；
- PDDL 动作包含正确的位置和完成事实前提；
- 失败、未执行和仍被阻塞的动作不进入 Domain；
- Domain 和 Problem 可解析；
- SafeSym 能完成安全注入；
- Fast Downward 能找到预期计划；
- 计划不得绕过必要前提直接执行 `place_order`。

### 9.5 Practice Shopping 首轮通过条件

首轮实验满足以下条件即判定 MVP 通过：

1. 发现一部分真实普通动作，且没有明显错误依赖；
2. 发现结账关键依赖链；
3. 前置动作成功后正确解锁 `place_order`；
4. 不生成 `order_submitted` 等结果伪动作；
5. 成功页可以返回空动作；
6. 最终 PDDL 保留所有已验证动作；
7. 规划必须经过必要信息填写后才能提交订单；
8. SafeSym 和 Fast Downward 能正常消费并求解；
9. Prompt 未泄漏 Practice Shopping 的完整功能答案。

动作漏识别、少量位置判断不稳定，以及只在前置动作完成后才动态出现的新动作，记录为当前已知限制，不作为本轮否决条件。

## 10. 非目标

本阶段不实现：

- 完整动作召回；
- supplement scan；
- 一个目标动作的多套前置解法；
- 跨位置 `requires`；
- 完整业务本体自动发现；
- 参数化 PDDL 对象模型；
- 为不同网站编写包含完整答案的 profile；
- 对旧语义路径进行全面重构或删除。
