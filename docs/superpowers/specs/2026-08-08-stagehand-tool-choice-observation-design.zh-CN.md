# Stagehand tool_choice 异常继续观察设计

## 目标

处理 Stagehand 返回 `Thinking mode does not support this tool_choice`、但底层网页操作可能已经发生的情况，避免把已产生页面变化的动作错误记录为失败自环。同时将中文项目文档与当前 Phase A 主线对齐。

## 行为边界

该错误只表示 Stagehand/模型适配层无法正常完成工具调用协议，不足以证明网页动作没有执行。

探索器遇到该错误时：

1. 保留 Stagehand 返回的原始失败信息和 `backend_reported_success=false`；
2. 继续获取动作后页面、截图和结构化观察；
3. 在截图可用时继续调用 Visual Delta；
4. 根据 URL path、结构签名和 Visual Delta 判断是否存在明确变化；
5. 存在明确变化时，按成功变化 edge 记录；
6. 没有明确变化时，记录 `no_observed_change` 自环，并继续探索其他候选。

其他未知执行错误仍按普通失败处理：不生成新状态、不调用 Visual Delta、记录失败自环。

## 职责边界

- Stagehand 只报告执行结果和 trace，不决定 graph 转换是否成立。
- 本地探索器根据动作后观察决定该异常是否实际产生了变化。
- Visual Delta 仍是纯变化观察者，只输出 `candidate_added_facts` 和 `candidate_removed_facts`。
- Visual Delta facts 只进入 raw edge trace，不进入 PlanningState、target matching planning conflict 或 Phase A PDDL。
- 本次不修改 embedding 阈值、Phase A 合并规则或持久化 graph schema。

## 文档对齐范围

### `docs/current-project-overview.zh-CN.md`

- 将 Visual Delta、PlanningState 和 Phase A 描述更新为当前主线；
- 记录 tool_choice 异常的准确处理语义；
- 记录明确变化时 target matching 不得匹配回来源节点；
- 记录实验统一写入 `outputs/experiments/<site>/latest/`；
- 增加 `BusinessAffordance.action_name/label/target_hint` 语义重叠待办；
- 移除或改写已经失效的旧实验结论。

### `docs/project-structure.zh-CN.md`

- 更新 Visual Delta 的输入、输出和消费边界；
- 明确新探索不生成 VLM `BusinessTransition`；
- 明确观察 facts 与 PlanningState/PDDL 隔离；
- 更新 target matching 的来源节点保护规则。

### `docs/project-decisions.zh-CN.md`

- 保留历史决策；
- 在最新位置追加本次异常处理和文档对齐决策，不改写历史上下文。

## 测试

至少覆盖：

1. tool_choice 异常且 URL 变化：继续观察并记录成功转换；
2. tool_choice 异常且结构签名变化：继续观察并记录成功转换；
3. tool_choice 异常且只有 Visual Delta 非空：继续观察并记录成功转换；
4. tool_choice 异常且没有变化：记录 `no_observed_change` 自环；
5. 未知执行错误：仍为失败自环且不调用 Visual Delta；
6. 原始异常和 `backend_reported_success=false` 保留在 execution metadata；
7. 现有 target matching、Phase A 和 PDDL 回归测试继续通过。

## 非目标

- 不修改 Stagehand 多步骤业务动作的完成边界；
- 不解决 business affordance 字段重复；
- 不调整 URL/结构签名粒度；
- 不处理 Phase A CLI 自动启用 embedding 的隐藏调用；
- 不运行真实网站实验，直到代码和文档修改通过验收。

