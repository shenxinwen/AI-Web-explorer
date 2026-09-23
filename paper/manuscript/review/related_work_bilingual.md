# VERA Related Work: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX draft; the Chinese text is a semantic translation. Publication metadata was checked against ACL Anthology or the cited arXiv record on 2026-09-22.

## Autonomous GUI exploration and environment modeling / 自主 GUI 探索与环境建模

**English**

Recent work treats interaction as a way to acquire environment-specific GUI knowledge. GUI-explorer generates function-aware goals, collects trajectories, and mines transition-aware knowledge from observation--action--outcome triples. UIExplore-Bench formalizes autonomous UI exploration as discovering actionable functionality and evaluates both structured and screenshot-only agents, while GUI-Bee explores novel environments to collect data for environment-specific grounding. Other systems organize experience into graphs or state-machine memories for later task execution: UI-KOBE and EAM construct reusable app-specific graph knowledge, GraphPilot records page and element functions together with transitions, and ActionEngine builds an updatable state-machine memory through offline crawling. These works establish that autonomous exploration, graph construction, and revisitation are important mechanisms; VERA does not claim them as new. We instead ask when a function proposed during such exploration has sufficient outcome evidence to enter a persistent functional model, and how the interaction used to obtain that evidence should remain auditable.

**中文**

近期工作将交互视为获取特定 GUI 环境知识的途径。GUI-explorer 生成面向功能的目标、采集轨迹，并从“观察—动作—结果”三元组中挖掘状态转移知识。UIExplore-Bench 将自主 UI 探索形式化为发现可操作功能，并同时评价结构化输入和纯截图智能体；GUI-Bee 则探索新环境，为特定环境的动作定位收集数据。其他系统把经验组织成供后续任务执行使用的图或状态机记忆：UI-KOBE 和 EAM 构建可复用的应用知识图，GraphPilot 同时记录页面、元素功能和转移关系，ActionEngine 通过离线爬取构建可更新的状态机记忆。这些工作已经说明自主探索、图构建和状态重访是重要机制；VERA 不把它们本身作为创新。我们关注的是：探索中提出的功能何时获得了足够的结果证据，可以进入持久功能模型，以及获得这些证据的交互如何保持可审查。

## Action-effect verification and reliable knowledge / 动作效果验证与可靠知识

**English**

Post-action verification is increasingly used to make GUI execution robust. VeriGUI explicitly predicts action effects, checks subsequent observations, and uses failed verification to guide recovery. VAGEN gives a verifier interaction tools with which to probe an environment for task-completion evidence. Validation also appears in memory-based systems: GraphPilot checks generated action sequences against stored transitions, and ActionEngine repairs failed execution while updating its memory. VERA shares the principle that execution claims require environmental evidence, so expected-effect verification itself is not our novelty. The distinction is its role in task-free model induction: verification governs whether a reusable location-conditioned functional claim is admitted to persistent knowledge. Our evaluation therefore holds candidates and trajectories fixed and directly compares proposal-based, executor-status-based, and evidence-grounded admission.

**中文**

动作后验证正越来越多地用于提高 GUI 执行的稳健性。VeriGUI 显式预测动作效果、检查后续观察，并利用验证失败指导恢复。VAGEN 为验证器提供交互工具，使其能够主动探查环境中的任务完成证据。验证也出现在记忆式系统中：GraphPilot 根据存储的转移关系检查生成的动作序列，ActionEngine 在修复执行失败的同时更新记忆。VERA 同样遵循“执行主张需要环境证据”的原则，因此 expected-effect verification 本身不是我们的创新。差异在于验证在 task-free 模型归纳中的作用：它决定一条可复用、位置条件下的功能主张能否进入持久知识。因此，我们固定候选和轨迹，直接比较基于提议、基于执行器状态和基于证据的知识准入。

## Risk awareness and guardrails / 风险感知与防护机制

**English**

Several benchmarks and guardrails assess the consequences of computer-use actions. WebGuard labels state-changing Web actions and trains models to predict their outcomes and risk levels. OS-Sentinel combines formal checks with a contextual VLM judge over realistic mobile trajectories, and OSGuard distinguishes isolated action judgments from end-to-end execution under state-based safety invariants. SeerGuard evaluates proposed actions in the current GUI state and predicts likely consequences before execution. These studies preclude a claim that VERA is the first to consider contextual or pre-execution GUI risk. VERA instead studies this signal inside open-ended functional model induction: a risk record is attached to the selected evidence-gathering action and, for ordinary exploration, linked to the functional claim, execution trace, and subsequent outcome evidence. The current system records this information for awareness and audit; intervention policies are outside the evaluated scope.

**中文**

已有多项 benchmark 和 guardrail 研究计算机操作的后果。WebGuard 标注会改变状态的 Web 动作，并训练模型预测其结果与风险等级。OS-Sentinel 将形式化检查与面向真实移动轨迹的上下文 VLM 判断器结合；OSGuard 则区分孤立的动作级判断和带有状态安全约束的端到端执行。SeerGuard 在当前 GUI 状态下评价智能体提出的动作，并在执行前预测可能后果。因此，VERA 不能声称首次研究上下文相关或执行前 GUI 风险。VERA 的差异在于把这一信号置于开放式功能模型归纳内部：风险记录附着到已选证据采集动作；对于普通探索，它还与功能主张、执行轨迹和后续结果证据关联。当前系统保存这些信息用于感知和审计，具体干预策略不在本文评测范围内。

## Positioning / 本文定位

**English**

Prior work has separately made substantial progress in autonomous exploration, effect verification, persistent GUI memory, and action-risk assessment. VERA focuses on their intersection. It represents open-ended functional model induction as evidence production under two linked concerns: whether an acquired claim is sufficiently supported to become reusable knowledge, and whether the action used to acquire that evidence may have an important environmental consequence. This framing yields a common trace from hypothesis and pre-action risk record through execution evidence to the admission decision.

**中文**

既有工作已经分别在自主探索、效果验证、持久 GUI 记忆和动作风险判断方面取得重要进展。VERA 关注的是这些方向的交叉点：它将开放式功能模型归纳表达为受到两个关联问题约束的证据生产过程——所得主张是否获得足够支持，可以成为可复用知识；以及为获得这些证据所执行的动作，是否可能产生重要环境后果。该框架形成一条共同的可追溯链路，从功能假设和动作执行前风险记录，经由执行证据，最终连接到知识准入决定。
