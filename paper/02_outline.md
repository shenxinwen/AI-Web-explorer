# 论文大纲

本文件是当前正式论文大纲。早期中文工作大纲已归档为 [`archive/大纲v3.md`](archive/大纲v3.md)，仅用于追溯，不再要求与本文件同步更新。

## 暂定题目

Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration

## 摘要结构（待撰写）

1. 背景：任务导向 Web Agent 的交互经验难以沉淀为应用级知识。
2. 问题：自动探索产生的功能提议并不天然等于可靠知识，自主生成并执行验证目标还可能造成真实副作用。
3. 方法：维护 evidence-grounded functional model，通过执行前风险识别、真实执行和前后观察持续更新验证状态、证据链与风险信息。
4. 评价：功能模型质量、风险感知探索、下游规划与行为验证。
5. 结果：待实验完成后填写，不能提前作效果性陈述。

## 1. Introduction

### 1.1 Background and Problem

自主 Web/GUI 探索能够自动提出目标并发现页面、功能和转移，但“探索到信息”不等于“获得可靠知识”；自动化程度越高，越需要识别和记录系统主动行为的潜在副作用。

### 1.2 Two Core Challenges

1. 候选动作被发现、executor 报告执行成功，都不能直接证明预期功能结果真实发生，因而不能直接作为功能知识准入依据。
2. 验证未知功能可能触发删除、发送、授权、交易等高影响或不可逆行为。

### 1.3 Approach

将问题表述为 evidence-grounded and risk-aware functional model induction，通过功能假设、执行前风险识别、真实 GUI 执行、动作前后观察和证据判断持续维护模型。

### 1.4 Contributions

概述三项贡献：evidence-grounded functional modeling、execution-grounded open-ended model induction、risk-aware open-ended exploration。

## 2. Related Work

### 2.1 Autonomous GUI Exploration and Environment Modeling

讨论 GUI-explorer、UIExplore-Bench、UI-KOBE、GraphPilot、EAM、ActionEngine 等方向。明确 Web 探索、知识图、状态机记忆和 frontier 均已有研究，重点界定本文在“如何用动作前后证据验证预期功能结果，并避免把候选发现或执行器成功直接当作功能知识”上的差异。

### 2.2 Safe and Reliable GUI Agents

讨论 Guided Exploration of User-Sensitive Screens、OS-Sentinel、OSGuard、SeerGuard 等敏感状态发现、危险动作识别与后果预测工作。不主张首次考虑自动探索安全；区分本文把 task-free 探索中已选动作的风险判断与功能假设及证据链关联保存的场景。

## 3. Method

### 3.1 Problem Formulation

定义未知 Web GUI、任务无关开放探索、交互轨迹、应用级功能模型及风险约束。

### 3.2 Evidence-Grounded Functional Model

定义候选、executor-reported success 与 verified functional outcome 三个不同层次。每个候选关联一个执行前冻结的 expected observable outcome；系统仅在动作后证据支持该预期结果时准入对应功能知识。验证被明确用于持久功能知识准入，而不只是当前动作纠错；该机制旨在减少未经支持的知识准入，不构成绝对正确性保证。

- Semantic Location and High-Level Function
- Location Constraint and Observed Direct Action Dependency
- Functional Outcome
- Verification State and Interaction Evidence

### 3.3 Open-Ended Functional Model Induction

- Function Hypothesis Proposal
- Execution and Outcome Observation
- Evidence-Driven Model Update
- Persistent Frontier

### 3.4 Risk-Aware Open-Ended Exploration

定义截图、已选动作 label 与版本化风险库共同驱动的 VLM 二元风险判断；确认与拦截不是当前必要机制。

### 3.5 Conservative Downstream Projection

仅将达到证据要求的知识投影给规划/验证模型；PDDL-compatible representation 为一种实例。

## 4. Experiments

### 4.1 Functional Model Quality

在固定候选、执行前预期结果和交互轨迹下，比较“候选即事实”“executor success 即事实”和基于可观察结果验证的知识准入，对应 C1。主表报告 admitted knowledge precision、supported knowledge retention 和 admission yield；验证器一致性与证据完整性作为诊断。

### 4.2 Execution-Grounded Model Induction

在固定应用、起点和交互预算下，评价经支持功能覆盖、有效证据获取、知识增长和 persistent frontier 恢复，对应 C2。

### 4.3 Risk-Aware Exploration

评价自动探索中已选执行动作的风险识别、分类、上下文敏感性和记录完整性，对应 C3。

### 4.4 Downstream Planning and Behavior Verification

作为辅助效用实验，评价保守投影是否能支持新目标的路径规划，并减少使用未经证据支持的功能知识。

核心消融：w/o evidence-based outcome verification、w/o persistent frontier、w/o visual context / w/o taxonomy risk detection。

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
