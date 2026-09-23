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

We study open-ended exploration as *evidence production under dual risk* and introduce **VERA**, a framework for Verification and Environmental Risk Awareness in functional model induction. VERA proposes a location-conditioned functional claim with a frozen expected observable outcome. Before each selected browser action, it records a context-conditioned risk judgment grounded in the current GUI. After execution, it links the action, executor status, and before--after observations to the claim, admitting the claim only when evidence supports the expected outcome. Persistent unresolved hypotheses and replay recover further evidence-production opportunities. The contribution is the protocol connecting these records into a traceable functional model.

Controlled studies support these design choices. Evidence-grounded admission attains 96.97% precision while retaining 96.97% of human-supported functional knowledge. Under the same ordinary-attempt budget, Full improves website-macro-average evidence-supported coverage by 11.9 percentage points over Linear, with replay costs reported separately. Adding visual context improves acceptable risk-type accuracy by 35.4 points on an external context-challenge set, while binary detection exhibits a higher-recall, lower-precision trade-off. The evaluated risk records do not alter the selected action.

Our contributions are: (1) formulating open-ended functional model induction as evidence production under epistemic and environmental interaction risks, with a traceable separation among candidate discovery, executor success, evidence judgment, and admission; (2) showing how outcome verification governs persistent knowledge admission while frontier and replay sustain evidence production; and (3) making evidence acquisition traceable by linking contextual action risk to the claim, execution trace, and outcome evidence, evaluated on workflow and external cases.

**中文**

我们将开放式探索研究为*双重风险下的证据生产*，并提出用于功能模型归纳的验证与环境风险感知框架 **VERA**。VERA 提出位置条件下的功能主张，并冻结预期可观察结果。每个已选浏览器动作执行前，系统根据当前 GUI 记录上下文风险判断；执行后，将动作、执行器状态和前后观察与功能主张关联，只有证据支持预期结果时才准入该主张。持久保留的未解决假设与 replay 用于恢复后续证据生产机会。方法贡献在于把这些记录连接成可追溯功能模型的协议。

受控实验支持这些设计。基于证据的准入达到 96.97% precision，同时保留 96.97% 的人工支持功能知识。在相同普通尝试预算下，Full 相对 Linear 将网站 macro-average 的证据支持覆盖提高 11.9 个百分点，replay 成本单独报告。在外部 context-challenge 集上，加入视觉上下文将 acceptable risk-type accuracy 提高 35.4 个百分点，而二元检测体现为更高 recall、较低 precision 的权衡。本文评测的风险记录不会改变已选动作。

本文贡献包括：（1）把开放式功能模型归纳表述为知识风险和环境交互风险下的证据生产，并在可追溯模型中区分候选发现、执行器成功、证据判断和知识准入；（2）说明结果验证如何控制持久知识准入，以及 frontier 和 replay 如何维持证据生产；（3）把上下文动作风险与功能主张、执行轨迹和结果证据关联，使证据采集过程可追溯，并在真实探索动作和外部样本上进行评价。
