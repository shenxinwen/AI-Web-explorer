# 相关工作

| 方向 | 已核实代表工作 | 与本文的关系 | 基线可行性 |
| --- | --- | --- | --- |
| Autonomous GUI Exploration | [GUI-explorer (ACL 2025)](https://aclanthology.org/2025.acl-long.282/)、[UIExplore-Bench](https://arxiv.org/abs/2506.17779)、[UI-KOBE](https://arxiv.org/abs/2605.29534) | 已覆盖自动目标生成、真实交互轨迹、功能覆盖、图构建和欠探索节点重访。本文不能把 Web 探索或 persistent frontier 本身作为创新；C2 应聚焦为功能假设持续产生支持/否定证据的过程。 | UIExplore-Bench 的 GitLab Screen 模式、Random、BFS/DFS 和 UIExplore-AlGo 最适合 C2；GUI-explorer 有代码但主要面向移动 GUI；UI-KOBE 有代码但迁移成本较高。 |
| Environment Modeling and Executable Memory | [GraphPilot](https://arxiv.org/abs/2601.17418)、[EAM](https://arxiv.org/abs/2605.12294)、[ActionEngine](https://arxiv.org/abs/2602.20502) | 已覆盖页面/元素功能、状态转移规则、状态机记忆、执行路径验证和失败后更新。C1 不以“存在验证”为差异，而将验证明确建模为持久功能知识的准入门槛：候选、executor success 与 verified knowledge 分离，候选的执行前 expected outcome 必须获得执行后证据支持。 | GraphPilot/EAM 主要适合定位及下游比较；ActionEngine 是 Web 场景的重要近邻，需继续核查其验证结果是否直接控制持久知识准入。 |
| Action-Effect Verification | [VeriGUI (ACL 2026)](https://aclanthology.org/2026.acl-long.1335/) | 已显式建模预期 action effect、后续验证和失败恢复，因此 expected-effect verification 或 VLM 复审不能单独作为首次贡献。本文聚焦验证结果对开放探索所得持久功能知识的准入作用，并直接测量准入准确性与有效知识保留。 | 主要用于 C1 的概念和机制对照；其任务导向、训练式移动 GUI 设置不宜直接作为同环境主 baseline。 |
| Safe and Reliable GUI Agents | [Guided Exploration of User-Sensitive Screens](https://arxiv.org/abs/2606.25705)、[OS-Sentinel (ACL 2026)](https://aclanthology.org/2026.acl-long.431/)、[OSGuard](https://arxiv.org/abs/2606.15034)、[SeerGuard](https://arxiv.org/abs/2607.15550) | 已有工作覆盖敏感状态探索、step/trajectory-level 风险检测以及基于当前 GUI 和 proposed action 的执行前风险判断。本文不能主张首次考虑探索安全；C3 的差异是 task-free 功能探索中的已选动作判断，以及风险记录与功能假设、轨迹和长期证据的关联。 | SeerGuard 有公开代码，是最接近的 C3 方法候选；OS-Sentinel 是重要方法参照；OSGuard 可作外部动作级评测，但标签依赖用户指令，与本文设定不同。 |

## 差异化定位

本文相关工作分析应围绕同一个问题展开：探索产生的候选信息何时可以成为下游可使用的环境知识。重点比较以下维度：

统一缺口表述为：现有方法能够探索界面、验证动作效果或评估执行风险，但没有显式管理 task-free 探索如何形成风险判断与证据状态共同可追溯的持久功能知识。该表述不主张三个方向从未被组合，而聚焦于“自主验证行为的风险”和“所得功能知识的准入状态”是否在同一证据链中被共同表达。

其中，C2 关注探索过程如何持续产生交互证据，C1 关注给定这些证据后如何判定、表示和准入功能知识；比较相关工作时应分别核查这两个层面。

1. 功能是由静态观察提出，还是经过真实 GUI 交互支持；
2. 是否区分执行器成功与功能结果成功；
3. 是否显式保存 Proposed、Partially Supported、Interaction-Supported、Failed、Incomplete 等知识状态；
4. 是否能从结论回溯 hypothesis、execution trace、before/after observations 和 outcome judgment；
5. 是否在自动探索阶段识别候选功能的潜在风险；
6. 是否将二元风险判断、主要风险类型和判断证据写入长期环境模型。

## 当前基线建议

- **RQ1 / C1：** 在同一冻结候选和轨迹上比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission。外部工作用于定位和机制核查，不作为 C1 主实验的硬性数值 baseline。
- **RQ2 / C2：** 主实验在同一实现和动作空间内比较 Random、Linear 与 Full，以隔离证据生产、依赖感知选择和 persistent-frontier replay 的作用，并检查可靠知识归纳是否保留有用功能覆盖。UIExplore-Bench、GUI-explorer 与 UI-KOBE 用于探索思想和机制对照；不以通用覆盖领先作为论文成立条件。
- **RQ3 / C3：** 以共享 taxonomy 下的 Text-only 与 Context-conditioned 输入比较隔离视觉上下文贡献；SeerGuard、OS-Sentinel、OSGuard 和 WebGuard 用于相关工作、协议参照或样本来源，不作为任务与标签不一致条件下的直接数值 baseline。

以上为第一轮核实结果。正式冻结 baseline 前仍需确认 ActionEngine、OS-Sentinel、OSGuard 和 SeerGuard 的代码、数据许可、输入输出映射及运行成本。

## 写作约束

- 相关工作只用于界定既定贡献边界，不在本节新增论文主线。
- high-level action、persistent frontier、状态图、VLM、浏览器执行器和符号规划均不得被暗示为本文首创。
- 风险知识库是方法组件而非独立创新，不依赖或强调 SafeSym。
- 在正式稿中写出优先权或性能差异前，必须先核实原论文与实验设置。
