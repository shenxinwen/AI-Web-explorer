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
| Functional claim | `h=(semantic location, high-level function, frozen expected outcome)`；表示在该位置执行该功能预期产生相应可观察结果 | 知识准入的基本单位，不是脱离位置的抽象功能名 |
| Location constraint | 功能被提出、执行和观察时所在的位置或适用范围元数据 | 不与 semantic location 重复构成核心 claim，也不等同于完整业务 precondition |
| Observed direct action dependency | 页面观察提出且由成功交互序列支持的直接顺序关系，作为选择和适用性元数据保存 | 不是本次 outcome claim 的直接验证对象；不主张普遍必要、充分或严格因果关系 |
| Functional outcome | 功能结果状态与界面转移类型 | Executor Success 不等于 Functional Success |
| Evidence judgment | 冻结的预期结果在当前证据下为 Supported、Unsupported 或 Unresolved | 与运行时调度状态和知识准入分离 |
| Interaction evidence | 支持结论的来源、轨迹、前后观察与结果判断 | 可追溯不等于形式化正确性保证 |
| Interaction-level risk annotation | 在当前 GUI observation 中执行已选动作的二元风险判断、一个主要风险类型和页面证据 | 属于具体交互语境，不是动作或功能的固定属性；风险识别不等于阻止危险行为 |

功能结果使用两个独立维度：

1. 结果状态：Success、Failure、Uncertain；
2. 界面转移：Location-Preserving、Location-Transition。

论文级 evidence judgment 使用三类：

- **Supported**：完整交互证据支持执行前冻结的 expected observable outcome；
- **Unsupported**：足够完整的证据不支持或反驳该预期结果；
- **Unresolved**：尚未执行、执行异常、证据缺失或仅有部分证据，当前无法作出支持或不支持判断。

知识准入另以二元指示变量表达：仅当证据完整且 judgment 为 Supported 时准入；否则当前不准入，但不自动解释为功能为假。Proposed、partial evidence、incomplete execution、verifier error、pending、retryable、stale、blocked 等只作为实现层生命周期或诊断原因，不作为主文并列的证据类别。

## 方法概述：VERA

VERA（Verification and Environmental Risk Awareness）的核心设计是区分证据生产、知识准入与交互风险监督。开放探索提高功能发现的自主性，但也带来两类关联风险：候选或 executor success 可能在证据不足时污染持久模型，而验证未知功能的自主交互也可能对环境产生重要后果。VERA 将 C2 组织为共享的证据生产过程：它提出可检验功能假设并通过真实交互产生证据；C3 在每个已选验证动作执行前生成上下文相关的环境风险判断；C1 在执行后依据冻结预期与观察证据控制持久知识准入。

方法遵循三个不变量：（1）expected observable outcome 必须在执行前冻结，不能依据 after observation 事后改写；（2）candidate discovery 和 executor-reported success 均不能单独触发知识准入；（3）风险属于 observation-conditioned interaction，不是 high-level function 的上下文无关属性。知识准入在证据不足时采取保守策略，而风险判断在当前 shadow-mode 实验中 fail-open 并记录错误。这一区分服务于“持续产生证据”和“持久知识必须可靠”两种不同要求。

探索是证据生产手段，可靠、可审查的功能模型是主要产物；执行前风险判断是获得该模型时的交互监督与审计维度。安全是研究动机和长期目标，当前风险机制不构成执行安全边界，也不声称已经防止不可逆后果。

### 1. Testable Function Hypothesis Proposal

VLM 根据当前 GUI 和已有模型提出核心 functional claim `h=(ℓ,f,ŷ)`：semantic location `ℓ`、high-level function `f`，以及一句简短的 expected observable outcome `ŷ`。该结果只能描述执行后可从 GUI 或保存状态中检查的变化，可以包含多个等价的可见证据，但不得依赖隐藏后端状态。位置约束和 observed direct dependency 作为适用性与探索选择元数据另行保存，不被当前 outcome verification 自动视为已验证的普遍 precondition。候选与 expected outcome 同时保存，并在动作执行前冻结；新候选作为等待证据的 Unresolved claim，不直接写成环境事实。VLM 是可替换的候选生成与观察工具。

### 2. Pre-Execution Risk Awareness

系统在每个已选 browser action 执行前进行上下文条件风险判断：

1. 截取动作执行前的当前 GUI；
2. 将截图、已选 high-level action label 和完整的版本化风险库输入独立 VLM 判断；
3. 输出 `potential_risk`、一个主要 `risk_type`（无风险时为 null）和简短 `evidence`；
4. 普通探索将判断写入动作元数据，replay 将判断写入独立审计记录。

风险知识库提供稳定、可检查的类别定义、正例和明确低风险反例，VLM 负责结合动态页面上下文作二元判断。当前采用 shadow mode，风险标记不改变执行；检测异常 fail-open 并留存错误。人工确认、停止和拦截是可扩展执行策略。

风险判断的对象是 observation-conditioned selected action，可形式化为 `ρ_t=R(o_t,a_t,K)`：即“在当前 GUI 状态 `o_t` 下执行下一步已选 browser action `a_t` 是否具有潜在环境风险”。判断器实际接收执行前截图、该 action 的语义标签和风险 taxonomy。它不判断动作 label 或 high-level function 是否天然危险，也不把整个多动作 verification attempt 合并成单一风险对象。同一语义动作在不同页面、数据和业务状态下可以得到不同判断。普通探索的风险标注附着于具体 interaction attempt，并链接至相应 functional claim、执行轨迹和结果证据；replay 中的每个 action 也单独判断并关联其 replay step。完整功能模型可以引用这些记录，但不把它们聚合成功能的上下文无关属性。

该模块的论文定位不是通用安全防线，而是开放式功能归纳中的风险注释层：每次判断与被选功能假设、执行前观察和后续交互轨迹关联，以支持过程监督与事后审查。

### 3. Execution and Evidence Observation

浏览器执行器接收服务于当前 functional claim 的 selected browser action，并尝试完成该交互。系统记录 executor-reported status、动作前后截图、URL、可用的结构化状态变化和证据引用，形成供功能知识判定使用的 evidence packet。浏览器执行器是可替换工具；其成功状态只说明具体交互被报告为完成。

### 4. Evidence-Driven Model Update

系统以冻结的 functional claim 和 expected outcome 为条件，判断执行后 evidence packet 是否支持预期结果。当前实现使用 VLM 作为可替换的证据判断器；方法贡献是主张—预期结果—证据—准入协议，而不是新的 VLM 模型。原始实现中的 success/failed/uncertain outcome 与工件完整性在论文层映射为 Supported、Unsupported 或 Unresolved；只有证据完整且 judgment 为 Supported 的候选令 `A(h)=1`。未准入记录仍分别保留诊断原因以供审查。每项结论应支持如下追溯：

> functional claim + frozen expected outcome → execution trace → before/after observations → evidence judgment → admission indicator

论文级准入使用二元指示变量 `A(h) ∈ {0,1}`，避免把当前未准入误解为功能已被证明为假。未准入轨迹仍被持久保存，但不进入可供后续规划或探索复用的已验证功能集合。验证器异常或关键证据缺失时，知识准入采取保守处理，即 `A(h)=0`；这与运行时执行链路是否 fail-open 是两个不同问题。

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

PDDL-compatible projection 可以将 semantic locations 映射为 predicates，将 evidence-supported functions 映射为 actions，并以位置约束/受支持的直接依赖作为保守适用条件、以观察到的成功结果作为 effects。PDDL 与 SafeSym 均为下游实例。

## 算法与实现映射

| 论文模块 | 代码位置 | 测试或证据 |
| --- | --- | --- |
| 功能假设提出 | 待代码核查后填写 | 提示词、结构化输出样例、候选标注准确性 |
| GUI 执行与前后观察 | 待代码核查后填写 | 执行轨迹、before/after observation、执行器状态 |
| 结果判断与模型更新 | 待代码核查后填写 | evidence judgment、admission indicator 更新案例与标注评测 |
| Persistent frontier | 待代码核查后填写 | 未完成候选持久化、重访与恢复测试 |
| 执行前风险感知 | `grounded_web/risk_detection.py`、`grounded_web/openai_risk_detection.py`、`grounded_web/explorer.py`、`grounded_web/risk_taxonomy_v1.json` | schema/prompt/provider 单测；普通探索与 replay 集成测试；真实 VLM 冒烟 |
| 保守下游投影 | SafeSym / PDDL 相关代码位置待核查 | 投影一致性、规划可执行性与行为验证 |
