# 方法

## 问题与符号

给定未知 Web 应用，系统通过 GUI observation 与浏览器交互接口获得轨迹：

> observation → GUI interaction → new observation

系统不依赖用户预定义任务，而是根据当前环境自动提出候选功能并持续归纳应用级功能模型。目标不是恢复完整、不可观察的内部业务状态。

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
| Risk annotation | 已选动作的二元风险判断、一个主要风险类型和页面证据 | 风险识别不等于阻止危险行为 |

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

### 2. Pre-Execution Risk Awareness

系统在候选 high-level function 执行前进行轻量风险判断：

1. 截取动作执行前的当前 GUI；
2. 将截图、已选 high-level action label 和完整的版本化风险库输入独立 VLM 判断；
3. 输出 `potential_risk`、一个主要 `risk_type`（无风险时为 null）和简短 `evidence`；
4. 普通探索将判断写入动作元数据，replay 将判断写入独立审计记录。

风险知识库提供稳定、可检查的类别定义、正例和明确低风险反例，VLM 负责结合动态页面上下文作二元判断。当前采用 shadow mode，风险标记不改变执行；检测异常 fail-open 并留存错误。人工确认、停止和拦截是可扩展执行策略。

### 3. Execution and Outcome Observation

浏览器执行器尝试执行被选中的 high-level function。系统记录动作前后观察，并分别判断执行器是否完成动作以及预期功能结果是否发生。浏览器执行器是可替换工具。

### 4. Evidence-Driven Model Update

系统依据执行记录和结果观察更新 outcome 与 verification state。失败、不确定和未完成结果分别保留；只有达到证据要求的知识才能供下游使用。每项结论应支持如下追溯：

> hypothesis source → execution trace → before/after observations → outcome judgment

### 5. Persistent Frontier

当前位置尚待验证或未完成的假设被持久保存，系统可以重访已访问位置继续建模。该机制服务于持续探索，不作为独立概念贡献。

### 6. Conservative Downstream Projection

完整模型保留提议、部分支持、失败、不确定、未完成、证据和风险信息；下游模型可以同时依据证据阈值和风险信息选择知识：

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
| 执行前风险感知 | `grounded_web/risk_detection.py`、`grounded_web/openai_risk_detection.py`、`grounded_web/web_kobe_explorer.py`、`grounded_web/risk_taxonomy_v1.json` | schema/prompt/provider 单测；普通探索与 replay 集成测试；真实 VLM 冒烟 |
| 保守下游投影 | SafeSym / PDDL 相关代码位置待核查 | 投影一致性、规划可执行性与行为验证 |
