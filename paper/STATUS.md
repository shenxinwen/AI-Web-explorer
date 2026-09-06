# 论文状态

> 最后更新：2026-09-06
>
> 维护规则：只记录当前有效结论、证据缺口和下一步；详细内容写入对应专题文件。

## 投稿目标

- 目标会议：ICLR 2027
- 暂定题目：Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration
- 当前阶段：最小风险感知链路已实现并完成工程冒烟，最小可投稿实验协议 v1 已冻结，待 pilot

## 当前有效结论

- 研究问题：在自动化的开放式 Web 探索中，如何通过真实交互发现并验证应用功能，同时识别系统自主生成的功能验证行为可能带来的环境风险。
- 核心模型统一表达 semantic location、high-level function、location constraint、observed direct action dependency、functional outcome、verification state 和 interaction evidence。
- 论文显式区分功能假设、执行器动作完成和由真实交互结果支持的功能知识。
- 三项核心贡献已确定：evidence-grounded functional modeling、execution-grounded open-ended model induction、risk-aware open-ended exploration。
- C1 与 C2 的边界已明确：C2 通过开放探索产生交互轨迹和前后观察，C1 将这些证据转化为具有验证状态、可追溯且可供下游使用的功能知识。
- 风险机制在每个普通探索或 replay 动作执行前，将当前截图、已选 high-level action label 和完整风险库交给独立 VLM 判断，保存二元风险标记、一个主要风险类型和页面证据。
- 风险检测以 shadow mode 运行：判断不拦截动作；检测失败时 fail-open 并记录错误，保证探索链路可继续。
- 当前风险贡献聚焦检测、记录和可审查性，不主张已经拦截危险动作或保证探索安全。
- 已核实 Web 开放探索、Web 状态机记忆和自动探索安全均有直接相关工作，因此不将“Web 环境”或“首次考虑探索安全”作为创新主张。
- C3 的差异化定位收紧为：在 task-free/open-ended 功能归纳中，将已选动作的风险判断与功能假设、执行轨迹和结果证据关联保存。
- 下游规划与行为验证用于检验模型价值；PDDL、SafeSym、VLM、浏览器执行器和 persistent frontier 均不作为独立创新。
- 尚无论文级实验结果；所有效果性陈述仍是待验证研究问题。

## 已有资产

- 早期项目大纲（归档）：`archive/大纲v3.md`
- 项目实验记录：`../docs/experiments/`
- 项目设计与实现记录：`../docs/`

## 主要缺口

- 冻结风险评测集、人工标注规范和上下文对照样例。
- 验证五类风险在多网站、多动作上的覆盖，并单独评估 replay 链路。
- 设计风险识别标注规范，以及完整方法、w/o visual context、w/o taxonomy 的对比实验。
- 核实相关工作及正式引用，明确最接近方法和可比实验设定。
- 逐字段人工标注指南已建立；论文级 verification state 使用冻结规则从实现字段离线派生，不新增运行时功能。
- Pilot 后补齐指标计算脚本和协议中暴露的必要修正。
- 核查论文方法与当前代码的逐模块映射。
- 冻结可复现环境、模型版本、配置、轨迹与结果工件格式。
- 建立 ICLR LaTex 主稿。

## 下一步

1. 从历史工件导出少量样本，按 `experiments/annotation_guide_v1.md` 完成格式试标；安排第二标注者后完成 20 个样本的一致性试标。
2. 通过现有测试确认 `max_total_replays=0` 与 full 条件可区分，并检查截图路径/attempt metadata 完整性。
3. 运行两网站的 10-attempt pilot；只修复影响指标计算的阻塞问题。
4. Pilot 通过后运行正式实验，并将结果归档到 `experiments/results/`。
5. 并行建立与 `02_outline.md` 对齐的 ICLR LaTex 主稿。
