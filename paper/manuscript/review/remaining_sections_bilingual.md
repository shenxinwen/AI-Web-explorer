# VERA Remaining Sections: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX draft; the Chinese text is a semantic translation for author review.

## Abstract / 摘要

**English**

Open-ended Web exploration allows agents to discover application functionality without predefined user tasks, but its autonomy creates two linked risks: probing unknown functions can affect the environment, and insufficiently supported observations can become persistent knowledge. We introduce VERA, a framework that treats functional model induction as a traceable process of evidence production. VERA represents each discovered function as a testable claim with an expected observable outcome fixed before execution. For every selected semantic browser action, it records a context-conditioned assessment of potential environmental risk and links that record to the claim and interaction trace. After execution, VERA compares the observed outcome with the fixed expectation and admits the claim to reusable knowledge only when the interaction evidence supports it. Unresolved claims remain available for later verification through a persistent exploration process. In controlled studies, evidence-grounded admission achieves 96.97% precision while retaining 96.97% of human-supported functional knowledge. Persistent recovery improves website-macro-average evidence-supported coverage by 11.9 percentage points over linear exploration under the same ordinary-attempt budget, with replay cost reported separately. On an external context-challenge set, visual context improves acceptable risk-type accuracy by 35.4 points; binary detection shows a higher-recall, lower-precision trade-off. These results support shifting the focus of open-ended exploration from coverage alone toward reliable functional knowledge whose evidential basis and acquisition risks remain explicit and auditable.

**中文**

开放式 Web 探索使智能体能够在没有预定义用户任务的情况下发现应用功能，但这种自主性带来两类相互关联的风险：对未知功能的试探可能影响环境，而证据不足的观察也可能被持久化为知识。我们提出 VERA，一个将功能模型归纳视为可追溯证据生产过程的框架。VERA 把每个被发现的功能表示为可检验主张，并在执行前固定其预期可观察结果。对于每个已选语义浏览器动作，VERA 记录基于当前上下文的潜在环境风险判断，并将该记录与功能主张和交互轨迹关联。执行后，VERA 将观察到的结果与预先固定的预期进行比较，只有交互证据支持该主张时，才将其准入可复用知识。未解决主张则通过持续探索过程保留，以便后续验证。在受控实验中，基于证据的准入达到 96.97% precision，同时保留 96.97% 的人工支持功能知识。在相同普通尝试预算下，持久恢复相对线性探索将网站 macro-average 的证据支持覆盖提高 11.9 个百分点，replay 成本单独报告。在外部 context-challenge 集合上，视觉上下文将 acceptable risk-type accuracy 提高 35.4 个百分点；二元检测表现为更高 recall、较低 precision 的权衡。这些结果支持将开放式探索的关注点从覆盖本身推进到可靠功能知识的获得，同时使其证据基础和知识采集风险保持显式且可审查。

## Limitations and Ethics / 局限性与伦理

### Evaluation scope / 评测范围

**English**

Our functional-model experiments use two resettable shopping applications and three runs per condition. This controlled setting permits shared candidates, budgets, and evidence criteria, but does not establish performance across the diversity of production Web applications. The induced model covers only states and functions reached during exploration; it is neither a complete inventory of application functionality nor a reconstruction of hidden business logic. Location constraints and observed direct dependencies are local applicability evidence, not complete preconditions or causal rules. Comparisons with systems that use different tasks, action spaces, executors, or labels would require a new common evaluation rather than direct comparison of reported scores.

**中文**

我们的功能模型实验使用两个可重置购物应用，每个条件运行三次。该受控设置使候选、预算和证据标准可以保持一致，但不能证明方法在多样化生产 Web 应用上的表现。归纳模型只覆盖探索实际到达的状态和功能，既不是应用功能的完整清单，也不是对隐藏业务逻辑的恢复。位置约束和观察到的直接依赖属于局部适用性证据，而不是完整前置条件或因果规则。对于任务、动作空间、执行器或标签不同的系统，应建立新的共同评测，而不能直接比较各自报告的分数。

### Imperfect components and changing environments / 组件误差与环境变化

**English**

VERA currently relies on vision-language models for hypothesis generation, outcome judgment, and risk assessment, and on a browser executor for grounding and interaction. Errors in any component can propagate into missed functions, incorrect evidence judgments, or inaccurate risk records. Executor failure can also be difficult to distinguish from an unavailable function. Moreover, Web applications evolve: a claim supported at one time can become stale after an interface or policy change. The current work retains provenance that can support reinspection, but does not implement systematic staleness detection or continuous revalidation.

**中文**

VERA 当前使用视觉语言模型进行假设生成、结果判断和风险评估，并依赖浏览器执行器完成动作定位与交互。任何组件的错误都可能传播为功能遗漏、错误证据判断或不准确的风险记录。执行器失败也可能难以与功能不可用区分。此外，Web 应用会持续变化：某一时刻获得支持的主张可能在界面或策略改变后失效。当前工作保留了可用于重新检查的 provenance，但没有实现系统性的知识失效检测或持续重新验证。

### Risk recognition is not intervention / 风险识别不等于干预

**English**

The evaluated risk layer judges only the selected semantic action in its current visual context; it does not scan every visible candidate or reason over all possible long-horizon consequences. Its binary decision and single primary type also compress compound or ambiguous risks. In C3, visual context improves risk-type grounding most clearly, while binary detection trades higher recall for lower precision and its recall and F1 difference intervals cross zero. Risk records are produced before execution and could be consumed by a blocking or human-confirmation policy, but the evaluated system does not use them to alter actions. We therefore do not claim reduced harm, successful prevention, or an end-to-end safety guarantee.

**中文**

本文评测的风险层只判断当前视觉上下文中的已选语义动作；它不会扫描所有可见候选，也不会推理所有可能的长程后果。二元判断和单一主要类别也会压缩复合或模糊风险。C3 中最明确的改善是风险类型 grounding；二元检测则以较低 precision 换取较高 recall，并且 recall 和 F1 差异区间跨越 0。风险记录在执行前生成，可以被阻断或人工确认策略使用，但本文评测系统并不据此改变动作。因此，我们不宣称已经降低实际伤害、成功阻止危险行为或提供端到端安全保证。

### Annotation and statistical limitations / 标注与统计限制

**English**

AI-assisted initial labels were reviewed and revised item by item by a human author under frozen guides, but the study does not include independent double annotation or inter-annotator agreement. The external context challenge improves contextual diversity, yet its actions are supplied to the assessor and do not show that VERA would propose them. Only eight candidate pairs realize a binary gold-label difference, limiting pair-level conclusions. The three C2 repetitions are reported descriptively rather than used for significance claims.

**中文**

AI 辅助生成的初始标签由一名作者依据冻结指南逐项审查和修订，但研究没有采用双人独立标注，也没有报告标注者间一致性。外部 context challenge 提高了上下文多样性，但其中的动作由实验提供给判断器，不能说明 VERA 会主动提出这些动作。只有八个候选 pair 形成二元 gold-label 差异，因此 pair 层面的结论有限。C2 的三次重复只用于描述统计，不用于显著性主张。

### Ethical use of autonomous exploration / 自主探索的伦理使用

**English**

Open-ended agents can delete or disclose data, send communications, change permissions, enter transactions, or consume service resources. Screenshots and traces may also contain credentials or personal information. Experiments should therefore use authorized, resettable environments and isolated accounts where possible, minimize and redact sensitive data, retain only necessary artifacts, and respect access controls, service terms, and applicable review requirements. Deploying VERA on production systems would require an intervention policy, failure handling, data governance, and human oversight beyond the mechanisms evaluated here.

**中文**

开放式智能体可能删除或泄露数据、发送通信、修改权限、进入交易流程或消耗服务资源。截图和轨迹也可能包含凭据或个人信息。因此，实验应尽可能使用获得授权、可重置的环境和隔离账号，最小化并脱敏敏感数据，只保留必要工件，并遵守访问控制、服务条款和适用的审查要求。若要将 VERA 部署在生产系统中，还需要本文未评测的干预策略、失败处理、数据治理和人工监督。

## Reproducibility Statement / 可复现性声明

**English**

The anonymous artifact package contains the implementation, versioned prompts and risk taxonomy, frozen experiment configurations, reviewed annotations, machine-readable metrics, and analysis scripts for C1--C3. Configurations record entry states, ordinary-attempt and replay limits, random seeds where applicable, model sampling settings, viewport, and failure-handling rules. The C1 package contains 45 aggregated claims, 103 attempts, and the reviewed gold used by `scripts/paper/analyze_c1.py`. C2 provides the 18-run configuration, frozen coverage ledger, replay accounting, and `scripts/paper/analyze_c2.py`. C3 provides the 106 exploration-linked cases, 100 external cases, frozen assessor configuration, artifact manifests, and scripts for both evaluations. Failed executions, incomplete evidence, and negative examples are retained. Exact result packages are under `paper/experiments/results/E002--E004`. Their manifests reference the raw browser artifacts; inclusion of screenshots and traces in the supplementary release is contingent on sensitive-data review.

**中文**

匿名工件包包含实现代码、带版本的提示词和风险分类体系、冻结实验配置、人工审查标注、机器可读指标以及 C1--C3 分析脚本。配置记录入口状态、普通尝试和 replay 限额、适用时的随机 seed、模型采样设置、viewport 和失败处理规则。C1 工件包含 45 条聚合主张、103 次尝试、人工审查 gold 和 `scripts/paper/analyze_c1.py`。C2 提供 18 条运行的配置、冻结覆盖账本、replay 计数和 `scripts/paper/analyze_c2.py`。C3 提供 106 条探索关联样本、100 条外部样本、冻结判断器配置、工件清单和两条评测轨道的脚本。执行失败、证据不完整和负例均被保留。最终结果包位于 `paper/experiments/results/E002--E004`；其中的 manifests 引用原始浏览器工件，截图和轨迹是否纳入补充材料取决于敏感数据审查结果。

## Conclusion / 结论

**English**

Open-ended Web exploration can support reusable functional model induction, but discovery alone is not enough. An agent must distinguish a proposed function from an executor-reported completion and from an outcome supported by observable evidence. It must also account for the environmental consequences of the interactions used to obtain that evidence. VERA connects these concerns in a traceable model: it fixes functional claims before execution, records context-conditioned action risk, preserves before--after evidence, and admits only supported outcomes while retaining unresolved verification opportunities.

Across controlled studies, this design yields more precise knowledge admission, extends evidence-supported coverage through persistent recovery, and improves the contextual expression of risk consequences. The results are bounded: they do not establish general exploration optimality or evaluated harm prevention. They nevertheless support a broader view of trustworthy environment learning. What an agent learns should be evaluated not only by how much functionality it discovers, but also by what evidence makes those discoveries reusable and what actions were taken to acquire that evidence.

**中文**

开放式 Web 探索可以支持可复用的功能模型归纳，但仅仅发现功能还不够。智能体必须区分被提出的功能、执行器报告的完成状态和获得可观察证据支持的结果；同时，它还必须说明用于获取证据的交互可能带来什么环境后果。VERA 在一个可追溯模型中连接这些问题：在执行前固定功能主张，记录上下文条件下的动作风险，保存动作前后证据，只准入获得支持的结果，并保留尚未解决的验证机会。

受控实验表明，该设计能够提高知识准入 precision，通过持久恢复扩展证据支持覆盖，并改善风险后果的上下文表达。这些结果具有明确边界：它们不证明通用探索最优性，也没有评测实际伤害阻断。但它们支持一种更广义的可信环境学习观点：评价智能体学到了什么时，不仅要考虑发现了多少功能，还要考虑什么证据使这些发现可以复用，以及为了获得证据执行了什么动作。
