# 核心贡献与证据链

每项贡献应是可由实验、分析或证明支持或推翻的明确主张。

| ID | 主张 | 所需证据 | 当前状态 |
| --- | --- | --- | --- |
| C1 | **Evidence-Grounded Functional Modeling：** 将 semantic location、high-level function、location constraint、observed direct action dependency、functional outcome、verification state 与 interaction evidence 统一表示，并显式区分功能假设、动作执行和证据支持的知识。 | 功能结论、结果判断和直接依赖的标注准确性；证据链完整性；与直接采用 VLM 提议或普通探索记录的对比。 | 主张已确定，证据待实验 |
| C2 | **Execution-Grounded Open-Ended Model Induction：** 通过“功能假设提出 → GUI 执行 → 前后观察 → 结果判断 → 模型更新”持续维护功能模型，并保留失败、不确定、未完成假设及 persistent frontier。 | 开放探索协议；模型更新案例；功能覆盖和知识可靠性；移除 outcome verification / persistent frontier 的消融。 | 主张已确定，证据待实验 |
| C3 | **Risk-Aware Open-Ended Exploration：** 在候选功能执行前，结合预定义风险知识和当前 GUI 上下文识别潜在副作用，并将风险类型、严重程度、可逆性和判断证据纳入功能模型。 | 风险识别 precision/recall；风险分类准确率；规则库、VLM 与组合方法对比；上下文敏感案例；下游风险信息利用。 | 主张已确定，机制与证据待实验 |

## 贡献之间的证据链

1. C1 定义最终要维护的功能知识及其可信状态。
2. C2 说明这些知识如何由开放式真实交互持续产生和更新。
3. C3 为 C2 自主生成的功能验证目标提供执行前风险感知，并使探索过程可追踪、可审查。
4. 下游规划与行为验证用于检验 C1–C3 产生的模型是否具有应用价值，但不作为第四项独立贡献。

## 当前不应提前写入的效果性结论

- “减少错误尝试”与“减少重复探索”只有在实验支持后才能报告。
- 风险检测不等于实际拦截，也不能直接证明探索过程已经更加安全。
- PDDL 与 SafeSym 仅是保守投影和下游验证的实例，不是核心方法贡献。
