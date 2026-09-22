# VERA Introduction: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX draft; the Chinese text is a semantic translation for author review. Formal citations will be inserted after the related-work bibliography is verified.

## Paragraph 1: Application scenario / 应用场景

**English**

Consider an agent entering a previously unseen Web application. Rather than receiving a single user goal, the agent must determine what the application can do and organize its experience into a functional model that can support future tasks. Such a model could amortize interaction across tasks: instead of rediscovering the interface for every new request, a downstream agent could reuse grounded knowledge about available functions, where they apply, and what observable outcomes they produce. Building this model, however, requires more than passively reading a page. Many application functions become evident only after the agent changes state through interaction.

**中文**

设想一个智能体进入此前从未见过的 Web 应用。它不是接收一个单独的用户目标，而是需要判断这个应用能够做什么，并将自身经验组织成可支持未来任务的功能模型。这样的模型能够将一次探索的交互成本分摊到多个任务：下游智能体不必为每个新请求重新认识界面，而可以复用关于“有哪些功能、功能在哪里适用、会产生什么可观察结果”的落地知识。不过，建立这种模型不能只靠被动读取页面。许多应用功能只有在智能体通过交互改变状态后才会显现。

## Paragraph 2: Why open-ended exploration / 为什么需要开放式探索

**English**

This setting motivates *open-ended Web exploration*. Task-conditioned agents typically search for a path that completes a specified objective; they need not discover functionality irrelevant to that objective or preserve it for later use. An open-ended explorer instead proposes its own functional hypotheses, visits different application states, and accumulates knowledge for goals that are not yet known. These paradigms are complementary rather than universally ordered: task-conditioned interaction is well suited to completing the current request, whereas open-ended exploration is naturally aligned with constructing a reusable functional model. The same autonomy that enables this broader discovery, however, also removes much of the behavioral constraint provided by a concrete user goal.

**中文**

这一场景促使我们研究开放式 Web 探索。任务条件式智能体通常寻找一条完成指定目标的路径；它不必发现与当前目标无关的功能，也不必为未来使用保存这些功能。开放式探索智能体则自主提出功能假设、访问不同应用状态，并为尚未给出的未来目标积累知识。两种范式是互补关系，而不存在普遍的优劣顺序：任务条件式交互适合完成当前请求，开放式探索则天然更契合可复用功能模型的构建。然而，支持更广泛发现的自主性，也同时移除了具体用户目标原本提供的许多行为约束。

## Paragraph 3: Epistemic challenge / 知识侧困难

**English**

The first resulting challenge is epistemic. A proposed function is only a candidate, and an executor-reported success establishes only that an interaction was completed. Neither establishes that the intended application-level outcome occurred. Persisting either signal as fact can introduce unsupported knowledge that later misleads planning or verification. Functional model induction therefore needs an explicit admission boundary: the agent should state an expected observable outcome before acting, preserve the resulting interaction evidence, and admit the claim only when that evidence supports the frozen expectation.

**中文**

由此产生的第一个困难属于知识可信性。被提出的功能只是候选，而执行器报告成功也只表明某次交互已经完成；两者都不能证明预期的应用级结果真实发生。若将其中任一信号直接作为事实持久化，系统就可能引入未经支持的知识，并在以后误导规划或验证。因此，功能模型归纳需要明确的准入边界：智能体应在执行前声明预期的可观察结果，保存交互所产生的证据，并且只有在证据支持冻结预期时才准入该主张。

## Paragraph 4: Environmental interaction challenge / 环境交互困难

**English**

The second challenge concerns the process used to obtain that evidence. Testing an unknown function may require clicking, entering data, submitting a form, or confirming a transition. Depending on the visible application state, such an action may delete information, send content, change access, enter a transactional workflow, or prepare another consequential operation. Risk is therefore not a context-free property of a function name: it depends on the current observation and the particular browser action about to be executed. Moreover, a function can be learned correctly even though the interaction used to learn it was consequential. Trustworthy model induction must consequently make both the evidential status of acquired knowledge and the environmental risk of acquiring it explicit.

**中文**

第二个困难来自获得这些证据的过程。检验一个未知功能可能需要点击、输入数据、提交表单或确认状态转移。根据当前可见的应用状态，这类动作可能删除信息、发送内容、改变访问权限、进入交易流程，或者为其他具有重要后果的操作做准备。因此，风险不是功能名称脱离上下文后的固定属性，而取决于当前观察以及即将执行的具体浏览器动作。更重要的是，即使最终学到的功能是正确的，获得它的交互仍可能具有重要后果。因此，可信的模型归纳必须同时明确所得知识的证据状态，以及获得该知识所产生的环境风险。

## Paragraph 5: VERA / VERA 方法观点

**English**

We study open-ended exploration as *evidence production under dual risk* and introduce **VERA**, a framework for Verification and Environmental Risk Awareness in functional model induction. VERA proposes a location-conditioned functional claim together with a frozen expected observable outcome. Before each selected browser action, it records a context-conditioned risk judgment grounded in the current GUI observation. After execution, it links the action, executor status, and before--after observations to the claim, and admits the claim to downstream-usable knowledge only when the evidence supports the expected outcome. Persistent unresolved hypotheses, dependency-aware selection, and replay allow the exploration process to recover further opportunities for evidence production. The generators, executor, and judges are replaceable; the contribution is the protocol that connects their outputs into a traceable functional model.

**中文**

我们将开放式探索研究为“双重风险下的证据生产”，并提出 VERA——一个面向功能模型归纳的验证与环境风险感知框架。VERA 提出位置条件下的功能主张，并同时冻结预期的可观察结果。在每个已选浏览器动作执行之前，系统依据当前 GUI 观察记录上下文相关的风险判断。执行之后，系统将动作、执行器状态以及前后观察与功能主张关联；只有当证据支持预期结果时，该主张才进入可供下游使用的知识。持久保留的未解决假设、依赖感知选择和 replay，使探索过程能够恢复后续证据生产机会。生成器、执行器和判断器均可替换；本文的贡献在于把它们的输出连接为可追溯功能模型的协议。

## Paragraph 6: Controlled empirical evidence / 受控实验证据

**English**

Controlled studies support these design choices. Evidence-grounded admission attains 96.97% precision while retaining 96.97% of human-supported functional knowledge. Under the same ordinary-attempt budget, VERA's full exploration mechanism improves website-macro-average evidence-supported functional coverage by 11.9 percentage points over linear exploration, with replay costs reported separately. Finally, adding visual context improves acceptable risk-type accuracy by 35.4 percentage points on an external context-challenge set, while binary detection exhibits a higher-recall, lower-precision trade-off. Together, these results provide bounded evidence for reliable knowledge admission, sustained evidence production, and context-grounded risk awareness. In the evaluated system, potential risks are identified and recorded before execution but do not alter the selected action. They can inform a future blocking or human-confirmation policy, although such intervention is not implemented or evaluated in this work.

**中文**

受控实验为这些设计选择提供了支持。基于证据的准入达到 96.97% precision，同时保留 96.97% 的人工支持功能知识。在相同的普通尝试预算下，VERA 的完整探索机制相对 Linear 将网站 macro-average 证据支持功能覆盖率提高了 11.9 个百分点，并单独报告 replay 成本。最后，在外部 context-challenge 集上，加入视觉上下文使 acceptable risk-type accuracy 提高了 35.4 个百分点，同时二元检测呈现更高 recall、较低 precision 的权衡。整体而言，这些结果为可靠知识准入、持续证据生产和上下文风险感知提供了有边界的证据。在本文评测的系统中，风险会在执行前被发现并记录，但不会改变已选动作。这些记录可以为未来的阻断或人工确认策略提供依据，但本文没有实现或评价此类干预。

## Paragraph 7: Contributions / 贡献

**English**

Our contributions are: (1) we formulate open-ended functional model induction as evidence production under epistemic and environmental interaction risks, and define a traceable model that separates candidate discovery, executor-reported success, evidence judgment, and knowledge admission; (2) we introduce an execution-grounded induction protocol that freezes expected outcomes before interaction, admits only evidence-supported functional claims, and preserves unresolved verification opportunities, with controlled studies of both admission reliability and retained evidence-supported coverage; and (3) we associate each selected evidence-gathering action with a pre-execution, context-conditioned environmental-risk record and evaluate this layer on exploration-linked actions and an external context-challenge set. The evaluated layer provides awareness and audit evidence while remaining explicitly separate from execution-time control.

**中文**

本文的贡献包括：（1）我们将开放式功能模型归纳形式化为知识风险和环境交互风险下的证据生产，并定义一种可追溯模型，明确区分候选发现、执行器报告成功、证据判断与知识准入；（2）我们提出一种执行落地的归纳协议，在交互前冻结预期结果，只准入获得证据支持的功能主张，并保留尚未解决的验证机会，同时通过受控实验评价准入可靠性和保留下来的证据支持覆盖；（3）我们为每个已选证据采集动作关联执行前、上下文相关的环境风险记录，并在探索关联动作和外部 context-challenge 集上评价这一层。当前评测的风险层提供感知和审计证据，但与执行时控制明确分离。
