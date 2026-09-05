# 相关工作

| 方向 | 代表工作 | 与本文的关系 | 待核实事项 |
| --- | --- | --- | --- |
| Autonomous GUI Exploration and Environment Modeling | GUI-explorer、UIExplore、UI-KOBE、GraphPilot、EAM（名称与引用待逐篇核实） | 已有工作覆盖自动探索目标生成、功能发现、高层动作、frontier exploration、状态转移图、知识图和 executable memory，主要关注覆盖和知识获取。本文进一步关注功能假设如何经真实执行转化为有证据支持的知识，以及自动探索行为可能带来的风险。 | 正式文献条目；探索目标如何产生；是否真实执行；结果验证方式；是否考虑探索过程风险。 |
| Safe and Reliable GUI Agents | GUI Agent safety、action consequence prediction、危险动作识别与阻断（具体工作待检索） | 既有研究多关注给定用户任务下的安全执行。本文关注自动探索系统自主生成并执行功能验证目标时，如何依据环境上下文和功能语义识别潜在副作用，并将风险信息纳入长期功能模型。 | 是否依赖用户任务；判断对象是任务、轨迹还是候选功能；上下文输入；风险输出；是否进入环境模型。 |

## 差异化定位

本文相关工作分析应围绕同一个问题展开：探索产生的候选信息何时可以成为下游可使用的环境知识。重点比较以下维度：

1. 功能是由静态观察提出，还是经过真实 GUI 交互支持；
2. 是否区分执行器成功与功能结果成功；
3. 是否显式保存 Proposed、Partially Supported、Interaction-Supported、Failed、Incomplete 等知识状态；
4. 是否能从结论回溯 hypothesis、execution trace、before/after observations 和 outcome judgment；
5. 是否在自动探索阶段识别候选功能的潜在风险；
6. 是否将二元风险判断、主要风险类型和判断证据写入长期环境模型。

## 写作约束

- 相关工作只用于界定既定贡献边界，不在本节新增论文主线。
- high-level action、persistent frontier、状态图、VLM、浏览器执行器和符号规划均不得被暗示为本文首创。
- 风险知识库是方法组件而非独立创新，不依赖或强调 SafeSym。
- 在正式稿中写出优先权或性能差异前，必须先核实原论文与实验设置。
