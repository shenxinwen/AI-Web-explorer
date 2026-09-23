# VERA Problem Formulation and Method: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX manuscript; the Chinese text is a semantic translation for author review. This file is not included in the paper build.

## 3. Problem Formulation / 问题形式化

### Open-ended Web exploration / 开放式 Web 探索

**English**

Let $\mathcal{W}$ denote a Web application whose internal business state and transition rules are unknown. At interaction step $t$, an agent receives a GUI observation $o_t \in \mathcal{O}$ and selects a browser action $a_t \in \mathcal{A}$. Executing $a_t$ produces a new observation $o_{t+1}$ and executor-reported status $x_t$. The resulting interaction record is $\tau_t=(o_t,a_t,x_t,o_{t+1})$. Unlike task-conditioned Web agents, the agent is not given a user goal to complete. It instead explores the application to induce a reusable functional model from interaction traces. The model is limited to states and outcomes that are observable through the GUI or saved interaction artifacts; it is not intended to recover hidden application logic.

Here, $a_t$ denotes the semantic browser interaction submitted to the executor---such as clicking a labeled control or entering a value into a field---rather than every atomic mouse or keyboard event used internally to realize it.

**中文**

令 $\mathcal{W}$ 表示一个内部业务状态和转移规则未知的 Web 应用。在交互步骤 $t$，智能体接收 GUI 观察 $o_t \in \mathcal{O}$，并选择浏览器动作 $a_t \in \mathcal{A}$。执行 $a_t$ 后，环境产生新的观察 $o_{t+1}$，执行器返回状态 $x_t$。由此形成交互记录 $\tau_t=(o_t,a_t,x_t,o_{t+1})$。不同于以具体任务为条件的 Web 智能体，这里的智能体没有需要完成的用户目标，而是通过探索应用，从交互轨迹中归纳可复用的功能模型。该模型仅描述能够通过 GUI 或保存的交互工件观察到的状态与结果，不试图恢复应用内部不可见的业务逻辑。

这里，$a_t$ 表示提交给执行器的语义浏览器交互，例如点击带有语义标签的控件或在字段中输入值，而不是执行器为了完成该交互而在内部产生的每一次原子鼠标或键盘事件。

### Testable functional hypotheses / 可检验的功能假设

**English**

From an observation, the agent may propose a functional hypothesis

$$
h_i=(\ell_i,f_i,\hat{y}_i),
$$

where $\ell_i$ is a semantic location, $f_i$ is a high-level function, and $\hat{y}_i$ is an expected observable outcome. The claim states that executing $f_i$ at $\ell_i$ is expected to produce $\hat{y}_i$. Semantic locations and high-level functions describe application-level concepts rather than individual DOM elements. The model may additionally retain applicability metadata, including location constraints and observed direct action dependencies. Such dependencies record interaction-supported ordering relationships; they are not part of the outcome claim itself and are not asserted to be necessary or sufficient business preconditions.

**中文**

基于当前观察，智能体可以提出一个功能假设：

$$
h_i=(\ell_i,f_i,\hat{y}_i),
$$

其中，$\ell_i$ 表示语义位置，$f_i$ 表示高层功能，$\hat{y}_i$ 表示预期的可观察结果。该主张表示：在 $\ell_i$ 执行 $f_i$，预期产生 $\hat{y}_i$。语义位置和高层功能描述的是应用层概念，而不是单个 DOM 元素。模型还可以保存位置约束和观察到的直接动作依赖等适用性元数据；这些依赖不属于本次 outcome claim 本身，也不被宣称为必要或充分的业务前置条件。

**English**

The expected outcome $\hat{y}_i$ is generated together with the hypothesis and frozen before execution. It must identify a change that can be checked in a subsequent GUI observation or saved observable state. Freezing $\hat{y}_i$ prevents the claimed outcome from being retrofitted after observing the execution result. A proposed hypothesis is a candidate for verification, not yet a fact about the application.

**中文**

预期结果 $\hat{y}_i$ 与功能假设同时生成，并在执行前冻结。它必须指出一种能够在后续 GUI 观察或已保存的可观察状态中检查的变化。冻结 $\hat{y}_i$ 可以防止系统在看到执行结果之后反向修改原本声称要验证的结果。一个被提出的假设只是等待验证的候选，而不是关于应用的既成事实。

### Execution evidence and functional outcome / 执行证据与功能结果

**English**

For an attempted hypothesis $h_i$, the system stores an evidence packet

$$
e_i=(o_i^{\mathrm{pre}}, a_i, x_i, o_i^{\mathrm{post}}, m_i),
$$

where $o_i^{\mathrm{pre}}$ and $o_i^{\mathrm{post}}$ are the before and after observations, $a_i$ is the semantic interaction selected to test the claim, $x_i$ is the executor-reported status, and $m_i$ contains available metadata, evidence references, and any lower-level execution trace retained by the executor. Thus, a verification attempt is organized around a frozen claim and its selected semantic interaction, while the executor may use multiple atomic GUI operations to realize that interaction. An evidence judgment $J(h_i,e_i) \in \{\mathrm{Supported},\mathrm{Unsupported},\mathrm{Unresolved}\}$ evaluates whether $e_i$ supports the frozen expected outcome $\hat{y}_i$. `Unsupported` requires sufficiently complete evidence that does not support the expected outcome. A hypothesis that has not been attempted, whose execution failed before producing diagnostic evidence, or whose evidence is missing or only partial remains `Unresolved`. We separately record whether an executed interaction preserves the current semantic location or transitions to another one.

**中文**

对于一次针对假设 $h_i$ 的验证尝试，系统保存如下证据包：

$$
e_i=(o_i^{\mathrm{pre}}, a_i, x_i, o_i^{\mathrm{post}}, m_i),
$$

其中，$o_i^{\mathrm{pre}}$ 和 $o_i^{\mathrm{post}}$ 分别表示动作执行前后的观察，$a_i$ 表示为检验该主张而选择的语义交互，$x_i$ 表示执行器报告的状态，$m_i$ 包含可用的元数据、证据引用以及执行器保留的低层执行轨迹。因此，一次验证尝试围绕一个冻结的功能主张及其已选语义交互组织，而执行器可以使用多个原子 GUI 操作来完成该交互。证据判断 $J(h_i,e_i) \in \{\mathrm{Supported},\mathrm{Unsupported},\mathrm{Unresolved}\}$ 用于评价证据包 $e_i$ 是否支持执行前冻结的预期结果 $\hat{y}_i$。`Unsupported` 要求足够完整的证据不支持预期结果；尚未执行、执行失败且未产生可诊断证据、证据缺失或只有部分证据的假设均保持为 `Unresolved`。系统还单独记录已执行交互是保持在当前语义位置，还是转移到了另一个语义位置。

**English**

This definition distinguishes three claims that are otherwise easy to conflate: proposing $h_i$ establishes only that a candidate was discovered; an executor success $x_i$ establishes only that the interaction was reported as completed; and $J(h_i,e_i)=\mathrm{Supported}$ establishes that the available before--after evidence supports the expected functional outcome. Neither candidate discovery nor executor-reported success alone is sufficient for functional knowledge admission.

**中文**

这一定义区分了三个容易被混淆的层次：提出 $h_i$ 仅表示系统发现了一个候选；执行器返回成功 $x_i$ 仅表示该交互被报告为已经完成；只有 $J(h_i,e_i)=\mathrm{Supported}$ 才表示现有的动作前后证据支持预期的功能结果。候选发现和执行器报告成功，任何一个单独成立都不足以让相应内容作为功能知识被准入。

### Evidence judgment and knowledge admission / 证据判断与知识准入

**English**

The three-way evidence judgment is distinct from the binary admission indicator $A(h_i)\in\{0,1\}$. A hypothesis is admitted to the downstream-usable functional knowledge set only when its evidence is complete and supports its frozen expected outcome:

$$
A(h_i)=1
\quad\Longleftrightarrow\quad
\operatorname{complete}(e_i) \land
J(h_i,e_i)=\mathrm{Supported}.
$$

**中文**

三类证据判断不同于二元准入指示变量 $A(h_i)\in\{0,1\}$。只有当证据完整，并且证据支持冻结的预期结果时，该假设才会进入可供下游使用的功能知识集合：

$$
A(h_i)=1
\quad\Longleftrightarrow\quad
\operatorname{complete}(e_i) \land
J(h_i,e_i)=\mathrm{Supported}.
$$

**English**

When $A(h_i)=0$, the hypothesis is not admitted under the current evidence. This does not by itself mean that the proposed function is false. Non-admitted records and diagnostic reasons are retained for inspection and possible continuation; in particular, an unresolved attempt is not treated as negative evidence about the proposed function. We call the set of hypotheses, their evidence judgments and admission indicators, and their linked interaction evidence the evidence-grounded functional model $\mathcal{M}$.

**中文**

当 $A(h_i)=0$ 时，该假设在当前证据下不被准入。这本身并不意味着候选功能为假。未准入记录及其诊断原因仍被保留，以供检查或后续继续验证；特别是，一次 unresolved 尝试不会被视为反对该功能假设的负面证据。我们将功能假设、其证据判断与准入指示变量以及关联交互证据统称为证据驱动的功能模型 $\mathcal{M}$。

### Context-conditioned interaction risk / 上下文条件下的交互风险

**English**

Before executing a selected action, the system assigns an interaction-level risk annotation

$$
\rho_t=(b_t,k_t,q_t)=R(o_t,a_t,\mathcal{K}),
$$

where $b_t$ is a binary potential-risk judgment, $k_t$ is one primary risk type (or null when no risk is identified), $q_t$ is supporting interface evidence, and $\mathcal{K}$ is a versioned risk taxonomy. The object of this judgment is whether executing this selected interaction in the current GUI context may perform, enter, or prepare a risk-sensitive operation. The implemented judge receives the pre-action screenshot and a semantic label for $a_t$. It does not assign an intrinsic, context-free risk property to $f_i$, assess an entire verification process as one unit, classify the executor's internal atomic GUI events independently, or enumerate every possible action visible on the screen.

**中文**

在执行选定动作之前，系统生成一个交互级风险标注：

$$
\rho_t=(b_t,k_t,q_t)=R(o_t,a_t,\mathcal{K}),
$$

其中，$b_t$ 是二元潜在风险判断，$k_t$ 是一个主要风险类型（未识别到风险时为空），$q_t$ 是支撑该判断的界面证据，$\mathcal{K}$ 是带版本的风险分类体系。判断对象是：在当前 GUI 上下文中执行这个已选交互，是否可能实施、进入或准备一项风险敏感操作。实际判断器接收动作执行前的截图和 $a_t$ 的语义标签。该判断既不把风险视为高层功能 $f_i$ 固有且脱离上下文的属性，也不把整个验证过程合并为一个判断单元，不单独分类执行器内部的原子 GUI 事件，更不枚举屏幕上所有可能执行的动作。

**English**

The annotation $\rho_t$ is attached to the interaction record $\tau_t$. When $a_t$ is selected to test $h_i$, the record also links $\rho_t$ to that functional claim and its subsequent outcome evidence. Replay actions are assessed at the same semantic-action granularity and linked to their replay steps, even when they do not propose a new claim. In the system evaluated here, risk assessment records a pre-execution judgment but does not block or modify the selected action. Consequently, the formulation supports risk awareness and auditability, but does not by itself imply safer execution or an end-to-end safety guarantee.

**中文**

风险标注 $\rho_t$ 附着在交互记录 $\tau_t$ 上。当 $a_t$ 被选来检验 $h_i$ 时，该记录还会把 $\rho_t$ 与相应功能主张及其后续结果证据关联起来。即使 replay 动作不提出新主张，也会以相同的语义动作粒度进行判断，并关联到各自的 replay 步骤。在本文评测的系统中，风险判断在执行前被记录，但不会阻止或修改已经选定的动作。因此，这一形式化支持风险感知和可审查性，但其本身并不意味着执行过程已经更加安全，也不构成端到端的安全保证。

**English**

The overall problem is therefore to induce $\mathcal{M}$ through open-ended interaction while (i) admitting only functional claims supported by observable execution evidence, (ii) continuing to produce useful supported knowledge under a bounded exploration budget, and (iii) associating each selected evidence-gathering action with a context-conditioned pre-execution risk record.

**中文**

因此，本文的总体问题是：如何通过开放式交互归纳功能模型 $\mathcal{M}$，同时做到：（i）只准入由可观察执行证据支持的功能主张；（ii）在有限探索预算下继续产生有用且获得支持的功能知识；（iii）为每个已选的证据采集动作关联一条基于上下文的执行前风险记录。

---

## 4. VERA Method / VERA 方法

### Overview / 方法概述

**English**

VERA treats open-ended functional model induction as evidence production under two linked risks. The agent must act on an unfamiliar application to discover functionality, yet a proposed function or an executor-reported completion may not establish that the expected application-level outcome occurred. At the same time, the interactions used to obtain that evidence can alter the environment. The method therefore governs both how functional claims become persistent knowledge and how the actions used to test them are represented.

**中文**

VERA 将开放式功能模型归纳视为一个面临两类相互关联风险的证据生产过程。为了发现功能，智能体必须在陌生应用中采取行动；但被提出的功能或执行器报告的完成状态，并不能证明预期的应用级结果确实发生。与此同时，用于获得证据的交互本身可能改变环境。因此，VERA 的方法同时管理功能主张如何成为持久知识，以及用于检验这些主张的动作应当如何被表达和记录。

**English**

This view yields three design principles. First, *claims precede evidence*: VERA states a testable functional hypothesis and freezes its expected observable outcome before execution. Second, *knowledge requires outcome evidence*: executor status remains a diagnostic signal, while admission depends on whether the resulting observations support the frozen expectation. Third, *evidence acquisition is accountable interaction*: VERA assesses a selected semantic browser action in its current GUI context before execution and links the resulting risk record to the action, claim, and outcome evidence.

**中文**

这一观点导出三条设计原则。第一，*主张先于证据*：VERA 在执行前陈述可检验的功能假设，并冻结其预期可观察结果。第二，*知识需要结果证据*：执行器状态只作为诊断信号，知识准入取决于执行后观察是否支持冻结的预期。第三，*证据采集是可问责的交互*：VERA 在执行前结合当前 GUI 上下文判断已选语义浏览器动作，并将风险记录与动作、主张及结果证据关联起来。

**English**

VERA operationalizes these principles in a persistent exploration cycle. Candidate generation proposes claims; pre-execution risk assessment records potential consequences; browser interaction produces observable evidence; and post-execution verification governs admission to the functional model. A persistent frontier, dependency-aware selection, and replay preserve and recover unresolved verification opportunities so that evidence production can continue across locations. The candidate generator, browser executor, risk judge, and outcome verifier are replaceable components. VERA's method is the protocol that connects their outputs into a traceable functional model, rather than a new vision-language model or browser automation backend.

**中文**

VERA 在一个持续探索循环中操作化这些原则：候选生成提出功能主张；执行前风险判断记录潜在后果；浏览器交互产生可观察证据；执行后验证控制功能模型的知识准入。持久 frontier、依赖感知选择和 replay 保存并恢复未解决的验证机会，使证据生产能够跨语义位置继续进行。候选生成器、浏览器执行器、风险判断器和结果验证器都是可替换组件。VERA 的方法是把这些组件的输出连接成可追溯功能模型的协议，而不是一种新的视觉语言模型或浏览器自动化后端。

### Testable Function Hypothesis Proposal / 可检验功能假设的提出

**English**

To evaluate evidence rather than reinterpret it after the fact, VERA first turns a possible function into an explicit, testable claim. At a semantic location $\ell$, the proposal component conditions on the current GUI observation and the accumulated model to specify a high-level function together with its expected observable outcome. This representation targets application-level functionality---for example, adding an item or creating a project---rather than treating every visible widget as a separate function.

**中文**

为了评价证据，而不是在事后重新解释证据，VERA 首先把一个可能存在的功能转化为明确且可检验的主张。在语义位置 $\ell$，候选提出组件以当前 GUI 观察和已经积累的模型为条件，同时给出一个高层功能及其预期可观察结果。这种表达以应用级功能为对象，例如添加商品或创建项目，而不是把每个可见控件都当作一个独立功能。

**English**

The expected outcome defines in advance what subsequent evidence must support. It may describe equivalent visible manifestations, but cannot rely solely on hidden backend state. VERA stores the function and expectation together before browser interaction and does not revise the expectation in response to the observed result. The resulting hypothesis is registered as unresolved until execution evidence is judged. Proposal generation therefore creates a claim to test, not knowledge to admit.

**中文**

预期结果预先规定了后续证据必须支持什么。它可以描述多种等价的可见表现，但不能只依赖隐藏的后端状态。VERA 在浏览器交互开始前一并保存功能与预期，并且不会根据观察到的结果修改该预期。在执行证据得到判断之前，相应假设保持为 unresolved。因此，候选生成产生的是等待检验的主张，而不是可以直接准入的知识。

**English**

VERA keeps the outcome claim distinct from metadata describing where and when it has been observed to apply. Location constraints associate the claim with its semantic context. When testing a function relies on an earlier interaction, VERA also records that relation as an observed direct dependency. Such metadata helps select currently executable hypotheses and preserve local interaction context, but does not assert complete business preconditions or causal rules.

**中文**

VERA 将结果主张与描述其在何处、何时被观察为适用的元数据分开保存。位置约束把主张与其语义上下文关联起来。当某项功能的检验依赖更早的交互时，VERA 还将这种关系记录为观察到的直接依赖。这些元数据有助于选择当前可执行的假设并保留局部交互上下文，但并不宣称恢复了完整的业务前置条件或因果规则。

### Pre-Execution Risk Awareness / 执行前风险感知

**English**

Evidence acquisition is an interaction with the environment, not a neutral internal computation. VERA therefore assesses the selected semantic browser action before it is executed. Because the consequence of an action depends on the visible application state, the assessed object is the pair of the current GUI observation and the selected action, rather than a context-free function name. The same action label can consequently receive different judgments in different states.

**中文**

证据采集是对环境的交互，而不是中性的内部计算。因此，VERA 在已选语义浏览器动作执行前对其进行判断。由于动作后果取决于应用的可见状态，判断对象是当前 GUI 观察与已选动作的组合，而不是脱离上下文的功能名称。因此，同一动作标签在不同状态下可以得到不同判断。

**English**

For each selected action, VERA captures the current screenshot and combines it with the action label and a versioned risk taxonomy. An independent vision-language judge returns a structured record containing a binary \texttt{potential\_risk} decision, one primary \texttt{risk\_type} when risk is identified, and brief interface-grounded evidence. The taxonomy supplies a shared vocabulary of category definitions and examples; it is not a prediction model on its own.

**中文**

对于每个已选动作，VERA 截取当前界面，并将截图、动作标签和版本化风险分类体系组合为判断输入。独立的视觉语言判断器返回结构化记录，包括二元 \texttt{potential\_risk} 判断、识别到风险时的一个主要 \texttt{risk\_type}，以及简短的界面依据。风险分类体系提供共享的类别定义和示例词汇，而不是一个独立预测模型。

**English**

VERA attaches this record to the assessed action and, for an ordinary verification attempt, to the functional claim and subsequent outcome evidence. Replay actions receive separate records at the same semantic-action granularity. These records expose a pre-execution signal that a downstream policy could use for blocking or human confirmation. In the evaluated system, however, the signal is recorded without changing the selected action; if risk inference fails, execution continues and the error remains in the audit trail.

**中文**

VERA 将该记录关联到被判断的动作；对于普通验证尝试，还会将其与功能主张及后续结果证据关联。Replay 动作以相同的语义动作粒度分别生成记录。这些记录提供一种可供下游阻断或人工确认策略使用的执行前信号。不过，在本文评测的系统中，该信号只被记录，并不改变已选动作；如果风险推理失败，执行继续，同时错误保留在审计轨迹中。

### Execution and Evidence Collection / 执行与证据采集

**English**

Testing a functional claim requires evidence about the application-level outcome, not merely evidence that an interaction command was issued. The browser executor receives the selected semantic action and attempts to realize it. VERA stores the pre-execution observation, the concrete interaction trace, the executor-reported status, the post-execution observation, URLs, and any available structured state changes or evidence references. Together these fields form the evidence packet in Section 3.

**中文**

检验功能主张需要关于应用级结果的证据，而不只是某条交互命令已经发出的证据。浏览器执行器接收已选语义动作并尝试完成它。VERA 保存执行前观察、具体交互轨迹、执行器报告状态、执行后观察、URL，以及任何可用的结构化状态变化或证据引用。这些字段共同构成第 3 节定义的证据包。

**English**

This packet deliberately preserves both executor status and observable outcome evidence. A successful executor status can indicate that a click or input sequence completed even when the expected application-level change did not occur. Conversely, a reported failure may reflect grounding, timing, or environment errors rather than the absence of the proposed function. VERA uses the status diagnostically and defers knowledge admission until the evidence is compared with the frozen outcome claim.

**中文**

该证据包有意同时保留执行器状态和可观察结果证据。执行器报告成功可能只说明点击或输入序列已经完成，即使预期的应用级变化并未发生。反过来，执行器报告失败也可能源于动作定位、时序或环境错误，而不是候选功能不存在。VERA 将执行器状态作为诊断信号，并推迟知识准入，直到证据与冻结的结果主张完成比较。

### Evidence-Grounded Model Update / 基于证据的模型更新

**English**

Knowledge admission is a separate decision from both proposal and execution. The outcome verifier receives the frozen functional claim and its evidence packet, compares the expected outcome with the observed post-interaction state, and records a `Supported`, `Unsupported`, or `Unresolved` judgment. The current implementation uses a vision-language model, but the admission protocol does not depend on a particular verifier architecture.

**中文**

知识准入是独立于候选提出和动作执行的决定。结果验证器接收冻结的功能主张及其证据包，将预期结果与交互后的可观察状态进行比较，并记录 `Supported`、`Unsupported` 或 `Unresolved` 判断。当前实现使用视觉语言模型，但知识准入协议不依赖某种特定的验证器架构。

**English**

VERA admits a hypothesis only when the required evidence is complete and the evidence judgment is `Supported`, following Equation (4). The admitted record links the functional claim and frozen expectation to the execution trace, before--after observations, evidence judgment, and admission decision. Evidence that is missing, inconclusive, or inconsistent with the expectation does not enter the downstream-usable knowledge set. The associated claim and attempt nevertheless remain in the model with their judgment and diagnostic reason. This separation prevents unresolved execution problems from becoming functional facts while preserving them as future verification opportunities.

**中文**

按照公式（4），只有在必要证据完整且 evidence judgment 为 `Supported` 时，VERA 才准入该假设。准入记录把功能主张及其冻结预期与执行轨迹、动作前后观察、证据判断和准入决定关联起来。缺失、不确定或与预期不一致的证据不能进入可供下游使用的知识集合，但相应主张和尝试仍连同判断与诊断原因保留在模型中。这种区分防止未解决的执行问题变成功能事实，同时把它们保存为未来的验证机会。

### Persistent Evidence Production / 持久化证据生产

**English**

Conservative admission is useful only if exploration can continue producing evidence for claims that are not resolved immediately. An interaction may move the browser away from a claim's semantic location, an execution may fail, or a run may exhaust its current budget. VERA retains such hypotheses in a persistent frontier rather than equating interruption with rejection or discarding the verification opportunity.

**中文**

只有当探索能够继续为尚未立即解决的主张生产证据时，保守准入才真正有用。一次交互可能使浏览器离开主张所属的语义位置，执行可能失败，或者当前运行可能耗尽预算。VERA 将这些假设保存在持久 frontier 中，而不是把中断等同于拒绝，或直接丢弃验证机会。

**English**

The selection procedure prioritizes hypotheses whose observed direct dependencies are satisfied in the current context. When unresolved hypotheses remain at a previously visited location, VERA may replay an observed path to that location and resume evidence production. Replay restores a previously observed context; it does not relax the evidence judgment or admission rule.

**中文**

选择过程优先处理那些观察到的直接依赖已在当前上下文中满足的假设。当先前访问过的位置仍有未解决假设时，VERA 可以 replay 一条已经观察到的路径返回该位置并继续生产证据。Replay 恢复的是先前观察到的上下文，不会放宽证据判断或知识准入规则。

**English**

Replay is therefore a mechanism for recovering verification opportunities, not an uncounted exploration action. VERA records replay interactions and their pre-execution risk annotations separately from ordinary candidate attempts. This separation permits an evaluation to hold the ordinary attempt budget fixed while reporting the additional GUI cost and any supported functionality obtained after replay.

**中文**

因此，replay 是一种恢复验证机会的机制，而不是无需计费的探索动作。VERA 将 replay 交互及其执行前风险标注与普通候选尝试分开记录。这样的区分使实验可以在固定普通尝试预算的同时，单独报告 replay 带来的额外 GUI 成本，以及 replay 后获得支持的功能。

**English**

Persistent frontier, dependency-aware selection, and replay implement the evidence-production side of the method. They do not change the admission rule: regardless of how a candidate is reached, only an evidence-supported outcome can become admitted functional knowledge.

**中文**

持久 frontier、依赖感知选择和 replay 共同实现了方法中的证据生产部分。它们不会改变知识准入规则：无论系统通过何种方式到达候选，只有获得真实交互结果支持的内容才能成为被准入的功能知识。

### Traceable Functional Model / 可追溯功能模型

**English**

The resulting model preserves more than a list of discovered functions. For each claim, it links the frozen expectation, selected semantic action, pre-execution risk record, interaction trace, before--after evidence, evidence judgment, and admission decision. Supported, unsupported, and unresolved claims remain distinguishable, together with diagnostic reasons for non-admission. This trace is the common representation through which VERA accounts for both how evidence was acquired and why a claim did or did not become reusable knowledge.

**中文**

最终模型保存的不只是已发现功能的列表。对于每条主张，它将冻结的预期、已选语义动作、执行前风险记录、交互轨迹、动作前后证据、证据判断和准入决定关联起来。Supported、unsupported 和 unresolved 主张保持可区分，并保留未准入的诊断原因。借助这条共同轨迹，VERA 同时说明证据是如何获得的，以及一条主张为何成为或没有成为可复用知识。

**English**

Downstream consumers can use a conservative view containing only admitted functions, their semantic locations, observed direct dependencies, and supported outcomes, while the complete trace remains available for inspection or further verification. This interface does not require a particular planner and does not treat the induced model as a complete recovery of hidden business state or causal dynamics.

**中文**

下游使用者可以采用一个保守视图，其中只包含已准入功能、其语义位置、观察到的直接依赖和获得支持的结果；完整轨迹则继续用于检查或后续验证。该接口不依赖某种特定规划器，也不把归纳出的模型视为对隐藏业务状态或因果动态的完整恢复。

---

## Author-review questions / 建议重点审查的问题

1. **Knowledge object / 知识对象：** Does $h=(\ell,f,\hat{y})$ correctly capture the core location-conditioned outcome claim, with location constraints and observed direct dependencies retained separately as applicability metadata? / $h=(\ell,f,\hat{y})$ 是否准确表达了“位置条件下的结果主张”这一核心知识对象，同时将位置约束和观察到的直接依赖另行保存为适用性元数据？
2. **Admission semantics / 准入语义：** Does the binary indicator $A(h)\in\{0,1\}$ clearly separate non-admission from a judgment that the function is false? / 二元准入指示变量是否已清楚区分“当前不准入”与“该功能为假”？
3. **Risk object / 风险对象：** Does $\rho_t=R(o_t,a_t,\mathcal{K})$ clearly express a pre-execution judgment about each selected browser action in its current visual context, including action-level replay assessment? / $\rho_t=R(o_t,a_t,\mathcal{K})$ 是否清楚表达了对每个已选浏览器动作在当前视觉上下文中的执行前判断，并涵盖逐动作的 replay 风险评估？
4. **Unresolved reasons / Unresolved 原因：** Are not-attempted, execution failure, missing evidence, and partial evidence sufficient diagnostic subtypes for the appendix? / 尚未尝试、执行失败、证据缺失和部分证据是否足以作为附录中的诊断子类型？
5. **Traceable model / 可追溯模型：** Does the final subsection clearly explain why claims, action risk, execution evidence, judgment, and admission belong in one linked representation? / 最后一小节是否清楚解释了为什么功能主张、动作风险、执行证据、证据判断与准入决定应保存在同一关联表达中？
