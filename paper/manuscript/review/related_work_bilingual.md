# VERA Related Work: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation. Citation metadata was previously checked against the cited records.

## Autonomous exploration and environment models / 自主探索与环境模型

**English**

GUI-explorer, UIExplore-Bench, and GUI-Bee treat interaction as a means to discover environment-specific functionality or collect grounding data. UI-KOBE, EAM, GraphPilot, and ActionEngine further organize experience into reusable graphs or state-machine memories. These systems establish exploration, structured memory, and revisitation as important mechanisms. VERA changes the evidential status of their typical outputs: a discovered function remains a hypothesis until an observable outcome supports its admission to persistent knowledge.

**中文**

GUI-explorer、UIExplore-Bench 和 GUI-Bee 将交互作为发现环境特定功能或收集 grounding 数据的手段。UI-KOBE、EAM、GraphPilot 和 ActionEngine 进一步把经验组织成可复用图结构或状态机记忆。这些系统确立了探索、结构化记忆和重新访问的重要性。VERA 改变的是这些输出的证据地位：被发现的功能仍然是假设，只有可观察结果支持时才能进入持久知识。

## Action-effect verification / 动作效果验证

**English**

VeriGUI predicts action effects and checks subsequent observations for execution recovery, while VAGEN equips a verifier with interaction tools for collecting task-completion evidence. GraphPilot and ActionEngine also validate or repair execution against stored transitions. VERA uses the same general insight---execution claims require environmental evidence---but assigns verification a different decision role. In task-free model induction, the verifier controls whether a location-conditioned functional claim becomes reusable knowledge, rather than only whether the current task should continue or recover.

**中文**

VeriGUI 预测动作效果并检查后续观察以恢复执行，VAGEN 则让验证器使用交互工具收集任务完成证据。GraphPilot 和 ActionEngine 也依据已保存状态转移验证或修复执行。VERA 采用相同的一般认识——执行主张需要环境证据——但赋予验证不同的决策角色：在无任务条件的模型归纳中，验证器决定位置条件下的功能主张能否成为可复用知识，而不只是决定当前任务应该继续还是恢复。

## Risk-aware GUI agents and positioning / 风险感知 GUI 智能体与本文定位

**English**

WebGuard predicts outcomes and risk levels for state-changing Web actions; OS-Sentinel and OSGuard combine contextual judgment with safety specifications or state invariants; and SeerGuard evaluates proposed actions in the current GUI state before execution. VERA studies contextual risk at a different interface: the assessed action is being used to acquire evidence for an unknown function. Its risk record is therefore linked to the same claim, execution trace, and outcome evidence that govern knowledge admission.

VERA connects these directions around a single question: how should an open-ended agent acquire reusable functional knowledge when both the conclusion and the act of testing it carry risk? This yields a common trace from a frozen hypothesis and pre-action risk record through execution evidence to an admission decision. The contribution is this role assignment and connection in task-free functional model induction, rather than a new foundation model, browser executor, exploration primitive, or standalone risk taxonomy.

**中文**

WebGuard 预测改变 Web 状态的动作结果和风险等级；OS-Sentinel 与 OSGuard 将上下文判断同安全规范或状态不变量结合；SeerGuard 则在执行前结合当前 GUI 状态判断候选动作。VERA 在不同接口上研究上下文风险：被判断的动作正在用于为未知功能获取证据。因此，风险记录会与控制知识准入的同一功能主张、执行轨迹和结果证据关联。

VERA 围绕一个问题连接上述方向：当结论本身和检验结论的动作都带有风险时，开放式智能体应如何获取可复用功能知识？由此形成从冻结假设和执行前风险记录，经执行证据，到准入决定的共同轨迹。本文贡献是这些对象在无任务功能模型归纳中的角色分配与连接，而不是新的基础模型、浏览器执行器、探索原语或独立风险分类体系。
