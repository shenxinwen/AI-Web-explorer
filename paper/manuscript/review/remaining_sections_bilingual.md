# VERA Remaining Sections: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation for author review.

## Abstract / 摘要

**English**

Open-ended Web exploration allows agents to discover application functionality without predefined user tasks, but its autonomy creates two linked risks: probing unknown functions can affect the environment, and insufficiently supported observations can become persistent knowledge. We introduce VERA, a framework that treats functional model induction as a traceable process of evidence production. VERA represents each discovered function as a testable claim with an expected observable outcome fixed before execution. For every selected semantic browser action, it records a context-conditioned assessment of potential environmental risk and links that record to the claim and interaction trace. After execution, VERA compares the observed outcome with the fixed expectation and admits the claim to reusable knowledge only when the interaction evidence supports it. Unresolved claims remain available for later verification through a persistent exploration process. In controlled studies, evidence-grounded admission achieves 96.97% precision while retaining 96.97% of human-supported functional knowledge. Persistent recovery improves website-macro-average evidence-supported coverage by 11.9 percentage points over linear exploration under the same ordinary-attempt budget, with replay cost reported separately. On an external context-challenge set, visual context improves acceptable risk-type accuracy by 35.4 points; binary detection shows a higher-recall, lower-precision trade-off. These results support shifting the focus of open-ended exploration from coverage alone toward reliable functional knowledge whose evidential basis and acquisition risks remain explicit and auditable.

**中文**

开放式 Web 探索使智能体能够在没有预定义用户任务时发现应用功能，但这种自主性产生两类关联风险：试探未知功能可能影响环境，证据不足的观察也可能成为持久知识。我们提出 VERA，一个把功能模型归纳视为可追溯证据生产过程的框架。VERA 将每个被发现功能表示为可检验主张，并在执行前固定其预期可观察结果。对于每个已选语义浏览器动作，系统记录基于上下文的潜在环境风险判断，并将其与主张和交互轨迹关联。执行后，VERA 将观察结果与固定预期比较，只有交互证据支持主张时才将其准入可复用知识。未解决主张通过持续探索过程保留，供后续验证。在受控实验中，基于证据的准入达到 96.97% precision，并保留 96.97% 的人工支持功能知识。在相同普通尝试预算下，持久恢复相对线性探索将网站 macro-average 证据支持覆盖提高 11.9 个百分点，replay 成本单独报告。在外部 context-challenge 集上，视觉上下文将 acceptable risk-type accuracy 提高 35.4 点；二元检测体现为更高 recall、较低 precision 的权衡。这些结果支持把开放式探索的重点从覆盖本身转向可靠功能知识，同时使知识的证据基础和获取风险保持显式且可审查。

## Limitations and Ethics / 局限性与伦理

### Scope and validity / 范围与有效性

**English**

The functional-model experiments cover two resettable shopping applications with three runs per condition. They do not establish performance across production sites, and the induced model includes only states and functions reached during exploration. VLM and executor errors can propagate into missed functions, incorrect evidence judgments, or inaccurate risk records; executor failure may also be difficult to distinguish from an unavailable function. AI-assisted labels were reviewed by one human author rather than independently double-annotated. The three C2 repetitions are descriptive, and only eight C3 candidate pairs realize a binary gold-label difference. External C3 actions are supplied to the assessor and do not show that VERA would propose them.

**中文**

功能模型实验覆盖两个可重置购物应用，每个条件运行三次，不能证明在生产网站上的表现。归纳模型只包含探索到达的状态与功能。VLM 和执行器错误可能传播为功能遗漏、错误证据判断或不准确风险记录；执行器失败也可能难以与功能不可用区分。AI 辅助标签由一名作者审查，而非双人独立标注。C2 的三次重复用于描述统计，C3 只有八个候选 pair 形成二元 gold-label 差异。外部 C3 动作由实验提供给判断器，不能说明 VERA 会主动提出它们。

### Knowledge and risk boundaries / 知识与风险边界

**English**

Observed dependencies are local applicability evidence, not complete business preconditions, and supported claims can become stale as sites change. The current model retains provenance for reinspection but does not implement continuous revalidation. The risk layer judges the selected semantic action, not every visible candidate or all long-horizon consequences; its binary label and single primary type also compress compound risks. Risk records can inform blocking or human confirmation, but the evaluated system does not alter actions and therefore provides no evidence of harm reduction or end-to-end safety.

**中文**

观察到的依赖是局部适用性证据，而不是完整业务前置条件；网站变化也可能使已支持主张过期。当前模型保留 provenance 供重新检查，但未实现持续重新验证。风险层判断已选语义动作，而不是每个可见候选或所有长程后果；二元标签和单一主要类型也会压缩复合风险。风险记录可以为阻断或人工确认提供输入，但评测系统不会改变动作，因此没有实际伤害降低或端到端安全的证据。

### Ethical deployment / 伦理部署

**English**

Open-ended agents can delete or disclose data, send communications, change permissions, enter transactions, or consume service resources; screenshots and traces may contain credentials or personal information. Experiments should use authorized, resettable environments and isolated accounts, minimize and redact sensitive data, and respect access controls, service terms, and review requirements. Production deployment would additionally require intervention policies, failure handling, data governance, and human oversight.

**中文**

开放式智能体可能删除或披露数据、发送通信、修改权限、进入交易或消耗服务资源；截图和轨迹也可能包含凭据或个人信息。实验应使用获得授权、可重置的环境和隔离账号，最小化并脱敏敏感数据，并遵守访问控制、服务条款和审查要求。生产部署还需要干预策略、失败处理、数据治理和人工监督。

## Reproducibility Statement / 可复现性声明

**English**

The anonymous artifact contains the implementation, versioned prompts and risk taxonomy, frozen configurations, reviewed labels, machine-readable metrics, and analysis scripts for C1--C3. Configurations record budgets, replay limits, seeds, model settings, viewport, and failure rules. Exact result packages are under `paper/experiments/results/E002--E004`; the Appendix summarizes protocol details. Inclusion of raw screenshots and traces in the supplementary release is contingent on sensitive-data review.

**中文**

匿名工件包含实现、版本化提示词和风险分类体系、冻结配置、审查标签、机器可读指标以及 C1--C3 分析脚本。配置记录预算、replay 限额、seed、模型设置、viewport 和失败规则。完整结果包位于 `paper/experiments/results/E002--E004`，协议细节由 Appendix 汇总。原始截图和轨迹是否纳入补充材料取决于敏感数据审查。

## Conclusion / 结论

**English**

Open-ended Web exploration can support reusable functional model induction, but discovery alone is not enough. An agent must distinguish a proposed function from an executor-reported completion and from an outcome supported by observable evidence. It must also account for the environmental consequences of the interactions used to obtain that evidence. VERA connects these concerns in a traceable model: it fixes functional claims before execution, records context-conditioned action risk, preserves before--after evidence, and admits only supported outcomes while retaining unresolved verification opportunities.

Across controlled studies, this design yields more precise knowledge admission, extends evidence-supported coverage through persistent recovery, and improves the contextual expression of risk consequences. The results are bounded: they do not establish general exploration optimality or evaluated harm prevention. They nevertheless support a broader view of trustworthy environment learning. What an agent learns should be evaluated not only by how much functionality it discovers, but also by what evidence makes those discoveries reusable and what actions were taken to acquire that evidence.

**中文**

开放式 Web 探索可以支持可复用功能模型归纳，但仅仅发现功能还不够。智能体必须区分被提出的功能、执行器报告完成和获得可观察证据支持的结果；同时还必须说明用于获得证据的交互可能产生什么环境后果。VERA 在可追溯模型中连接这些问题：执行前固定功能主张，记录上下文动作风险，保存前后证据，只准入获得支持的结果，并保留未解决验证机会。

受控实验表明，该设计产生更精确的知识准入，通过持久恢复扩展证据支持覆盖，并改善风险后果的上下文表达。结果具有明确边界：它们不能证明通用探索最优性，也没有评价实际伤害阻断。但它们支持更广义的可信环境学习观点：评价智能体学到了什么时，不仅要考虑发现多少功能，还要考虑什么证据使这些发现可以复用，以及为获得证据执行了什么动作。
