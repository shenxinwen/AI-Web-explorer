# VERA Experimental Setup: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX draft; the Chinese text is a semantic translation for author review. No C1--C3 artifact or result is modified.
>
> **Snapshot notice:** This file preserves the pre-compression review version and will be regenerated after the revised English structure is approved.

## Evaluation questions / 评价问题

**English**

We design three controlled studies around the claims in the Problem Formulation and Method. Rather than compare end-to-end scores against systems with different tasks, action spaces, executors, and label definitions, each study holds the relevant inputs fixed and varies the mechanism under examination. We ask: **RQ1:** Does evidence-grounded admission improve the precision of persistent functional knowledge while retaining human-supported claims? **RQ2:** Under a fixed ordinary-attempt budget, does persistent, execution-grounded exploration retain useful evidence-supported functional coverage, and what additional GUI cost does replay incur? **RQ3:** Can the risk assessor identify and type potential environmental consequences of selected actions, and how does current visual context affect its judgments?

**中文**

我们围绕 Problem Formulation 和 Method 中的主张设计三个受控实验。不同系统在任务、动作空间、执行器和标签定义上并不一致，因此我们不进行异构端到端分数的直接比较；每个实验固定相关输入，只改变所研究的机制。三个问题是：**RQ1：** 基于证据的准入能否在保留人工确认支持主张的同时，提高持久功能知识的 precision？**RQ2：** 在固定普通尝试预算下，持久化、执行落地的探索能否保留有用的证据支持功能覆盖，replay 又会带来多少额外 GUI 成本？**RQ3：** 风险判断器能否识别并分类已选动作可能产生的环境后果，当前视觉上下文会如何影响判断？

## Applications and common protocol / 应用与共同协议

**English**

RQ1 and RQ2 use two interactive shopping applications: SauceDemo and Practice Shopping. Each exploration run starts from the designated entry URL in a clean browser session; resettable application state is restored before a run. Formal exploration uses three runs per application and condition, with at most 25 ordinary high-level candidate attempts per run. The budget counts attempts to test candidate functions. Replay actions do not consume this budget because they restore a previously observed context rather than test a new candidate; we therefore limit and report their GUI actions separately.

For RQ1 and RQ2, all candidate hypotheses include an expected observable outcome frozen before execution. The retained artifacts include the selected action, executor status, before and after observations, evidence references, and model judgments. Initial annotations were generated with AI assistance and then reviewed and revised item by item by a human author under a frozen annotation guide. The reviewed labels are used as gold. This process is not independent double annotation, so we do not report inter-annotator agreement. Failed executions, incomplete evidence, and negative examples remain in the evaluation artifacts rather than being discarded.

**中文**

RQ1 和 RQ2 使用两个可交互购物应用：SauceDemo 与 Practice Shopping。每次探索从指定入口 URL 和干净浏览器会话开始；可重置的应用状态会在运行前恢复。正式探索对每个应用、每个条件运行三次，每次最多包含 25 个普通高层候选尝试。该预算统计检验候选功能的尝试。Replay 用于恢复先前观察到的上下文，而不是检验新候选，因此不占普通尝试预算；其 GUI 动作受到单独限制并单独报告。

对于 RQ1 和 RQ2，所有候选假设都包含执行前冻结的预期可观察结果。保留工件包括已选动作、执行器状态、动作前后观察、证据引用和模型判断。标注首先由 AI 辅助生成，再由一名作者依据冻结指南逐项审查和修订；审查后的标签作为 gold。该过程并非双人独立标注，因此不报告标注者间一致性。执行失败、证据不完整和负样本均保留在评测工件中，而不是被删除。

## RQ1: Evidence-grounded knowledge admission / 基于证据的知识准入

**English**

RQ1 tests whether outcome evidence provides a more reliable admission boundary than either proposal or executor status alone. The comparison is designed to falsify this claim if evidence-grounded admission fails to improve precision or does so only by discarding most human-supported knowledge.

**中文**

RQ1 检验结果证据能否提供比候选提出或执行器状态更可靠的知识准入边界。如果基于证据的准入不能提高 precision，或者只能通过丢弃大部分人工支持知识来提高 precision，那么这一主张将不成立。

**English**

RQ1 uses naturally occurring candidates and frozen trajectories from three Full runs on each application. Duplicate attempts are aggregated by application, semantic location, and canonical action identifier, yielding 45 unique functional claims backed by 103 attempts. Human review identifies a claim as supported when at least one valid attempt confirms that the function exists at that location and provides before--after evidence for its core functional outcome. The final set contains 33 supported claims. Four attempts lack complete evidence and remain non-admissible under the evidence-grounded rule.

All three rules consume the same candidates and traces. **Proposal-as-fact** admits every proposal. **Executor-success-as-fact** admits a claim after at least one executor-reported success. **Evidence-grounded admission** requires at least one evidence-complete attempt judged to support the frozen outcome. This isolates admission from exploration and execution differences. Primary metrics are admitted knowledge precision, supported knowledge retention, and admission yield. Diagnostics include false admissions, missed supported claims, evidence completeness, and executor--outcome disagreement.

**中文**

RQ1 使用两个应用各三条 Full 运行中自然产生的候选和冻结轨迹。重复尝试按“应用、语义位置、规范动作标识”聚合，最终得到由 103 次尝试支持的 45 条唯一功能主张。当至少一次有效尝试既确认功能存在于该位置，又提供支持其核心功能结果的前后证据时，人工审查将该主张标为 supported。最终有 33 条 supported claims。103 次尝试中有 4 次证据不完整，在基于证据的规则下不能准入。

三种规则消费完全相同的候选和轨迹。**Proposal-as-fact** 准入所有提议；**Executor-success-as-fact** 在至少一次执行器报告成功后准入；**Evidence-grounded admission** 要求至少一次证据完整的尝试被判定支持冻结结果。这样能够把准入规则与探索、执行差异分离。主指标是 admitted knowledge precision、supported knowledge retention 和 admission yield；诊断包括错误准入、遗漏的支持主张、证据完整性和 executor--outcome disagreement。

## RQ2: Persistent evidence production / 持续证据生产

**English**

RQ2 tests whether preserving and recovering unresolved verification opportunities produces additional evidence-supported functionality under the same ordinary candidate-attempt budget. The relevant comparison is Full versus Linear: both use the same dependency-aware selection and admission rule, while only Full retains a frontier across locations and replays observed paths. Any coverage gain must therefore be interpreted together with replay's additional GUI cost.

**中文**

RQ2 检验在相同普通候选尝试预算下，保存并恢复未解决验证机会能否产生更多由证据支持的功能。关键比较是 Full 与 Linear：二者使用相同的依赖感知选择和准入规则，只有 Full 会跨位置保留 frontier 并 replay 已观察路径。因此，任何覆盖增益都必须与 replay 的额外 GUI 成本共同解释。

**English**

We compare three policies while holding applications, entry states, ordinary-attempt budgets, candidate representation, executor, and evidence admission fixed. **Random** uses a frozen seed and neither checks observed dependencies nor replays paths. **Linear** checks observed direct dependencies and selects deterministically, but abandons unresolved candidates after leaving their semantic location. **Full** adds a persistent frontier and replay to Linear. The design contains 18 valid runs: two applications, three conditions, and three repetitions.

The reviewed inventories contain 16 functions for Practice Shopping and 22 for SauceDemo. A function counts as covered at most once per run and only when complete interaction evidence supports its outcome. The primary metric is evidence-supported functional coverage, reported per run, averaged within each application, and macro-averaged across applications. We separately report coverage growth, ordinary attempts and outcomes, stopping reasons, replay operations and GUI actions, and functions first covered after replay. Because replay adds GUI cost, greater coverage under the ordinary-attempt budget is not treated as greater total-interaction efficiency.

**中文**

我们在固定应用、起点、普通尝试预算、候选表达、执行器和证据准入规则的条件下比较三种策略。**Random** 使用冻结 seed，不检查观察到的依赖，也不 replay。**Linear** 检查观察到的直接依赖并确定性选择，但离开语义位置后不再恢复未解决候选。**Full** 在 Linear 上加入 persistent frontier 和 replay。正式设计共包含 18 条有效运行：两个应用、三个条件、三次重复。

人工审查后的功能清单分别包含 Practice Shopping 的 16 项和 SauceDemo 的 22 项功能。每项功能在一条 run 中最多计一次，而且只有完整交互证据支持其结果时才算覆盖。主指标为证据支持功能覆盖率：逐 run 报告，先在应用内取平均，再对应用作 macro-average。我们另行报告覆盖增长、普通尝试及结果、停止原因、replay 次数和 GUI 动作，以及首次在 replay 后获得覆盖的功能。由于 replay 产生额外 GUI 成本，普通尝试预算下的较高覆盖不能直接解释为总交互效率更高。

## RQ3: Context-conditioned environmental risk awareness / 上下文环境风险感知

**English**

RQ3 tests whether a pre-execution risk record can be produced for VERA's own selected actions and whether visual context improves the grounding of risk judgments. No single dataset adequately answers both questions: naturally occurring exploration actions provide workflow fidelity but a narrow risk distribution, whereas a deliberately varied challenge set supplies stronger contextual contrasts but not actions proposed by VERA. We therefore use two complementary tracks and report them separately.

The **external context-challenge track** contains 100 independently sampled screenshot--action cases, including 30 candidate pairs and 40 diversity cases. These supplied actions are inputs to the assessor; the experiment does not claim that VERA would propose them. Gold contains 65 risk positives and permits multiple acceptable types for compound risks. Text-only receives the action and shared taxonomy; Context-conditioned additionally receives the screenshot. Thus, the comparison isolates visual context, while the taxonomy remains shared output vocabulary.

Both tracks report precision, recall, F1, and risk-type accuracy on positive cases. We also analyze corrected and introduced errors, false positives and negatives, and pair consistency. External intervals use 10,000 cluster-bootstrap samples, with each candidate pair treated as a cluster and each diversity case as a singleton (seed 20260920). An interval crossing zero is reported only as a point-estimate direction. Potential risks are identified and recorded before execution, but the experiment does not alter the selected action or evaluate an intervention policy.

**中文**

RQ3 检验两个问题：VERA 能否为自身选择的动作生成执行前风险记录，以及视觉上下文能否改善风险判断的 grounding。单一数据集不足以充分回答这两个问题：自然产生的探索动作与真实工作流一致，但风险分布较窄；刻意构造多样性的挑战集提供了更强的上下文对照，但其中动作并非由 VERA 提出。因此，我们使用两条互补且分开报告的轨道。

**English**

The **exploration-linked track** contains 106 run-locally deduplicated ordinary actions from the six valid RQ2 Full runs; 32 are human-confirmed risk positives in the financial-transaction and sensitive-data categories. Four input conditions use the same judge: action only; action plus taxonomy; screenshot plus action; and the full screenshot, action, and taxonomy input. This track tests actions produced by VERA's exploration. Replay remains auditable but is excluded from classification accuracy.

**中文**

**探索关联轨道**包含六条有效 RQ2 Full 运行中 106 条运行内去重的普通动作，其中 32 条由人工确认为风险正例，类别为 financial transaction 和 sensitive data。同一判断器接受四种输入：仅动作；动作加 taxonomy；截图加动作；截图、动作和 taxonomy 的完整输入。该轨道检验 VERA 探索实际产生的动作。Replay 记录仍可审查，但不进入分类准确率比较。

**外部 context-challenge 轨道**包含 100 条独立抽样的截图—动作样本，其中有 30 个候选 pair 和 40 条 diversity 样本。这些动作是供应给判断器的输入；实验不声称 VERA 会主动提出它们。Gold 包含 65 个风险正例，并允许复合风险有多个可接受类型。Text-only 接收动作和共享 taxonomy；Context-conditioned 额外接收截图。因此比较隔离视觉上下文的贡献，taxonomy 则保持为共享输出词汇。

两条轨道均报告 precision、recall、F1 和正例上的风险类型准确率，并分析被上下文纠正或引入的错误、误报、漏报和 pair 一致性。外部区间采用 10,000 次 cluster bootstrap，将每个候选 pair 作为一个 cluster、每条 diversity 样本作为 singleton，seed 为 20260920。区间跨 0 的差异只描述为点估计方向。潜在风险在执行前被识别并记录，但实验不会改变已选动作，也不评价干预策略。
