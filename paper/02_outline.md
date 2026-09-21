# 论文大纲

本文件是当前正式论文大纲。早期中文工作大纲已归档为 [`archive/大纲v3.md`](archive/大纲v3.md)，仅用于追溯，不再要求与本文件同步更新。

## 论文题目

VERA: Verification and Environmental Risk Awareness for Functional Model Induction through Open-Ended Web Exploration

## 摘要结构（待撰写）

1. 背景：任务无关的开放探索能够发现网站功能，但其价值不应只由覆盖率衡量。
2. 问题：自动探索同时引入两类关联风险——功能提议或 executor success 可能被错误持久化为知识，而自主验证动作也可能对环境产生重要后果。
3. 缺口：现有方法可以探索界面、验证动作效果或判断执行风险，但没有显式管理 task-free 探索如何形成风险信息与证据状态共同可追溯的持久功能知识。
4. 方法：VERA 通过执行前环境风险判断、真实 GUI 交互、执行前冻结的 expected outcome 和执行后证据准入持续归纳功能模型。
5. 评价：知识准入可靠性；在固定预算下保留的证据支持功能覆盖；已选探索动作的风险识别与记录完整性。
6. 结果：C1 提高知识准入 precision，C2 在固定普通动作预算下保留并提高证据支持覆盖，C3 的视觉上下文显著改善可接受风险类型 grounding，并呈现更高 recall、较低 precision 的二元权衡。

## 1. Introduction

### 1.1 Background and Problem

自主 Web/GUI 探索能够自动提出目标并发现页面、功能和转移，但“探索到信息”不等于“获得可靠知识”；自动化程度越高，越需要在不实质性放弃功能发现能力的情况下，提高所得知识的可靠性并识别系统主动行为的潜在环境风险。

### 1.2 Two Risks of Autonomous Evidence Production

1. 候选动作被发现、executor 报告执行成功，都不能直接证明预期功能结果真实发生，因而不能直接作为功能知识准入依据。
2. 验证未知功能可能触发删除、发送、授权、交易等高影响或不可逆行为，而这些风险判断通常没有与最终形成的功能知识和证据链共同保存。

### 1.3 Approach

将问题表述为 evidence-grounded and risk-aware functional model induction，通过功能假设、执行前风险识别、真实 GUI 执行、动作前后观察和证据判断持续维护模型。

### 1.4 Contributions

概述统一问题下的三条机制与证据轨道：evidence-grounded knowledge admission 控制模型归纳的认知风险，environmental risk awareness 使证据生产行为的潜在后果可感知和可审查，execution-grounded open-ended exploration 为二者生产候选、轨迹和观察证据。强调安全是动机，当前贡献是风险感知而非风险阻断。

## 2. Related Work

### 2.1 Autonomous GUI Exploration and Environment Modeling

讨论 GUI-explorer、UIExplore-Bench、UI-KOBE、GraphPilot、EAM、ActionEngine 等方向。明确 Web 探索、知识图、状态机记忆和 frontier 均已有研究，重点界定本文在“如何用动作前后证据验证预期功能结果，并避免把候选发现或执行器成功直接当作功能知识”上的差异。

### 2.2 Safe and Reliable GUI Agents

讨论 Guided Exploration of User-Sensitive Screens、OS-Sentinel、OSGuard、SeerGuard 等敏感状态发现、危险动作识别与后果预测工作。不主张首次考虑自动探索安全；区分本文在 task-free 探索中对“当前 GUI 上下文中的已选动作”作交互级风险判断，并将其与功能假设及证据链关联保存的场景。

## 3. Method

### 3.1 Problem Formulation

定义未知 Web GUI、任务无关开放探索、交互轨迹、应用级功能模型及风险约束。

### 3.2 Design Principle: Evidence Production under Dual Risk

开放探索提高自主性，但同时产生知识污染风险与环境交互风险。VERA 分离证据生产、知识准入和交互风险监督，并将三者绑定到同一可追溯 interaction record。

### 3.3 Evidence-Grounded Functional Model and Admission

定义候选、executor-reported success 与 verified functional outcome 三个不同层次。每个候选关联一个执行前冻结的 expected observable outcome；系统仅在动作后证据支持该预期结果时准入对应功能知识。验证被明确用于持久功能知识准入，而不只是当前动作纠错；该机制旨在减少未经支持的知识准入，不构成绝对正确性保证。

- Semantic Location and High-Level Function
- Location Constraint and Observed Direct Action Dependency
- Functional Outcome
- Verification State and Interaction Evidence

### 3.4 Open-Ended Evidence Production

- Function Hypothesis Proposal
- Execution and Outcome Observation
- Evidence-Driven Model Update
- Persistent Frontier

### 3.5 Context-Conditioned Environmental Risk Awareness

定义由执行前截图、已选动作 label 与版本化风险库共同驱动的上下文条件 VLM 二元风险判断。风险标注属于具体 interaction attempt，不作为 high-level function 的固定属性；确认与拦截不是当前必要机制。

### 3.6 Conservative Downstream Projection

仅将达到证据要求的知识投影给规划/验证模型；PDDL-compatible representation 为一种实例。

## 4. Experiments

### 4.1 Functional Model Quality

在固定候选、执行前预期结果和交互轨迹下，比较“候选即事实”“executor success 即事实”和基于可观察结果验证的知识准入，对应 C1。主表报告 admitted knowledge precision、supported knowledge retention 和 admission yield；验证器一致性与证据完整性作为诊断。

### 4.2 Execution-Grounded Model Induction

在固定应用、起点和普通候选动作预算下比较 Random、Linear 与 Full，以有交互证据支持的功能覆盖率为主指标，并报告覆盖增长、有效尝试以及 persistent frontier/replay 的新增覆盖和额外 GUI 成本，对应 C2。

### 4.3 Risk-Aware Exploration

评价自动探索中已选执行动作的风险识别、分类、上下文敏感性和记录完整性，对应 C3。

### 4.4 Downstream Planning and Behavior Verification

作为辅助效用实验，评价保守投影是否能支持新目标的路径规划，并减少使用未经证据支持的功能知识。

核心消融：w/o evidence-based outcome verification、w/o persistent frontier，以及 C3 的 Text-only / Context-conditioned 比较。风险 taxonomy 作为共享的形式化表达词汇，不单独承担外部消融主张。

## 5. Limitations and Ethics Statement

讨论探索覆盖边界、VLM 与执行器误判、部分支持知识、风险判断的覆盖代价以及动态网站中的知识失效。

## 6. Conclusion

总结从 function hypothesis 经 risk detection、execution、observation 到 evidence-based model update 的主线，以及风险信息和保守下游投影。

## 7. Reproducibility Statement

待环境、模型、数据、配置和生成命令冻结后填写。

## 8. References

待相关工作核实后维护正式参考文献。

## 9. Appendix

预留模型 schema、提示词、风险策略、评测标注规范、完整实验矩阵和案例分析。
