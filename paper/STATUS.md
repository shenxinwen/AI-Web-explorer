# 论文状态

> 最后更新：2026-09-14
>
> 维护规则：只记录当前有效结论、证据缺口和下一步；详细内容写入对应专题文件。

## 投稿目标

- 目标会议：ICLR 2027
- 暂定题目：Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration
- 当前阶段：C1 正式实验与结果归档已完成；尚未开始撰写论文正文，下一阶段转向 C2 实验准备。

## 当前有效结论

- 研究问题：在自动化的开放式 Web 探索中，如何通过真实交互发现并验证应用功能，同时识别系统自主生成的功能验证行为可能带来的环境风险。
- 核心模型统一表达 semantic location、high-level function、location constraint、observed direct action dependency、functional outcome、verification state 和 interaction evidence。
- C1 已收敛为 evidence-grounded functional verification and knowledge admission：候选发现与 executor-reported success 均不直接构成功能知识。每个候选在执行前同时生成并冻结一句 expected observable outcome；只有执行后证据支持该结果的候选才进入持久功能模型。
- 三项核心贡献已确定：evidence-grounded functional modeling、execution-grounded open-ended model induction、risk-aware open-ended exploration。
- C1 与 C2 的边界已明确：C2 发现候选、生成执行前 expected outcome，并产生交互轨迹和前后观察；C1 使用冻结的主张与证据验证 functional outcome，并据此输出 proposed → admitted / rejected。VLM 是当前可替换验证器，不是 C1 的贡献本身。
- C1 自然实验固定同一组候选和轨迹，比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission；主指标为 admitted knowledge precision、supported knowledge retention 和 admission yield，验证器一致性及 executor–outcome disagreement 为诊断。
- C1 正式实验固定为 SauceDemo 与 Practice Shopping；RealWorld 的一次非正式资格检查因证据完整性不足而排除，不进入任何正式统计。受控挑战集仅在自然负样本不足时再考虑，不与自然样本混合报告。
- 风险机制在每个普通探索或 replay 动作执行前，将当前截图、已选 high-level action label 和完整风险库交给独立 VLM 判断，保存二元风险标记、一个主要风险类型和页面证据。
- 风险检测以 shadow mode 运行：判断不拦截动作；检测失败时 fail-open 并记录错误，保证探索链路可继续。
- 当前风险贡献聚焦检测、记录和可审查性，不主张已经拦截危险动作或保证探索安全。
- 已核实 Web 开放探索、Web 状态机记忆和自动探索安全均有直接相关工作，因此不将“Web 环境”或“首次考虑探索安全”作为创新主张。
- C3 的差异化定位收紧为：在 task-free/open-ended 功能归纳中，将已选动作的风险判断与功能假设、执行轨迹和结果证据关联保存。
- 下游规划与行为验证用于检验模型价值；PDDL、SafeSym、VLM、浏览器执行器和 persistent frontier 均不作为独立创新。
- C1 正式结果已归档：45 条候选功能中有 33 条人工支持知识。Evidence-grounded admission 的 precision 为 96.97%，supported knowledge retention 为 96.97%，高于 proposal-as-fact 的 73.33% precision 和 executor-success-as-fact 的 82.50% precision。该结论目前仅限 C1 的两个正式网站和冻结设置。
- C2 主实验已收敛为 Random、Linear、Full 三条件比较，唯一主指标为有交互证据支持的功能覆盖率；覆盖增长、有效尝试率以及 replay 成本与新增覆盖作为辅助分析。Replay GUI 动作不计入普通候选 attempt 预算，但单独限额和报告。

## 已有资产

- 早期项目大纲（归档）：`archive/大纲v3.md`
- 项目实验记录：`../docs/experiments/`
- 项目设计与实现记录：`../docs/`

## 主要缺口

- C1 的 expected outcome、执行实例、before/after evidence、功能级聚合、人工 gold、三种准入策略和离线指标均已完成；结果及错误案例见 `experiments/results/E003/`。
- 冻结风险评测集、人工标注规范和上下文对照样例。
- 验证五类风险在多网站、多动作上的覆盖，并单独评估 replay 链路。
- 设计风险识别标注规范，以及完整方法、w/o visual context、w/o taxonomy 的对比实验。
- 核实相关工作及正式引用，明确最接近方法和可比实验设定。
- 逐字段人工标注指南已建立；论文级 verification state 使用冻结规则从实现字段离线派生，不新增运行时功能。
- C2 三条件开关、随机 seed、replay GUI 动作计数、恢复后 attempt 关联、完整 attempt 导出和离线指标脚本已实现并通过回归；尚未进行 live pilot。
- 冻结可复现环境、模型版本、配置、轨迹与结果工件格式。
- 建立 ICLR LaTex 主稿。

## 下一步

1. 冻结 E004 / C2 的精确模型、prompt、seed、运行命令和输出目录；不复用 C1 的结果作为 C2 过程指标。
2. 获得确认后运行 6 次 C2 pilot，检查功能覆盖率、覆盖增长曲线、有效尝试率和 frontier/replay 成本记录是否可计算。
3. C2 稳定后再开始 C3 pilot；当前不撰写论文正文。
