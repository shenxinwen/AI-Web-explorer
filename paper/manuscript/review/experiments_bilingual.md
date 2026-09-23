# VERA Experimental Setup: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation. No frozen C1--C3 artifact is modified.

## Evaluation questions and common protocol / 评价问题与共同协议

**English**

We use controlled comparisons rather than align end-to-end scores from systems with different tasks, action spaces, executors, and labels. The studies ask: (RQ1) whether outcome evidence improves knowledge admission while retaining human-supported claims; (RQ2) whether persistent recovery extends evidence-supported coverage under a fixed ordinary-attempt budget and at what replay cost; and (RQ3) whether VERA records risk on its selected actions and how visual context changes risk grounding.

RQ1 and RQ2 use the resettable shopping applications SauceDemo and Practice Shopping. Each condition has three runs per application, starts from a clean browser session, and permits at most 25 ordinary high-level candidate attempts. Replay restores an observed context rather than testing a new candidate, so its GUI actions are limited and reported separately. Every RQ1/RQ2 hypothesis has an expected outcome fixed before execution, and failed or incomplete attempts remain in the artifacts. AI-assisted initial annotations were reviewed and revised item by item by a human author under frozen guides. Appendix details the configurations, annotation protocols, and retained artifacts.

**中文**

我们采用受控比较，而不对任务、动作空间、执行器和标签不同的系统强行对齐端到端分数。实验研究：（RQ1）结果证据能否在保留人工支持主张的同时改善知识准入；（RQ2）在固定普通尝试预算下，持久恢复能否扩展证据支持覆盖，以及 replay 成本是多少；（RQ3）VERA 能否为自身选择的动作记录风险，视觉上下文会如何改变风险 grounding。

RQ1 和 RQ2 使用可重置购物应用 SauceDemo 和 Practice Shopping。每个条件在每个应用上运行三次，从干净浏览器会话开始，最多允许 25 个普通高层候选尝试。Replay 用于恢复已观察上下文而不是检验新候选，因此其 GUI 动作单独限制和报告。所有 RQ1/RQ2 假设都有执行前固定的预期结果，失败或不完整尝试仍保留在工件中。AI 辅助生成的初始标注由一名作者依据冻结指南逐项审查和修订。配置、标注协议和保留工件详见 Appendix。

## RQ1: Evidence-grounded knowledge admission / 基于证据的知识准入

**English**

RQ1 holds discovery and execution fixed while varying only the admission rule. It aggregates candidates from six Full runs by application, semantic location, and canonical action identifier, yielding 45 functional claims backed by 103 attempts. Human review identifies 33 claims with at least one valid attempt supporting the core outcome; four attempts lack complete evidence.

Proposal as fact admits all candidates; executor success as fact requires at least one executor-reported success; and evidence-grounded admission requires a complete attempt that supports the frozen outcome. The primary metrics are admitted-knowledge precision and supported-knowledge retention. This design would contradict the reliability claim if evidence grounding failed to improve precision or retained little human-supported knowledge.

**中文**

RQ1 固定发现与执行，只改变准入规则。它按应用、语义位置和规范动作标识聚合六条 Full 运行中的候选，得到由 103 次尝试支持的 45 条功能主张。人工审查识别出 33 条至少有一次有效尝试支持核心结果的主张；四次尝试缺少完整证据。

Proposal as fact 准入全部候选；executor success as fact 要求至少一次执行器报告成功；evidence-grounded admission 要求一次完整尝试支持冻结结果。主指标是 admitted-knowledge precision 和 supported-knowledge retention。如果证据 grounding 未提高 precision，或只保留很少人工支持知识，该设计的可靠性主张就不能成立。

## RQ2: Persistent evidence production / 持续证据生产

**English**

RQ2 fixes the application, entry state, candidate representation, executor, admission rule, and ordinary-attempt budget. Random selects unfinished candidates with a frozen seed and uses neither dependency checks nor replay. Linear uses observed direct dependencies and deterministic selection but abandons unresolved candidates after leaving their location. Full adds a persistent frontier and replay to Linear. The design has 18 valid runs.

The reviewed inventories contain 16 functions for Practice Shopping and 22 for SauceDemo. A function counts once per run and only when complete evidence supports its outcome. We report application means and their macro-average, together with replay operations, GUI actions, and functions first covered after replay. Because replay adds interaction outside the ordinary-attempt budget, coverage gains are not interpreted as total-interaction efficiency gains.

**中文**

RQ2 固定应用、入口状态、候选表达、执行器、准入规则和普通尝试预算。Random 使用冻结 seed 选择未完成候选，不检查依赖，也不 replay。Linear 使用观察到的直接依赖和确定性选择，但离开位置后放弃未解决候选。Full 在 Linear 上加入 persistent frontier 和 replay。实验共有 18 条有效运行。

人工审查清单包含 Practice Shopping 的 16 项功能和 SauceDemo 的 22 项功能。每项功能在每条运行中最多计一次，且只有完整证据支持其结果时才计入。我们报告应用内平均值及网站 macro-average，并同时报告 replay 次数、GUI 动作和首次在 replay 后得到覆盖的功能。由于 replay 增加了普通尝试预算之外的交互，覆盖增益不被解释为总交互效率增益。

## RQ3: Context-conditioned environmental risk awareness / 上下文环境风险感知

**English**

RQ3 uses two complementary tracks. Naturally occurring exploration actions provide workflow fidelity but limited risk diversity; an external challenge set provides stronger contextual contrasts but uses actions supplied to the assessor. The exploration-linked track contains 106 run-locally deduplicated ordinary actions from the six RQ2 Full runs, including 32 human-confirmed positives. It evaluates four inputs to the same judge: action only, action plus taxonomy, screenshot plus action, and complete screenshot--action--taxonomy.

The external context-challenge track contains 100 independently sampled screenshot--action cases, including 30 candidate context pairs and 40 diversity cases; 65 are risk-positive. It compares Text-only with Context-conditioned while sharing the same taxonomy, thereby isolating visual context. Compound positives may have multiple acceptable types, while the assessor returns one primary type.

Both tracks report binary precision, recall, F1, and positive-case type accuracy. The external set additionally uses cluster-bootstrap intervals and error analysis. An interval crossing zero is treated as unresolved rather than significant. Risk judgments are produced before execution, but the experiment does not use them to modify actions.

**中文**

RQ3 使用两条互补轨道。自然产生的探索动作具有真实工作流一致性，但风险多样性有限；外部挑战集提供更强上下文对照，但动作由实验提供给判断器。探索关联轨道包含六条 RQ2 Full 运行中 106 条运行内去重普通动作，其中 32 条为人工确认正例。它向同一判断器提供四种输入：仅动作、动作加 taxonomy、截图加动作，以及完整的截图—动作—taxonomy。

外部 context-challenge 轨道包含 100 条独立抽样的截图—动作样本，其中有 30 个候选上下文 pair 和 40 条 diversity 样本；65 条为风险正例。它在共享同一 taxonomy 的条件下比较 Text-only 与 Context-conditioned，从而隔离视觉上下文。复合正例可以有多个可接受类型，而判断器只返回一个主要类型。

两条轨道均报告二元 precision、recall、F1 和正例类型准确率。外部集合还使用 cluster bootstrap 区间和错误分析。区间跨 0 的差异被视为未明确，而不是显著。风险判断在执行前生成，但实验不据此改变动作。
