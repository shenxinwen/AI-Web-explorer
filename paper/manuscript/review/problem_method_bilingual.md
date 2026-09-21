# VERA Problem Formulation and Method: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX manuscript; the Chinese text is a semantic translation for author review. This file is not included in the paper build.

## 3. Problem Formulation / 问题形式化

### Open-ended Web exploration / 开放式 Web 探索

**English**

Let $\mathcal{W}$ denote a Web application whose internal business state and transition rules are unknown. At interaction step $t$, an agent receives a GUI observation $o_t \in \mathcal{O}$ and selects a browser action $a_t \in \mathcal{A}$. Executing $a_t$ produces a new observation $o_{t+1}$ and executor-reported status $x_t$. The resulting interaction record is $\tau_t=(o_t,a_t,x_t,o_{t+1})$. Unlike task-conditioned Web agents, the agent is not given a user goal to complete. It instead explores the application to induce a reusable functional model from interaction traces. The model is limited to states and outcomes that are observable through the GUI or saved interaction artifacts; it is not intended to recover hidden application logic.

**中文**

令 $\mathcal{W}$ 表示一个内部业务状态和转移规则未知的 Web 应用。在交互步骤 $t$，智能体接收 GUI 观察 $o_t \in \mathcal{O}$，并选择浏览器动作 $a_t \in \mathcal{A}$。执行 $a_t$ 后，环境产生新的观察 $o_{t+1}$，执行器返回状态 $x_t$。由此形成交互记录 $\tau_t=(o_t,a_t,x_t,o_{t+1})$。不同于以具体任务为条件的 Web 智能体，这里的智能体没有需要完成的用户目标，而是通过探索应用，从交互轨迹中归纳可复用的功能模型。该模型仅描述能够通过 GUI 或保存的交互工件观察到的状态与结果，不试图恢复应用内部不可见的业务逻辑。

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

where $o_i^{\mathrm{pre}}$ and $o_i^{\mathrm{post}}$ are the before and after observations, $a_i$ is the executed interaction, $x_i$ is the executor-reported status, and $m_i$ contains available metadata and evidence references. An evidence judgment $J(h_i,e_i) \in \{\mathrm{Supported},\mathrm{Unsupported},\mathrm{Unresolved}\}$ evaluates whether $e_i$ supports the frozen expected outcome $\hat{y}_i$. `Unsupported` requires sufficiently complete evidence that does not support the expected outcome. A hypothesis that has not been attempted, whose execution failed before producing diagnostic evidence, or whose evidence is missing or only partial remains `Unresolved`. We separately record whether an executed interaction preserves the current semantic location or transitions to another one.

**中文**

对于一次针对假设 $h_i$ 的验证尝试，系统保存如下证据包：

$$
e_i=(o_i^{\mathrm{pre}}, a_i, x_i, o_i^{\mathrm{post}}, m_i),
$$

其中，$o_i^{\mathrm{pre}}$ 和 $o_i^{\mathrm{post}}$ 分别表示动作执行前后的观察，$a_i$ 表示实际执行的交互，$x_i$ 表示执行器报告的状态，$m_i$ 包含可用的元数据和证据引用。证据判断 $J(h_i,e_i) \in \{\mathrm{Supported},\mathrm{Unsupported},\mathrm{Unresolved}\}$ 用于评价证据包 $e_i$ 是否支持执行前冻结的预期结果 $\hat{y}_i$。`Unsupported` 要求足够完整的证据不支持预期结果；尚未执行、执行失败且未产生可诊断证据、证据缺失或只有部分证据的假设均保持为 `Unresolved`。系统还单独记录已执行交互是保持在当前语义位置，还是转移到了另一个语义位置。

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

where $b_t$ is a binary potential-risk judgment, $k_t$ is one primary risk type (or null when no risk is identified), $q_t$ is supporting interface evidence, and $\mathcal{K}$ is a versioned risk taxonomy. The object of this judgment is whether executing this selected interaction in the current GUI context may perform, enter, or prepare a risk-sensitive operation. The implemented judge receives the pre-action screenshot and a semantic label for $a_t$. It does not assign an intrinsic, context-free risk property to $f_i$, assess an entire multi-action verification attempt as one unit, or enumerate every possible action visible on the screen.

**中文**

在执行选定动作之前，系统生成一个交互级风险标注：

$$
\rho_t=(b_t,k_t,q_t)=R(o_t,a_t,\mathcal{K}),
$$

其中，$b_t$ 是二元潜在风险判断，$k_t$ 是一个主要风险类型（未识别到风险时为空），$q_t$ 是支撑该判断的界面证据，$\mathcal{K}$ 是带版本的风险分类体系。判断对象是：在当前 GUI 上下文中执行这个已选交互，是否可能实施、进入或准备一项风险敏感操作。实际判断器接收动作执行前的截图和 $a_t$ 的语义标签。该判断既不把风险视为高层功能 $f_i$ 固有且脱离上下文的属性，也不把整个多动作验证尝试合并为一个判断单元，更不枚举屏幕上所有可能执行的动作。

**English**

The annotation $\rho_t$ is attached to the interaction record $\tau_t$. When $a_t$ is selected to test $h_i$, the record also links $\rho_t$ to that functional claim and its subsequent outcome evidence. Replay actions are assessed individually and linked to their replay steps, even when they do not propose a new claim. In the system evaluated here, risk assessment runs in shadow mode: it records a pre-execution judgment but does not block or modify the selected action. Consequently, the formulation supports risk awareness and auditability, but does not by itself imply safer execution or an end-to-end safety guarantee.

**中文**

风险标注 $\rho_t$ 附着在交互记录 $\tau_t$ 上。当 $a_t$ 被选来检验 $h_i$ 时，该记录还会把 $\rho_t$ 与相应功能主张及其后续结果证据关联起来。即使 replay 动作不提出新主张，也会逐动作进行判断并关联到各自的 replay 步骤。在本文评测的系统中，风险判断以 shadow mode 运行：系统在执行前记录判断，但不会阻止或修改已经选定的动作。因此，这一形式化支持风险感知和可审查性，但其本身并不意味着执行过程已经更加安全，也不构成端到端的安全保证。

**English**

The overall problem is therefore to induce $\mathcal{M}$ through open-ended interaction while (i) admitting only functional claims supported by observable execution evidence, (ii) continuing to produce useful supported knowledge under a bounded exploration budget, and (iii) associating each selected evidence-gathering action with a context-conditioned pre-execution risk record.

**中文**

因此，本文的总体问题是：如何通过开放式交互归纳功能模型 $\mathcal{M}$，同时做到：（i）只准入由可观察执行证据支持的功能主张；（ii）在有限探索预算下继续产生有用且获得支持的功能知识；（iii）为每个已选的证据采集动作关联一条基于上下文的执行前风险记录。

---

## 4. VERA Method / VERA 方法

### Overview / 方法概述

**English**

VERA organizes open-ended Web exploration as a cycle for producing, evaluating, and retaining functional knowledge. Given the current GUI observation and the functional model accumulated so far, the system proposes a testable function hypothesis and freezes an expected observable outcome. It then annotates the potential environmental risk of executing the selected verification action in the current context. A browser executor performs the interaction and returns an execution status, while VERA stores the before and after observations and associated metadata. Finally, an outcome verifier compares this evidence with the frozen expectation and controls whether the hypothesis is admitted to the persistent functional model.

**中文**

VERA 将开放式 Web 探索组织成一个持续生产、评价和保留功能知识的循环。给定当前 GUI 观察和此前累积的功能模型，系统提出一个可检验的功能假设，并冻结对应的预期可观察结果。随后，系统标注在当前上下文中执行已选验证动作可能带来的环境风险。浏览器执行器完成交互并返回执行状态，VERA 同时保存动作前后的观察以及相关元数据。最后，结果验证器将这些证据与冻结的预期结果进行比较，并据此决定是否将该假设准入持久功能模型。

**English**

This cycle separates three responsibilities. Open-ended exploration discovers candidates and produces interaction evidence; pre-execution risk awareness describes the potential consequence of the selected interaction; and post-execution verification governs knowledge admission. The candidate generator, browser executor, risk judge, and outcome verifier are replaceable components. VERA's method is the protocol connecting their outputs into a traceable functional model, rather than a new vision-language model or browser automation backend.

**中文**

这一循环区分了三项职责：开放式探索负责发现候选并产生交互证据；执行前风险感知负责描述已选交互的潜在后果；执行后验证负责控制知识准入。候选生成器、浏览器执行器、风险判断器和结果验证器都是可替换组件。VERA 的方法贡献在于把这些组件的输出连接为可追溯功能模型的协议，而不是提出一种新的视觉语言模型或浏览器自动化后端。

### Testable Function Hypothesis Proposal / 可检验功能假设的提出

**English**

At a semantic location $\ell$, a proposal component conditions on the current GUI observation and the existing model to generate one or more high-level function hypotheses. Each proposal defines a location-conditioned functional claim using a functional label and a concise expected observable outcome. The model separately retains applicability metadata, including location constraints and any directly observed action dependencies. The proposal operates at the level of application functions---for example, adding an item or creating a project---rather than enumerating every visible widget.

**中文**

在语义位置 $\ell$，候选提出组件以当前 GUI 观察和已有功能模型为条件，生成一个或多个高层功能假设。每个候选用功能标签和一条简洁的预期可观察结果定义一个位置条件下的功能主张。模型另行保存适用性元数据，包括位置约束和任何直接观察到的动作依赖。候选描述的是应用功能层面的行为，例如添加商品或创建项目，而不是枚举界面上每一个可见控件。

**English**

The expected outcome states what evidence should become observable if the function succeeds. It may allow equivalent visible manifestations, but it may not depend solely on hidden backend state. The hypothesis and expectation are stored together before the browser interaction begins and are not revised in response to the resulting observation. New hypotheses are registered as unresolved claims awaiting evidence. Thus, proposal generation expands the set of claims to test without asserting that those claims are already true.

**中文**

预期结果说明：如果该功能成功，应当能够观察到什么证据。它可以允许多种等价的可见表现，但不能只依赖隐藏的后端状态。功能假设和预期结果在浏览器交互开始前一并保存，且不会根据事后观察到的结果进行改写。新假设被登记为等待证据的 unresolved 主张。因此，候选生成扩展的是待检验主张的集合，而不是直接宣称这些主张已经成立。

**English**

When a proposed function depends on an earlier interaction, VERA records the dependency as an observed direct ordering relation. These relations help prioritize executable hypotheses and preserve the local interaction context, but they are deliberately narrower than general business preconditions or causal rules.

**中文**

当一个候选功能依赖于更早的交互时，VERA 将这种依赖记录为观察到的直接顺序关系。这些关系有助于优先选择当前可执行的假设，并保留局部交互上下文；但其含义被有意限定得比一般业务前置条件或因果规则更窄。

### Pre-Execution Risk Awareness / 执行前风险感知

**English**

Before executing each selected browser action, VERA captures the current screenshot and constructs a risk-query tuple containing the screenshot, the semantic label of that action, and the complete versioned risk taxonomy. An independent vision-language judge returns a structured record with a binary \texttt{potential\_risk} decision, one primary \texttt{risk\_type} when risk is identified, and brief interface-grounded evidence. The taxonomy supplies stable category definitions, positive examples, and explicit low-risk counterexamples; it is shared output vocabulary rather than a prediction model on its own.

**中文**

在执行每个已选浏览器动作之前，VERA 截取当前界面，并构造一个风险查询元组，其中包含截图、该动作的语义标签和完整的版本化风险分类体系。一个独立的视觉语言判断器返回结构化记录，包括二元 \texttt{potential\_risk} 判断、识别到风险时的一个主要 \texttt{risk\_type}，以及简短的界面依据。风险分类体系提供稳定的类别定义、正例和明确的低风险反例；它是各条件共享的输出词汇，而不是一个独立的预测模型。

**English**

Risk is assessed for the observation-conditioned selected action. The same action label may therefore receive different judgments on different pages or under different visible application states. VERA attaches the resulting record to the particular hypothesis and interaction attempt, rather than storing risk as a context-free property of a high-level function or an aggregate property of a multi-action verification attempt. Ordinary exploration actions store the annotation in their action metadata; every replay action is assessed separately and retains the same information in an audit record linked to its replay step.

**中文**

风险判断针对的是以当前观察为条件的已选动作。因此，同一个动作标签在不同页面或不同可见应用状态下可能得到不同判断。VERA 将风险记录附着到具体的功能假设和交互尝试，而不是将风险保存为某个高层功能脱离上下文后的固定属性，也不把它作为整个多动作验证尝试的聚合属性。普通探索动作把风险标注保存在动作元数据中；每个 replay 动作也会被单独判断，并将相同信息保存在与该 replay 步骤关联的审计记录中。

**English**

The evaluated system uses the detector in shadow mode. Its output does not cancel, replace, or modify the selected action. If risk inference fails, the execution path continues and the error is recorded. This fail-open execution policy preserves the exploration process for measurement, while making clear that the risk component is an awareness and audit layer rather than an execution-time safety boundary.

**中文**

本文评测的系统以 shadow mode 使用风险检测器。检测结果不会取消、替换或修改已选动作。如果风险推理失败，执行链路仍然继续，同时记录该错误。这种 fail-open 执行策略使探索过程能够继续用于测量，也明确表明风险组件是一层感知与审计机制，而不是执行时的安全边界。

### Execution and Evidence Collection / 执行与证据采集

**English**

The browser executor receives the selected browser action that serves the current functional claim and attempts to realize that interaction. VERA stores the pre-execution observation, the concrete interaction trace, the executor-reported status, the post-execution observation, URLs, and any available structured state changes or evidence references. Together these fields form the evidence packet defined in Section 3.

**中文**

浏览器执行器接收服务于当前功能主张的已选浏览器动作，并尝试完成该交互。VERA 保存执行前观察、具体交互轨迹、执行器报告状态、执行后观察、URL，以及任何可用的结构化状态变化或证据引用。这些字段共同构成第 3 节定义的证据包。

**English**

The executor status is retained as a diagnostic signal, not used as the final functional truth label. In particular, an executor may report success after completing a click or input sequence even when the intended application-level outcome did not occur. Conversely, an execution failure may reflect grounding, timing, or environment errors rather than the absence of the proposed function. VERA therefore defers persistent knowledge admission until the evidence packet is evaluated against the frozen expected outcome.

**中文**

执行器状态被保留为诊断信号，而不被用作最终的功能事实标签。具体而言，执行器可能在完成点击或输入序列后报告成功，即使预期的应用级结果并未发生。反过来，一次执行失败也可能源于动作定位、时序或环境错误，而不是说明候选功能不存在。因此，VERA 会推迟持久知识准入，直到证据包依据冻结的预期结果完成评价。

### Evidence-Grounded Model Update / 基于证据的模型更新

**English**

The outcome verifier receives the frozen functional claim, its expected observable outcome, and the evidence packet. It decides whether the observed post-interaction state supports the expectation and records a `Supported`, `Unsupported`, or `Unresolved` evidence judgment. The current implementation uses a vision-language model for this judgment, but the admission protocol does not depend on a particular verifier architecture.

**中文**

结果验证器接收冻结的功能主张、对应的预期可观察结果以及证据包。它判断交互后的可观察状态是否支持该预期，并记录 `Supported`、`Unsupported` 或 `Unresolved` 证据判断。当前实现使用视觉语言模型完成这一判断，但知识准入协议并不依赖某一种特定的验证器架构。

**English**

VERA admits a hypothesis only when the required evidence is complete and the evidence judgment is `Supported`, following Equation (4). The admitted record links the functional claim and frozen expectation to the execution trace, before--after observations, evidence judgment, and admission indicator. Evidence that is missing, inconclusive, or inconsistent with the expectation does not enter the downstream-usable knowledge set. The associated attempt is nevertheless retained so that failure and uncertainty remain auditable.

**中文**

按照公式（4），只有在必要证据完整且 evidence judgment 为 `Supported` 时，VERA 才准入该假设。准入记录把功能主张及其冻结预期与执行轨迹、动作前后观察、证据判断和准入指示变量关联起来。缺失、不确定或与预期不一致的证据不能进入可供下游使用的知识集合，但相应尝试仍会被保留，以便失败和不确定情况可以被审查。

**English**

Knowledge admission is conservative even though risk inference is fail-open for execution. A risk-detector error does not halt the browser interaction, whereas an outcome-verification error or incomplete evidence cannot produce admitted knowledge. This asymmetry separates continuity of evidence production from the reliability requirement imposed on persistent knowledge.

**中文**

尽管风险推理在执行层采用 fail-open 策略，知识准入仍然是保守的。风险检测器出错不会中止浏览器交互，而结果验证器出错或证据不完整则不能产生被准入的知识。这种不对称设计把“持续产生证据”的要求与“持久知识必须可靠”的要求区分开来。

### Persistent Evidence Production / 持久化证据生产

**English**

Open-ended exploration can leave hypotheses unresolved when an interaction moves away from their semantic location, encounters an execution error, or exhausts the current budget. VERA maintains these hypotheses in a persistent frontier instead of discarding them. The selection procedure prioritizes hypotheses whose observed direct dependencies are satisfied in the current context. When unresolved hypotheses remain at a previously visited location, the system may replay an observed path to that location and resume evidence production.

**中文**

在开放式探索中，如果一次交互离开了假设所属的语义位置、遇到执行错误，或耗尽了当前预算，一些假设可能仍未得到解决。VERA 不会丢弃这些假设，而是将其保存在持久 frontier 中。选择过程优先考虑那些观察到的直接依赖已经在当前上下文中满足的假设。当先前访问过的位置仍存在未解决假设时，系统可以 replay 一条已观察到的路径返回该位置，并继续产生验证证据。

**English**

Replay is therefore a mechanism for recovering verification opportunities, not an uncounted exploration action. VERA records replay interactions and their pre-execution risk annotations separately from ordinary candidate attempts. This separation permits an evaluation to hold the ordinary attempt budget fixed while reporting the additional GUI cost and any supported functionality obtained after replay.

**中文**

因此，replay 是一种恢复验证机会的机制，而不是无需计费的探索动作。VERA 将 replay 交互及其执行前风险标注与普通候选尝试分开记录。这样的区分使实验可以在固定普通尝试预算的同时，单独报告 replay 带来的额外 GUI 成本，以及 replay 后获得支持的功能。

**English**

Persistent frontier, dependency-aware selection, and replay implement the evidence-production side of the method. They do not change the admission rule: regardless of how a candidate is reached, only an evidence-supported outcome can become admitted functional knowledge.

**中文**

持久 frontier、依赖感知选择和 replay 共同实现了方法中的证据生产部分。它们不会改变知识准入规则：无论系统通过何种方式到达候选，只有获得真实交互结果支持的内容才能成为被准入的功能知识。

### Conservative Downstream Projection / 保守的下游投影

**English**

The complete VERA model retains supported, unsupported, and unresolved claims, including diagnostic reasons for non-admission, alongside admitted knowledge, evidence, and interaction-level risk annotations. A downstream consumer need not receive all of this internal state. VERA instead exposes a conservative projection that selects only admitted functions and preserves their semantic locations, supported direct dependencies, and observed outcomes.

**中文**

完整的 VERA 模型在保存已准入知识、相关证据和交互级风险标注的同时，也保留 supported、unsupported 和 unresolved 主张以及未准入的诊断原因。下游使用者不必接收全部内部状态。VERA 提供一个保守投影，只选择已准入功能，并保留其语义位置、获得支持的直接依赖和观察到的结果。

**English**

For symbolic planning, one possible projection maps semantic locations to predicates and admitted functions to actions. Location constraints and supported direct dependencies provide conservative applicability conditions, while observed successful outcomes provide effects. Risk records may remain available to a downstream policy as contextual metadata, but the current shadow-mode system does not prescribe a blocking policy. The projection is an interface for using the induced model, not a claim that VERA recovers complete preconditions, causal dynamics, or hidden business state.

**中文**

对于符号规划，一种可能的投影方式是把语义位置映射为谓词，把已准入功能映射为动作。位置约束和获得支持的直接依赖提供保守的适用条件，观察到的成功结果则提供动作效果。风险记录可以作为上下文元数据继续提供给下游策略，但当前采用 shadow mode 的系统并未规定阻断策略。这种投影只是使用所归纳模型的一种接口，并不意味着 VERA 恢复了完整的前置条件、因果动态或隐藏业务状态。

---

## Author-review questions / 建议重点审查的问题

1. **Knowledge object / 知识对象：** Does $h=(\ell,f,\hat{y})$ correctly capture the core location-conditioned outcome claim, with location constraints and observed direct dependencies retained separately as applicability metadata? / $h=(\ell,f,\hat{y})$ 是否准确表达了“位置条件下的结果主张”这一核心知识对象，同时将位置约束和观察到的直接依赖另行保存为适用性元数据？
2. **Admission semantics / 准入语义：** Does the binary indicator $A(h)\in\{0,1\}$ clearly separate non-admission from a judgment that the function is false? / 二元准入指示变量是否已清楚区分“当前不准入”与“该功能为假”？
3. **Risk object / 风险对象：** Does $\rho_t=R(o_t,a_t,\mathcal{K})$ clearly express a pre-execution judgment about each selected browser action in its current visual context, including action-level replay assessment? / $\rho_t=R(o_t,a_t,\mathcal{K})$ 是否清楚表达了对每个已选浏览器动作在当前视觉上下文中的执行前判断，并涵盖逐动作的 replay 风险评估？
4. **Unresolved reasons / Unresolved 原因：** Are not-attempted, execution failure, missing evidence, and partial evidence sufficient diagnostic subtypes for the appendix? / 尚未尝试、执行失败、证据缺失和部分证据是否足以作为附录中的诊断子类型？
5. **Downstream projection / 下游投影：** Since the downstream evaluation is unfinished, should this subsection remain in the main method or move to the appendix until corresponding evidence is available? / 由于下游实验尚未完成，这一小节应继续保留在主方法中，还是暂时移至附录？
