# Phase A VLM 状态命名设计

## 目标

让 Phase A graph 和由它投影出的 PDDL 使用容易阅读的状态名，同时保持状态身份、匹配和命名彼此独立。

第一版只做一个简单闭环：VLM 根据当前截图自由提出状态名，本地只保证名称在数据和 PDDL 中可安全使用。暂不引入词表、名称 embedding 或同义词合并。

## 设计边界

- 状态名描述当前可见页面，不描述到达该页面的动作。
- VLM 只使用当前局部观察，不接收 profile facts 或全局规划状态。
- `node_label` 不参与节点身份计算、target matching 或去重。
- 不在名称中保留商品名、搜索词、具体数量等业务对象。
- revisit 已有节点时保留最早确定的名称。
- 仅清理被本方案替代的旧命名代码，不扩大重构范围。

## 数据流

1. VLM 在提出当前页面业务动作时，同时返回顶层 `state_label`。
2. 提示词要求 `state_label` 是简短英文 `snake_case`，描述当前可见状态，例如 `product_list_sorted`。
3. 解析器读取该值；缺失或格式异常不能使候选动作生成失败。
4. 本地仅执行技术性清洗，使名称可安全用于 graph 和 PDDL。
5. 动作后先完成既有 target matching：
   - 匹配历史节点：保留历史节点原来的 `node_label`，忽略本次候选名称。
   - 确认为新节点：将本次 VLM 名称写入 `node_label`。
6. VLM 名称为空或清洗后为空时，依次回退到 `page_type` 和稳定的状态编号。

节点的 `node_id`、观察摘要和匹配证据保持原有职责，不受名称影响。

## VLM 输出约束

在现有视觉候选动作 JSON 顶层增加：

```json
{
  "state_label": "product_list_sorted",
  "page_mode": "multi_region",
  "regions": []
}
```

提示词说明：

- 名称只描述截图中当前可见状态。
- 使用简短英文 `snake_case`。
- 不使用动作过程，例如 `after_clicking_sort`。
- 不包含具体业务对象、搜索词或数量。

第一版接受 VLM 在语义上的自由命名，不做本地词汇统一。若实验中出现明显的同义名称漂移，再依据真实样本增加规则。

## 旧设计清理

Phase A 状态命名不再：

- 从 profile `state_label_hint` 或 PlanningState facts 推导 `node_label`。
- 从到达节点的业务动作推导 `node_label`。

删除只服务于上述路径的辅助函数、常量、参数传递和测试。保留 profile facts、PlanningState、`node_label`、`state_summary`、`naming_provenance` 以及 projector 的通用标识符清洗，因为它们仍有其他职责。

## 失败处理

- VLM 未返回 `state_label`：动作候选仍正常使用，名称走回退路径。
- VLM 返回非字符串或非法内容：清洗；清洗结果为空则回退。
- revisit 时 VLM 返回不同名称：忽略新名称，历史名称不变。
- 两个不同节点名称相同：第一版允许。节点身份仍由 `node_id` 区分，projector 继续负责生成合法且无冲突的 PDDL 标识符。

## 测试与验收

- VLM 返回的 `state_label` 能进入新节点的 `node_label`。
- 名称不影响候选动作解析。
- 空名称和非法名称能够安全回退。
- 历史节点 revisit 后名称不改变。
- Phase A 命名不再依赖 profile facts 或到达动作。
- 删除旧命名路径后，现有 graph、探索和 PDDL 测试通过。
- 运行一次小规模真实实验，检查 graph 与 domain 中的名称是否比当前输出更容易阅读。

## 非目标

- 不做语义名称去重。
- 不维护全局命名词表。
- 不用名称辅助状态匹配。
- 不改探索、回退或终止策略。
- 不处理 Phase A 之外的业务事实建模。
