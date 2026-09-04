# 方法

## 问题与符号

给定未知 Web 应用，系统通过 GUI observation 与浏览器交互接口获得轨迹：

> observation → GUI interaction → new observation

系统不给定具体任务或完整功能清单，目标是在风险约束下持续归纳应用级功能模型，而不是恢复完整、不可观察的内部业务状态。

模型中的论文级概念如下：

| 概念 | 含义 | 明确边界 |
| --- | --- | --- |
| Semantic location | 稳定的业务位置，如商品列表、购物车、项目设置页 | 不是 DOM/截图的逐元素状态 |
| High-level function | 具有业务意义的功能，如添加商品、创建项目、邀请成员 | 不是按钮或输入框枚举 |
| Location constraint | 功能被提出、执行和观察时所在的位置 | 不等同于完整业务 precondition |
| Observed direct action dependency | 页面观察提出且由成功交互序列支持的直接顺序关系 | 不主张普遍必要、充分或严格因果关系 |
| Functional outcome | 功能结果状态与界面转移类型 | Executor Success 不等于 Functional Success |
| Verification state | 功能结论当前获得的支持程度 | 与运行时调度状态分离 |
| Interaction evidence | 支持结论的来源、轨迹、前后观察与结果判断 | 可追溯不等于形式化正确性保证 |

功能结果使用两个独立维度：

1. 结果状态：Success、Failure、Uncertain；
2. 界面转移：Location-Preserving、Location-Transition。

论文级 verification state：

- **Proposed**：已提出，尚无真实交互支持；
- **Partially Supported**：已有部分证据，不足以完整确认；
- **Interaction-Supported**：真实交互与结果观察提供充分支持；
- **Failed**：执行或结果观察明确不支持该假设；
- **Incomplete**：因中断、风险停止或其他原因未完成验证。

pending、retryable、stale、blocked 等只作为实现层子状态。

## 方法概述

### 1. Function Hypothesis Proposal

VLM 根据当前 GUI 和已有模型提出 semantic location、high-level function 与可能的直接动作依赖。所有新内容先保存为 Proposed 假设，不直接写成环境事实。VLM 是可替换的候选生成与观察工具。

### 2. Execution and Outcome Observation

浏览器执行器尝试执行被选中的 high-level function。系统记录动作前后观察，并分别判断执行器是否完成动作以及预期功能结果是否发生。浏览器执行器是可替换工具。

### 3. Evidence-Driven Model Update

系统依据执行记录和结果观察更新 outcome 与 verification state。失败、不确定和未完成结果分别保留；只有达到证据要求的知识才能供下游使用。每项结论应支持如下追溯：

> hypothesis source → execution trace → before/after observations → outcome judgment

### 4. Persistent Frontier

当前位置尚待验证或未完成的假设被持久保存，系统可以重访已访问位置继续建模。该机制服务于持续探索，不作为独立概念贡献。

### 5. Risk-Aware Functional Verification

执行前根据候选功能的影响程度与可恢复性确定验证深度。普通可恢复操作允许完整执行；潜在不可逆操作可在最终 commit 前停止，并将已获得证据记录为 Partially Supported 或 Incomplete（两者的判定规则待机制设计时明确）。

示例：

```text
Delete Project
→ Confirmation Dialog
→ [Commit Boundary]
→ Confirm Deletion
```

确认界面可为“存在删除功能”提供部分语义证据，但不能证明删除结果已经发生。

### 6. Conservative Downstream Projection

完整模型保留提议、部分支持、失败、不确定、未完成、证据和风险信息；下游可执行模型仅使用达到证据阈值的知识：

```text
Evidence-Grounded Functional Model
                ↓
       Conservative Projection
                ↓
      Downstream Planning Model
```

PDDL-compatible projection 可以将 semantic locations 映射为 predicates，将 interaction-supported functions 映射为 actions，并以位置约束/受支持的直接依赖作为保守适用条件、以观察到的成功结果作为 effects。PDDL 与 SafeSym 均为下游实例。

## 算法与实现映射

| 论文模块 | 代码位置 | 测试或证据 |
| --- | --- | --- |
| 功能假设提出 | 待代码核查后填写 | 提示词、结构化输出样例、候选标注准确性 |
| GUI 执行与前后观察 | 待代码核查后填写 | 执行轨迹、before/after observation、执行器状态 |
| 结果判断与模型更新 | 待代码核查后填写 | outcome/verification state 更新案例与标注评测 |
| Persistent frontier | 待代码核查后填写 | 未完成候选持久化、重访与恢复测试 |
| 风险判断与 commit boundary | 待机制收紧并完成代码核查后填写 | 风险案例、停止点、不可逆行为计数与覆盖率 |
| 保守下游投影 | SafeSym / PDDL 相关代码位置待核查 | 投影一致性、规划可执行性与行为验证 |
