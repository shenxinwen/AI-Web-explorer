# VERA Problem Formulation and Method: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation for author review.

## Problem Formulation / 问题形式化

### Open-ended functional model induction / 开放式功能模型归纳

**English**

Let $\mathcal{W}$ be a Web application with unknown business state and transition rules. At step $t$, an agent observes the GUI $o_t\in\mathcal{O}$, selects a semantic browser action $a_t\in\mathcal{A}$, and receives an executor-reported status $x_t$ and new observation $o_{t+1}$. The interaction record is $\tau_t=(o_t,a_t,x_t,o_{t+1})$. The agent has no predefined user task; its objective is to induce a reusable functional model from observable interaction. The model describes GUI-grounded functions and outcomes, not hidden application logic.

**中文**

令 $\mathcal{W}$ 表示业务状态和转移规则未知的 Web 应用。在步骤 $t$，智能体观察 GUI $o_t\in\mathcal{O}$，选择语义浏览器动作 $a_t\in\mathcal{A}$，并得到执行器报告状态 $x_t$ 和新观察 $o_{t+1}$。交互记录为 $\tau_t=(o_t,a_t,x_t,o_{t+1})$。智能体没有预定义用户任务，其目标是从可观察交互中归纳可复用功能模型。该模型描述 GUI grounding 的功能与结果，而不是隐藏的应用逻辑。

### Functional claims and outcome evidence / 功能主张与结果证据

**English**

At a semantic location, the agent may propose $h_i=(\ell_i,f_i,\hat{y}_i)$, where $\ell_i$ is the location, $f_i$ is a high-level function, and $\hat{y}_i$ is its expected observable outcome. The outcome is fixed before execution so that subsequent evidence evaluates a prior claim rather than a post-hoc interpretation. Location constraints and observed direct dependencies may be retained as applicability metadata, but are not complete business preconditions.

For an attempted claim, VERA stores $e_i=(o_i^{\mathrm{pre}},a_i,x_i,o_i^{\mathrm{post}},m_i)$, where $m_i$ contains the available trace, structured changes, and evidence references. An evidence judgment $J(h_i,e_i)\in\{\textsc{Supported},\textsc{Unsupported},\textsc{Unresolved}\}$ states whether complete observable evidence supports the frozen outcome. Unsupported requires sufficiently complete contrary evidence; unattempted claims, failed executions without diagnostic evidence, and partial evidence remain Unresolved. This separates candidate discovery, executor-reported completion, and evidence-supported functional outcome.

**中文**

在语义位置上，智能体可以提出 $h_i=(\ell_i,f_i,\hat{y}_i)$，其中 $\ell_i$ 是位置，$f_i$ 是高层功能，$\hat{y}_i$ 是预期可观察结果。该结果在执行前固定，使后续证据评价事前主张，而不是事后解释。位置约束和观察到的直接依赖可以作为适用性元数据保存，但不等于完整业务前置条件。

对于被尝试的主张，VERA 保存 $e_i=(o_i^{\mathrm{pre}},a_i,x_i,o_i^{\mathrm{post}},m_i)$，其中 $m_i$ 包含可用轨迹、结构化变化和证据引用。证据判断 $J(h_i,e_i)\in\{\textsc{Supported},\textsc{Unsupported},\textsc{Unresolved}\}$ 表示完整可观察证据是否支持冻结结果。Unsupported 需要足够完整的相反证据；未尝试主张、没有诊断证据的执行失败和部分证据均保持为 Unresolved。这样可区分候选发现、执行器报告完成和证据支持的功能结果。

### Knowledge admission and interaction risk / 知识准入与交互风险

**English**

Evidence judgment is distinct from the binary decision to expose a claim as downstream-usable knowledge: $A(h_i)=1$ iff $\operatorname{complete}(e_i)\land J(h_i,e_i)=\textsc{Supported}$. A non-admitted claim is not necessarily false; its judgment, diagnostic reason, and evidence remain available for inspection or later verification. We denote the resulting evidence-grounded functional model by $\mathcal{M}$.

Before action $a_t$ is executed under observation $o_t$, the agent produces $\rho_t=(b_t,k_t,q_t)=R(o_t,a_t,\mathcal{K})$, where $b_t$ is a binary potential-risk judgment, $k_t$ is one primary type (or null), $q_t$ is supporting interface evidence, and $\mathcal{K}$ is a versioned taxonomy. The assessed object is the selected semantic action in its current GUI context, not a context-free property of $f_i$. The risk record is attached to $\tau_t$ and, when the action tests $h_i$, to the same evidence chain used for outcome judgment. Replay actions receive their own action-level records.

The problem is to induce $\mathcal{M}$ under a bounded interaction budget while admitting only outcome-supported claims, sustaining evidence production across locations, and making the potential environmental consequences of evidence-gathering actions explicit before execution.

**中文**

证据判断不同于是否把主张暴露为下游可用知识的二元决定：当且仅当 $\operatorname{complete}(e_i)\land J(h_i,e_i)=\textsc{Supported}$ 时，$A(h_i)=1$。未准入主张不一定为假；其判断、诊断原因和证据仍可用于检查或后续验证。我们把最终的证据驱动功能模型记为 $\mathcal{M}$。

在观察 $o_t$ 下执行动作 $a_t$ 之前，智能体产生 $\rho_t=(b_t,k_t,q_t)=R(o_t,a_t,\mathcal{K})$，其中 $b_t$ 是二元潜在风险判断，$k_t$ 是一个主要类型（或为空），$q_t$ 是支撑界面证据，$\mathcal{K}$ 是版本化分类体系。判断对象是当前 GUI 上下文中的已选语义动作，而不是 $f_i$ 的上下文无关属性。风险记录附着到 $\tau_t$；当动作检验 $h_i$ 时，它还会关联到用于结果判断的同一证据链。Replay 动作分别生成动作级记录。

总体问题是在有限交互预算下归纳 $\mathcal{M}$，同时只准入获得结果证据支持的主张、跨位置维持证据生产，并在执行前显式表达证据采集动作的潜在环境后果。

## VERA Method / VERA 方法

### Design principles and overview / 设计原则与概述

**English**

VERA treats open-ended functional model induction as evidence production under two linked risks. A proposed function or executor-reported completion may not establish the expected application-level outcome, while the interaction used to obtain that evidence can itself alter the environment. The method therefore governs both how claims become persistent knowledge and how their acquisition actions are represented.

Three principles follow. First, *claims precede evidence*: the expected observable outcome is fixed before execution. Second, *knowledge requires outcome evidence*: executor status is diagnostic, whereas admission depends on support for the frozen outcome. Third, *evidence acquisition is traceable interaction*: the selected action receives a contextual risk record linked to the claim, execution, and outcome evidence. VERA operationalizes these principles in a persistent loop that proposes claims, records pre-action risk, collects evidence, judges outcomes, and preserves unresolved verification opportunities. Its generators, executor, and judges are replaceable; the method is the protocol connecting their outputs into $\mathcal{M}$.

**中文**

VERA 将开放式功能模型归纳视为两类关联风险下的证据生产。候选功能或执行器报告完成未必能证明预期应用级结果，而用于获得证据的交互本身可能改变环境。因此，该方法同时管理主张如何成为持久知识，以及获取主张证据的动作如何被表达。

由此产生三条原则。第一，*主张先于证据*：预期可观察结果在执行前固定。第二，*知识需要结果证据*：执行器状态是诊断信号，准入取决于证据是否支持冻结结果。第三，*证据采集是可追溯交互*：已选动作获得上下文风险记录，并与主张、执行和结果证据关联。VERA 在持续循环中操作化这些原则：提出主张、记录动作前风险、采集证据、判断结果并保留未解决验证机会。生成器、执行器和判断器均可替换；方法本身是把它们的输出连接到 $\mathcal{M}$ 的协议。

### From functional claim to knowledge admission / 从功能主张到知识准入

**English**

At semantic location $\ell$, the proposal component conditions on the current GUI and accumulated model to specify a high-level function and expected observable outcome. Proposals describe application-level functionality rather than every widget. The expectation may allow equivalent visible manifestations but cannot rely only on hidden state. It is stored before interaction and not revised after observing the result; the new hypothesis initially remains unresolved.

The browser executor receives the selected semantic action. VERA retains the pre-execution observation, concrete trace, executor status, post-execution observation, URLs, and available changes or evidence references. Preserving both status and outcome evidence is essential: an interaction sequence can complete without the intended effect, while failure can reflect grounding or timing rather than absence of the function.

The verifier compares this packet with the frozen claim and assigns Supported, Unsupported, or Unresolved. VERA then admits only complete, supporting evidence. Non-admitted claims remain linked to evidence and diagnostic reasons. Location constraints and observed direct dependencies help select currently executable hypotheses but do not change the outcome claim or assert complete preconditions.

**中文**

在语义位置 $\ell$，候选组件根据当前 GUI 和累积模型指定一个高层功能及其预期可观察结果。候选描述应用级功能，而不是每个控件。预期可以允许等价的可见表现，但不能只依赖隐藏状态。它在交互前保存，观察结果后不再修改；新假设最初保持 unresolved。

浏览器执行器接收已选语义动作。VERA 保存执行前观察、具体轨迹、执行器状态、执行后观察、URL 以及可用变化或证据引用。同时保留状态和结果证据非常重要：交互序列可能完成但未产生预期效果，失败也可能来自 grounding 或时序，而不是功能不存在。

验证器把该证据包与冻结主张比较，并给出 Supported、Unsupported 或 Unresolved。VERA 只准入完整且支持主张的证据。未准入主张仍与证据和诊断原因关联。位置约束与观察到的直接依赖帮助选择当前可执行假设，但不会改变结果主张，也不宣称完整前置条件。

### Pre-execution risk awareness / 执行前风险感知

**English**

Evidence acquisition is an environmental interaction, not a neutral internal operation. Before each selected action, VERA combines its semantic label with the current screenshot and a versioned risk taxonomy. An independent vision-language judge returns a binary potential-risk decision, one primary type when applicable, and brief interface-grounded evidence. Because risk is GUI-conditioned, identical action labels can receive different judgments in different states. VERA links each record to the action and, for ordinary verification, to the claim and later outcome evidence; replay steps are assessed separately. A downstream policy could use this signal for blocking or human confirmation. In the evaluated system, however, the record does not alter the action, and a risk-inference error is retained while execution continues.

**中文**

证据采集是环境交互，而不是中性的内部操作。每个动作执行前，VERA 将其语义标签与当前截图和版本化风险分类体系结合。独立视觉语言判断器返回二元潜在风险判断、适用时的一个主要类型和简短界面依据。由于风险以 GUI 为条件，相同动作标签在不同状态下可以得到不同判断。VERA 把每条记录关联到动作；对于普通验证，还关联到主张和后续结果证据；replay 步骤分别判断。下游策略可以使用该信号进行阻断或人工确认。不过在本文评测系统中，该记录不改变动作；风险推理错误被保留，执行继续。

### Persistent evidence production and traceability / 持续证据生产与可追溯性

**English**

Conservative admission creates unresolved claims when interaction leaves a location, execution fails, or the budget ends. VERA retains them in a persistent frontier rather than equating interruption with rejection. Selection prioritizes claims whose observed dependencies are satisfied; replay can restore an observed path and resume evidence production without relaxing admission. Replay is additional interaction, so operations, GUI actions, and risk annotations are reported separately from ordinary attempts.

The resulting model links each claim to its frozen expectation, selected action, pre-execution risk record, interaction trace, before--after evidence, judgment, and admission decision. Supported, unsupported, and unresolved claims remain distinguishable. Downstream consumers may use a conservative view of admitted functions and supported outcomes, while the complete trace remains available for inspection or further verification.

**中文**

当交互离开位置、执行失败或预算结束时，保守准入会留下未解决主张。VERA 将其保存在 persistent frontier 中，而不是把中断等同于拒绝。选择机制优先处理观察到的依赖已满足的主张；replay 可以恢复已经观察到的路径并继续生产证据，但不会放宽准入。Replay 是额外交互，因此其操作、GUI 动作和风险标注与普通尝试分开报告。

最终模型把每条主张与冻结预期、已选动作、执行前风险记录、交互轨迹、前后证据、判断和准入决定关联起来。Supported、unsupported 和 unresolved 主张保持可区分。下游可以使用只包含已准入功能和支持结果的保守视图，完整轨迹则用于检查或后续验证。
