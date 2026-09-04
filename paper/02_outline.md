# 论文大纲

本文件同步仓库根目录的当前工作大纲 [`大纲v3.md`](../大纲v3.md)，作为 `paper/` 工作区中的章节级状态。根目录文件仍是 v3 的完整论述来源；后续发生结构变更时应同时更新本文件与 `STATUS.md`。

## 暂定题目

Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration

## 摘要结构（待撰写）

1. 背景：任务导向 Web Agent 的交互经验难以沉淀为应用级知识。
2. 问题：开放探索产生的功能提议并不天然等于可靠知识，主动验证还可能造成真实副作用。
3. 方法：维护 evidence-grounded functional model，通过真实执行、前后观察和风险约束持续更新验证状态与证据链。
4. 评价：功能模型质量、风险感知探索、下游规划与行为验证。
5. 结果：待实验完成后填写，不能提前作效果性陈述。

## 1. Introduction

### 1.1 Background and Problem

任务导向 Web/GUI Agent 主要围绕当前任务和观察即时决策；任务无关探索虽能主动发现页面、功能和转移，但“探索到信息”不等于“获得可靠知识”。

### 1.2 Two Core Challenges

1. 功能提议、执行器成功和预期功能结果之间存在 grounding 缺口。
2. 验证未知功能可能触发删除、发送、授权、交易等高影响或不可逆行为。

### 1.3 Approach

将问题表述为 evidence-grounded and risk-aware functional model induction，通过功能假设、真实 GUI 执行、动作前后观察、证据判断和风险约束持续维护模型。

### 1.4 Contributions

概述三项贡献：evidence-grounded functional modeling、execution-grounded open-ended model induction、risk-aware functional verification。

## 2. Related Work

### 2.1 Autonomous GUI Exploration and Environment Modeling

讨论 GUI-explorer、UIExplore、UI-KOBE、GraphPilot、EAM 等方向，重点界定本文在“假设如何经真实执行与结果观察转化为有状态、可追溯知识”上的差异。

### 2.2 Safe and Reliable GUI Agents

讨论任务执行阶段的危险动作识别与后果预测，并区分本文“为理解未知 GUI 而主动探索时如何约束功能验证”的场景。

## 3. Method

### 3.1 Problem Formulation

定义未知 Web GUI、任务无关开放探索、交互轨迹、应用级功能模型及风险约束。

### 3.2 Evidence-Grounded Functional Model

- Semantic Location and High-Level Function
- Location Constraint and Observed Direct Action Dependency
- Functional Outcome
- Verification State and Interaction Evidence

### 3.3 Open-Ended Functional Model Induction

- Function Hypothesis Proposal
- Execution and Outcome Observation
- Evidence-Driven Model Update
- Persistent Frontier

### 3.4 Risk-Aware Functional Verification

定义影响程度、可恢复性、commit boundary 与部分支持状态；具体机制仍待收紧。

### 3.5 Conservative Downstream Projection

仅将达到证据要求的知识投影给规划/验证模型；PDDL-compatible representation 为一种实例。

## 4. Experiments

### 4.1 Functional Model Quality

评价功能、结果、直接动作依赖和证据可追溯性。

### 4.2 Risk-Aware Exploration

评价高影响或不可逆行为与有效模型覆盖之间的权衡。

### 4.3 Downstream Planning and Behavior Verification

评价保守投影是否能支持新目标的路径规划，并减少使用未经证据支持的功能知识。

核心消融：w/o evidence-based outcome verification、w/o persistent frontier、w/o risk-aware verification。

## 5. Limitations and Ethics Statement

讨论探索覆盖边界、VLM 与执行器误判、部分支持知识、风险判断的覆盖代价以及动态网站中的知识失效。

## 6. Conclusion

总结从 function hypothesis 经 execution、observation 到 evidence-based model update 的主线，以及风险约束和保守下游投影。

## 7. Reproducibility Statement

待环境、模型、数据、配置和生成命令冻结后填写。

## 8. References

待相关工作核实后维护正式参考文献。

## 9. Appendix

预留模型 schema、提示词、风险策略、评测标注规范、完整实验矩阵和案例分析。
