# VLM 观察验收设计

日期：2026-08-17

## 目标与边界

本阶段只验证 VLM 能否在不接收网站功能答案的情况下，稳定生成探索主线所需的观察结果。实验不修改探索调度器、位置候选池、PDDL 投影或 SafeSym bridge。

实验分为两个连续阶段：

1. 候选与依赖观察；
2. 动作前后观察。

第一阶段通过后再验证第二阶段，避免把候选发现、动作验证和下游调度问题混在同一次实验中。

## 与当前主线的关系

实验沿用现有 location-scoped candidate pool：

- 第一次进入语义位置时进行 initial scan；
- 同位置且只有已执行动作可以解释的变化时，不重新扫描候选；
- 位置变化后切换到目标位置候选池，首次到达时扫描；
- 同位置出现除已执行动作外的其他明显变化时，后续复用 targeted 或 supplement scan；
- 候选继续按 `(semantic location, canonical action)` 去重。

新设计只要求候选观察能够额外表达 `ready | blocked | unknown` 和直接依赖，不在本阶段改变候选池实现。

## 第一阶段：候选与依赖观察

### 输入约束

模型主要接收当前截图和通用观察说明，不接收：

- 网站完整功能词表；
- 具体动作契约或动作示例答案；
- 标准业务流程；
- SafeSym goal 或剩余任务步骤；
- profile 中的位置、事实和功能答案；
- 已完成动作历史。

### 最小输出

```json
{
  "location": "checkout",
  "actions": [
    {
      "id": "complete_checkout_information",
      "instruction": "Fill in the required checkout information",
      "status": "ready",
      "requires": [],
      "evidence": ["Required editable checkout fields are visible"]
    },
    {
      "id": "place_order",
      "instruction": "Place the order",
      "status": "blocked",
      "requires": ["complete_checkout_information"],
      "evidence": ["Required checkout information is incomplete"]
    }
  ]
}
```

### 动作发现要求

- 不要求穷举页面上的全部动作，优先保证返回结果正确。
- 页面存在明确动作时，至少返回一个有效候选。
- 成功页、结果页或纯提示页没有可执行动作时，`actions=[]` 是正确结果。
- 不得编造截图中不存在的动作。
- 不得把 `order_submitted` 等结果事实包装成独立动作。
- 动作应是可以交给 Stagehand 独立执行并通过前后观察验证的语义操作。
- 不输出字段级点击、单字符输入等低层步骤，也不使用 `finish_everything` 等无法界定的笼统动作。

### 状态与依赖语义

- `ready`：当前可以直接执行，且必须满足 `requires=[]`。
- `blocked`：当前不能完成，并且必须列出当前页面中直接、未满足的前置动作。
- `unknown`：截图证据不足，无法可靠判断是否可执行或需要什么前提。
- 不允许 `blocked + requires=[]`；无法指出前提时应返回 `unknown`。
- `requires` 不记录已完成历史条件，也不展开传递依赖。
- `requires` 中的每个 ID 必须对应同次响应中的候选动作，确保本地调度器能够执行。
- 页面排列、空间邻近、推荐顺序或常见业务流程不能单独构成依赖证据。

### 动作粒度

模型可以根据当前页面自主选择合理粒度，不要求匹配预定义动作名称或固定数量。

以下两种表达均可接受：

- `place_order` 分别依赖 `fill_billing_information` 和 `fill_payment_information`；
- `place_order` 依赖一个能够覆盖两部分输入的 `complete_checkout_information`。

对于已经返回的 blocked 动作，其一个或多个前置动作必须共同完整覆盖截图中明确可见的直接前置需求。不能只返回部分前提，从而形成绕过必要条件的规划捷径。

### 硬失败项

出现下列任一情况，候选与依赖实验判定不通过：

- 返回不存在或无法执行的动作；
- 把动作结果识别为新动作；
- 将独立动作错误写入另一个动作的 `requires`；
- blocked 动作遗漏明确可见的必要直接前提；
- `requires` 引用了同次响应中不存在或不可直接执行的动作；
- 成功页为了满足候选数量而编造动作。

错误依赖采用硬门槛，因为它会直接污染 planner-facing precondition，并可能导致无关动作被强制执行或可达计划被错误阻塞。

## 第二阶段：动作前后观察

### 输入

- 动作前截图；
- 本次实际执行的单一语义动作；
- 动作后截图。

### 最小输出职责

动作前后观察只回答：

1. 动作是否产生了与指令一致的可靠变化；
2. 当前语义位置是否发生变化；
3. 除已执行动作可以解释的变化外，页面是否还有其他明显变化。

建议的实验输出形态：

```json
{
  "outcome": "success | failure | unknown",
  "location_change": "changed | unchanged | unknown",
  "other_significant_change": true,
  "evidence": ["short visible evidence"]
}
```

`other_significant_change` 指候选操作集合或活跃操作表面出现了不能只用已执行动作的局部结果解释的明显变化，例如新弹窗、新表单步骤、新操作区域或候选可用性结构发生变化。普通字段被填写、排序结果更新等已执行动作的直接预期结果本身不自动触发整页候选重扫。

## 后续主线预期行为

本阶段只验证 VLM 输出，不实现以下行为，但实验结果应能支持它们：

```text
进入位置
→ initial scan 建立候选池
→ 选择 ready 动作
→ Stagehand 执行
→ 动作前后观察
   ├─ 失败或 unknown：保留审计并按现有重试策略处理
   ├─ 位置改变：切换位置候选池
   ├─ 同位置且有其他明显变化：targeted/supplement scan
   └─ 同位置且只有动作直接结果：本地更新候选状态和 remaining_requires
→ remaining_requires 清空后 blocked 候选转为 ready
```

当前可行性阶段直接沿用现有动作成功标准：Stagehand 完成执行，并且动作前后观察到与动作一致的可靠变化，即可在本地将该动作视为完成并消除相应 dependency。暂不增加部分完成、语义完整度或多级置信状态机。

## 实验通过后的下游验收方向

VLM 输出达到上述标准后，再单独设计候选池和 PDDL 改动。最终最低目标是：

- 只把实际执行成功的动作投影到 Domain；
- 每个动作保留位置前提；
- 观察到的直接依赖转成合法 precondition/effect；
- Domain/Problem 能被 SafeSym 消费并由 Fast Downward 求解；
- PDDL goal 不反向参与探索或候选排序。

本阶段不追求完美恢复网站全部规则，只验证从开放页面观察到可执行动作和必要依赖，并生成可供后续合法规划投影使用的数据是否可行。
