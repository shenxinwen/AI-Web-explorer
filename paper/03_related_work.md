# 相关工作

| 方向 | 代表工作 | 与本文的关系 | 待核实事项 |
| --- | --- | --- | --- |
| Autonomous GUI Exploration and Environment Modeling | GUI-explorer、UIExplore、UI-KOBE、GraphPilot、EAM（名称与引用待逐篇核实） | 已有工作覆盖功能发现、高层动作、frontier exploration、状态转移图、知识图和 executable memory。本文不把这些组件本身作为创新，而关注功能假设如何经过真实执行和结果观察，转化为具有明确验证状态和可追溯证据的功能知识。 | 正式文献条目；任务设定；是否真实执行；结果验证方式；记忆/图结构；失败与不确定结果的处理方式。 |
| Safe and Reliable GUI Agents | GUI Agent safety、action consequence prediction、危险动作阻断（具体工作待检索） | 既有研究多关注给定任务执行中的危险动作。本文研究任务无关主动探索中的功能验证约束：在获取未知 GUI 知识时避免制造不可逆副作用。风险控制是功能验证约束，不主张为通用安全框架。 | 风险分类；后果预测粒度；可逆性建模；是否支持 commit boundary；安全性和覆盖率的评价指标。 |

## 差异化定位

本文相关工作分析应围绕同一个问题展开：探索产生的候选信息何时可以成为下游可使用的环境知识。重点比较以下维度：

1. 功能是由静态观察提出，还是经过真实 GUI 交互支持；
2. 是否区分执行器成功与功能结果成功；
3. 是否显式保存 Proposed、Partially Supported、Interaction-Supported、Failed、Incomplete 等知识状态；
4. 是否能从结论回溯 hypothesis、execution trace、before/after observations 和 outcome judgment；
5. 是否在主动探索阶段限制高影响或不可逆验证。

## 写作约束

- 相关工作只用于界定既定贡献边界，不在本节新增论文主线。
- high-level action、persistent frontier、状态图、VLM、浏览器执行器和符号规划均不得被暗示为本文首创。
- 在正式稿中写出优先权或性能差异前，必须先核实原论文与实验设置。
