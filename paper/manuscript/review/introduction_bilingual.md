# VERA Introduction: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation for author review.

## Application scenario and open-ended exploration / 应用场景与开放式探索

**English**

Consider an agent entering a previously unseen Web application. Rather than receiving a single user goal, the agent must determine what the application can do and organize its experience into a functional model that can support future tasks. Such a model could amortize interaction across tasks: instead of rediscovering the interface for every new request, a downstream agent could reuse grounded knowledge about available functions, where they apply, and what observable outcomes they produce. Building this model, however, requires more than passively reading a page. Many application functions become evident only after the agent changes state through interaction.

This setting motivates *open-ended Web exploration*. Task-conditioned agents typically search for a path that completes a specified objective; they need not discover functionality irrelevant to that objective or preserve it for later use. An open-ended explorer instead proposes its own functional hypotheses, visits different application states, and accumulates knowledge for goals that are not yet known. These paradigms are complementary rather than universally ordered: open-ended exploration is aligned with reusable model construction, but its autonomy removes constraints supplied by a concrete goal.

**中文**

设想一个智能体进入此前从未见过的 Web 应用。它不是接收一个单一用户目标，而是要判断该应用能够做什么，并把交互经验组织成可支持未来任务的功能模型。这样的模型能够在不同任务间复用交互成本：下游智能体不必为每个新请求重新发现界面，而可以复用关于可用功能、适用位置和可观察结果的落地知识。然而，构建该模型不能只靠被动读取页面；许多应用功能只有在智能体通过交互改变状态后才会显现。

这促使我们研究*开放式 Web 探索*。任务导向智能体通常寻找完成指定目标的路径，不必发现与当前目标无关的功能，也不必保存这些功能供未来使用。开放式探索器则主动提出功能假设、访问不同应用状态，并为尚未出现的目标积累知识。两种范式是互补的：开放式探索更契合可复用模型构建，但其自主性也削弱了具体用户目标所提供的行为约束。

## Two linked risks / 两类关联风险

**English**

The first resulting challenge is epistemic. A proposed function is only a candidate, and an executor-reported success establishes only that an interaction was completed. Neither establishes that the intended application-level outcome occurred. Persisting either signal as fact can introduce unsupported knowledge that later misleads planning or verification. Functional model induction therefore needs an explicit admission boundary: the agent should state an expected observable outcome before acting, preserve the resulting interaction evidence, and admit the claim only when that evidence supports the frozen expectation.

The second challenge concerns the process used to obtain that evidence. Testing an unknown function may require clicking, entering data, submitting a form, or confirming a transition. Depending on the visible application state, such an action may delete information, send content, change access, enter a transactional workflow, or prepare another consequential operation. Risk is therefore not a context-free property of a function name: it depends on the current observation and the particular browser action about to be executed. Moreover, a function can be learned correctly even though the interaction used to learn it was consequential. Trustworthy model induction must consequently make both the evidential status of acquired knowledge and the environmental risk of acquiring it explicit.

**中文**

第一个问题是知识层面的风险。被提出的功能只是候选，执行器报告成功也只说明某次交互被完成；二者都不能证明预期的应用级结果确实发生。若把任一信号直接持久化为事实，就可能引入缺少支持的知识，进而误导后续规划或验证。因此，功能模型归纳需要明确的准入边界：智能体应在动作前声明预期可观察结果，保存交互证据，并且只在证据支持冻结预期时准入该主张。

第二个问题来自获得这些证据的过程。验证未知功能可能需要点击、输入数据、提交表单或确认状态转移。根据当前可见应用状态，这些动作可能删除信息、发送内容、改变访问权限、进入交易流程或准备其他重要操作。因此，风险不是功能名称脱离上下文后的固定属性，而取决于当前观察和即将执行的浏览器动作。即使一个功能被正确学习，获取它的交互仍可能具有重要后果。可信模型归纳必须同时显式表达所得知识的证据状态和获得知识的环境风险。

## VERA, evidence, and contributions / VERA、证据与贡献

**English**

We study open-ended exploration as *evidence production under dual risk* and introduce **VERA**, a framework for Verification and Environmental Risk Awareness in functional model induction. VERA organizes exploration around a single traceable evidence chain. At a semantic location, it first states a functional claim and freezes its expected observable outcome. It then selects an action to test that claim and, before execution, records the action's potential environmental consequences in the current GUI context. Execution produces a trace and before--after observations, which are judged against the frozen expectation. Only supporting evidence admits the claim to downstream-usable knowledge; otherwise the claim remains distinguishable as unsupported or unresolved. A persistent frontier and replay preserve unresolved claims and recover their contexts, allowing this evidence-production process to continue rather than weakening the admission rule. Thus, pre-action risk judgment describes the potential consequences of acquiring evidence, post-action verification determines what that evidence supports, and admission determines what becomes reusable knowledge.

Controlled studies support these design choices. Evidence-grounded admission attains 96.97% precision while retaining 96.97% of human-supported functional knowledge. Under the same ordinary-attempt budget, VERA's full exploration mechanism improves website-macro-average evidence-supported functional coverage by 11.9 percentage points over linear exploration, with replay costs reported separately. Finally, adding visual context improves acceptable risk-type accuracy by 35.4 percentage points on an external context-challenge set, while binary detection exhibits a higher-recall, lower-precision trade-off. A complementary exploration-linked evaluation confirms that risk records can be attached to actions arising in VERA's ordinary workflow; the external actions are supplied to the assessor to isolate contextual grounding. Together, these results provide bounded evidence for reliable knowledge admission, sustained evidence production, and context-grounded risk awareness. The evaluated risk records do not alter the selected action.

Our contributions are: (1) formulating open-ended functional model induction as evidence production under epistemic and environmental interaction risks, and defining a traceable model linking functional claims, acquisition actions, risk records, execution traces, outcome evidence, and admission decisions; (2) separating candidate discovery and executor-reported completion from evidence-grounded knowledge admission, and showing how a persistent frontier and replay sustain the verification opportunities required by conservative admission; and (3) making the acquisition side of the same evidence chain auditable by attaching context-conditioned risk records to selected actions, and evaluating their workflow coverage and contextual grounding through complementary exploration-linked and external evaluations.

**中文**

我们将开放式探索研究为*双重风险下的证据生产*，并提出用于功能模型归纳的验证与环境风险感知框架 **VERA**。VERA 围绕一条统一、可追溯的证据链组织探索。在一个语义位置，系统首先提出功能主张，并冻结其预期可观察结果；随后选择用于检验该主张的动作，并在执行前结合当前 GUI 上下文记录该动作的潜在环境后果。执行产生交互轨迹与前后观察，系统依据冻结预期判断这些证据。只有支持性证据才使主张进入下游可用知识；否则，主张仍被明确保留为不支持或未解决。持久 frontier 保存未解决主张，replay 恢复其上下文，使证据生产能够继续，而不必放宽知识准入规则。因此，执行前风险判断描述获取证据可能带来的环境后果，执行后验证判断证据支持什么，知识准入则决定什么能够成为可复用知识。

受控实验支持这些设计。基于证据的准入达到 96.97% precision，同时保留 96.97% 的人工支持功能知识。在相同普通尝试预算下，VERA 的完整探索机制相对线性探索将网站 macro-average 的证据支持功能覆盖提高 11.9 个百分点，replay 成本单独报告。在外部 context-challenge 集上，加入视觉上下文将 acceptable risk-type accuracy 提高 35.4 个百分点，而二元检测体现为更高 recall、较低 precision 的权衡。互补的 exploration-linked 评测确认，风险记录可以附着于 VERA 普通工作流中产生的动作；外部评测的动作则由实验提供给判断器，用于隔离视觉上下文对风险 grounding 的作用。这些结果共同为可靠知识准入、持续证据生产和上下文风险感知提供了有边界的证据。本文评测的风险记录不会改变已选动作。

本文贡献包括：（1）把开放式功能模型归纳表述为知识风险和环境交互风险下的证据生产，并定义一个将功能主张、证据采集动作、风险记录、执行轨迹、结果证据和准入决定连接起来的可追溯模型；（2）将候选发现和执行器报告完成与基于证据的知识准入明确区分，并说明持久 frontier 与 replay 如何维持保守准入所需要的验证机会；（3）为已选动作附加上下文相关风险记录，使同一证据链的采集侧可供审查，并通过互补的 exploration-linked 与外部评测检验其工作流覆盖和上下文 grounding。
