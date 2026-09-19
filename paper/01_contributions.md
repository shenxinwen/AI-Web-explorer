# 核心贡献与证据链

每项贡献应是可由实验、分析或证明支持或推翻的明确主张。

| ID | 主张 | 所需证据 | 当前状态 |
| --- | --- | --- | --- |
| C1 | **Evidence-Grounded Functional Verification and Knowledge Admission：** 本文将功能验证建模为知识准入问题，显式区分 candidate discovery、executor-reported success 与 verified functional outcome。每个候选在执行前关联一个冻结的、可观察的 expected outcome；只有执行后证据支持该结果时，候选才进入持久功能模型。该机制旨在减少未经支持的知识准入，而非保证绝对正确。 | 在相同候选与冻结交互轨迹下，比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission，检验其能否提高准入知识准确性，同时保留已获得支持的有效功能知识。 | 正式实验完成；结果见 E003 |
| C2 | **Execution-Grounded Open-Ended Functional Model Induction：** 通过“提出可检验功能假设 → GUI 执行 → 结果观察 → 证据判定”持续产生 C1 所需的支持或否定证据，并将未完成假设保留到可恢复的探索上下文中。依赖感知选择、persistent frontier 与 replay 是证据生产机制，而非独立创新。 | 在固定普通候选动作预算下比较 Random、Linear、Full；报告有交互证据支持的功能覆盖率、覆盖增长、有效证据产生率，以及 replay 新增覆盖与额外 GUI 成本。该实验用于证明可靠知识归纳仍保留有用的功能发现能力，而非主张通用探索能力领先。 | 正式 v2 的 18 条运行与人工确认覆盖账本已冻结：网站 macro-average 为 Random 28.8%、Linear 42.6%、Full 54.5%；Full 相对 Linear 为 +11.9 pp。 |
| C3 | **Context-Conditioned Environmental Risk Awareness for Open-Ended Exploration：** 将当前 GUI observation、已选 high-level action 与风险分类知识共同用于执行前环境风险判断，并把交互级二元判断、主要风险类型和界面证据与相应功能假设及交互轨迹关联保存。风险不是动作或功能脱离上下文后的固定属性。 | 风险识别 precision/recall/F1；风险类型准确率；动作语义与视觉上下文消融；相同/相似动作在不同上下文中的对照案例；风险记录与功能/轨迹的关联完整率；普通探索与 replay 覆盖。 | 最小机制已实现；当前为不改变执行的 shadow mode，效果证据待实验 |

## 贡献之间的证据链

1. C1 定义可检验的功能主张、执行前冻结的 expected outcome、执行后证据验证和持久知识准入规则。
2. C2 通过开放式真实交互持续产生 C1 所需的证据。
3. C3 为 C2 自主生成的功能验证目标提供执行前风险感知，并使探索过程可追踪、可审查。
4. 下游规划与行为验证用于检验 C1–C3 产生的模型是否具有应用价值，但不作为第四项独立贡献。

统一主张是：**VERA 以开放探索持续产生证据，以执行后验证控制知识准入，并在执行前显式记录环境风险；可靠性与风险感知是优化目标，功能覆盖是需要保留并报告代价的基础能力。**

概念接口为：**C2 输出候选、执行前 expected outcome、交互轨迹与前后观察；C1 消费冻结的主张与证据，区分 executor-reported success 与 verified functional outcome，并输出 proposed → admitted / rejected 的准入决定。** 工程实现可以将两者放在同一循环中，但论文定义和实验控制变量必须分开。

## 当前不应提前写入的效果性结论

- “减少无效尝试”与“减少重复探索”只有在对应诊断指标支持后才能报告；C2 的功能覆盖率用于衡量可靠知识归纳是否过度牺牲探索能力，不用于笼统宣称探索能力领先。
- 风险检测不等于实际拦截，也不能直接证明探索过程已经更加安全。
- Web 环境本身不是创新点；已有工作已研究 Web UI 开放探索与 Web GUI 状态机记忆。
- 不主张本文首次考虑自动探索安全；本文的差异是将已选动作风险判断与开放式功能归纳及其证据链结合。
- PDDL 与 SafeSym 仅是保守投影和下游验证的实例，不是核心方法贡献。
