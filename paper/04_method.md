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
| Expected observable outcome | 候选执行后应在 GUI 或保存的可观察状态中出现的结果；与候选同时产生并在执行前冻结 | 不包含隐藏后端状态，也不在看到 after observation 后改写 |
| Location constraint | 功能被提出、执行和观察时所在的位置 | 不等同于完整业务 precondition |
| Observed direct action dependency | 页面观察提出且由成功交互序列支持的直接顺序关系 | 不主张普遍必要、充分或严格因果关系 |
| Functional outcome | 功能结果状态与界面转移类型 | Executor Success 不等于 Functional Success |
| Verification state | 功能结论当前获得的支持程度 | 与运行时调度状态分离 |
| Interaction evidence | 支持结论的来源、轨迹、前后观察与结果判断 | 可追溯不等于形式化正确性保证 |
| Interaction-level risk annotation | 在当前 GUI observation 中执行已选动作的二元风险判断、一个主要风险类型和页面证据 | 属于具体交互语境，不是动作或功能的固定属性；风险识别不等于阻止危险行为 |

功能结果使用两个独立维度：

1. 结果状态：Success、Failure、Uncertain；
2. 界面转移：Location-Preserving、Location-Transition。

论文级 verification state：

- **Proposed**：已提出，尚无真实交互支持；
- **Partially Supported**：已有部分证据，不足以完整确认；
- **Interaction-Supported**：真实交互与结果观察提供充分支持；
- **Failed**：执行或结果观察明确不支持该假设；
- **Incomplete**：因人工中断、执行异常、预算结束或其他原因未完成验证。

pending、retryable、stale、blocked 等只作为实现层子状态。

## 方法概述：VERA

VERA（Verification and Environmental Risk Awareness）将开放探索组织为持续的功能知识归纳循环：C2 提出可检验功能假设并通过真实交互产生证据，C3 在每个已选验证动作执行前生成环境风险判断，C1 在执行后依据冻结预期与观察证据控制持久知识准入。探索是证据生产手段，可靠、可审查的功能模型是主要产物；当前风险判断以 shadow mode 支持监督和审计，不构成执行安全边界。

### 1. Testable Function Hypothesis Proposal

VLM 根据当前 GUI 和已有模型提出 semantic location、high-level function、可能的直接动作依赖，以及一句简短的 expected observable outcome。该结果只能描述执行后可从 GUI 或保存状态中检查的变化，可以包含多个等价的可见证据，但不得依赖隐藏后端状态。候选与 expected outcome 同时保存，并在动作执行前冻结；所有新内容先处于 Proposed 状态，不直接写成环境事实。VLM 是可替换的候选生成与观察工具。

### 2. Pre-Execution Risk Awareness

系统在候选 high-level function 执行前进行上下文条件风险判断：

1. 截取动作执行前的当前 GUI；
2. 将截图、已选 high-level action label 和完整的版本化风险库输入独立 VLM 判断；
3. 输出 `potential_risk`、一个主要 `risk_type`（无风险时为 null）和简短 `evidence`；
4. 普通探索将判断写入动作元数据，replay 将判断写入独立审计记录。

风险知识库提供稳定、可检查的类别定义、正例和明确低风险反例，VLM 负责结合动态页面上下文作二元判断。当前采用 shadow mode，风险标记不改变执行；检测异常 fail-open 并留存错误。人工确认、停止和拦截是可扩展执行策略。

风险判断的对象是 observation-conditioned interaction，即“在当前 GUI 状态下执行这个已选动作是否具有潜在环境风险”，而不是动作 label 或 high-level function 是否天然危险。同一语义动作在不同页面、数据和业务状态下可以得到不同判断。风险标注附着于具体 interaction attempt，并链接至相应功能假设、执行轨迹和结果证据；完整功能模型可以引用这些记录，但不把它们聚合成功能的上下文无关属性。

该模块的论文定位不是通用安全防线，而是开放式功能归纳中的风险注释层：每次判断与被选功能假设、执行前观察和后续交互轨迹关联，以支持过程监督与事后审查。

### 3. Execution and Evidence Observation

浏览器执行器尝试执行被选中的 high-level function。系统记录 executor-reported status、动作前后截图、URL、可用的结构化状态变化和证据引用，形成供功能知识判定使用的 evidence packet。浏览器执行器是可替换工具；其成功状态只说明具体交互被报告为完成。

### 4. Evidence-Driven Model Update

系统以冻结的 functional claim 和 expected outcome 为条件，判断执行后 evidence packet 是否支持预期结果。当前实现使用 VLM 作为可替换的证据判断器；方法贡献是主张—预期结果—证据—准入协议，而不是新的 VLM 模型。失败、证据不足和未完成结果分别保留以供审查，但不能作为已验证功能供下游使用。只有证据完整且 outcome judgment 为 success 的候选进入 admitted 状态。每项结论应支持如下追溯：

> functional claim + frozen expected outcome → execution trace → before/after observations → outcome judgment → admission decision

论文级准入状态使用 `Proposed → Admitted / Rejected`：Rejected 轨迹仍被持久保存，但不进入可供后续规划或探索复用的已验证功能集合。验证器异常或关键证据缺失时，知识准入采取保守处理，即不准入；这与运行时执行链路是否 fail-open 是两个不同问题。

### 5. Persistent Evidence Production

当前位置尚待验证或未完成的假设被持久保存，系统可以重访已访问位置继续建模。Persistent frontier 与 replay 服务于跨位置持续生产验证证据，不作为独立概念贡献，也不用于主张通用探索覆盖领先。

在论文概念上，开放探索循环（C2）负责发现候选并产生交互轨迹和前后观察；证据驱动模型（C1）负责判断预期 functional outcome 是否得到可观察证据支持，并据此作出知识准入决定。Executor-reported success 只是交互执行状态，不等同于 verified functional outcome。二者可以共享工程循环，但实验中分别控制证据输入与探索过程。

### 6. Conservative Downstream Projection

完整模型保留提议、部分支持、失败、不确定、未完成、证据和风险信息；下游模型可以同时依据证据阈值和风险信息选择知识：

```text
Evidence-Grounded Functional Verification and Knowledge Admission
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
| 执行前风险感知 | `grounded_web/risk_detection.py`、`grounded_web/openai_risk_detection.py`、`grounded_web/explorer.py`、`grounded_web/risk_taxonomy_v1.json` | schema/prompt/provider 单测；普通探索与 replay 集成测试；真实 VLM 冒烟 |
| 保守下游投影 | SafeSym / PDDL 相关代码位置待核查 | 投影一致性、规划可执行性与行为验证 |
