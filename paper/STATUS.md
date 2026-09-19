# 论文状态

> 最后更新：2026-09-17
>
> 维护规则：只记录当前有效结论、证据缺口和下一步；详细内容写入对应专题文件。

## 投稿目标

- 目标会议：ICLR 2027
- 论文题目：VERA: Verification and Environmental Risk Awareness for Functional Model Induction through Open-Ended Web Exploration
- 当前阶段：论文标题、摘要提交版、keywords 与 TL;DR 已暂定；ICLR 2027 官方 LaTeX 模板已放入 `manuscript/`，下一阶段开始搭建匿名主稿。C1 正式结果已归档；C2 formal v2 的 18 条运行、人工确认覆盖账本与结果包均已冻结；C3 正式效果实验尚未开始。

## 写作状态

- 正式 LaTeX 入口：`manuscript/iclr2027_conference.tex`。
- 原始模板备份：`manuscript/iclr2027_conference_template.tex`；后续不在该文件上撰写正文。
- 投稿模式：保持 `\iclrfinalcopy` 注释，作者身份不写入匿名投稿版本。
- 标题已暂定为 VERA 正式标题；摘要提交版已暂定，C2 结果句可更新，仍待 C3 最终结果完成后统一定稿。
- Keywords 暂定为：`web agents, open-ended web exploration, GUI agents, functional model induction, evidence-grounded verification, knowledge admission, environmental risk awareness`。
- TL;DR 暂定为：`VERA builds reliable functional models through open-ended web exploration by assessing interaction risks in context and admitting only evidence-supported functions, while preserving useful functional coverage.`
- `manuscript/sections/` 尚未开始写作；模板示例正文尚未替换。
- 当前本地环境未检测到 `latexmk` 或 `pdflatex`，现阶段使用 Overleaf 编译；若后续安装本地 TeX 工具链，再补充本地编译命令。

## 当前有效结论

- 研究问题：智能体如何通过开放式 Web 探索归纳可靠、可审查的功能知识，同时感知其自主探索动作可能给环境带来的风险，并避免为了可靠性与风险感知而实质性放弃功能发现能力。
- 统一主线：探索是提出可检验假设并产生真实交互证据的手段；可靠、可审查的功能模型是主要产物；执行前环境风险判断是自主产生证据时的监督与审计维度。论文不以通用探索覆盖领先作为主要目标。
- 核心模型统一表达 semantic location、high-level function、location constraint、observed direct action dependency、functional outcome、verification state 和 interaction evidence；交互级 risk annotation 与相应功能假设、GUI observation 和轨迹关联，但不作为 high-level function 的上下文无关属性。
- C1 已收敛为 evidence-grounded functional verification and knowledge admission：候选发现与 executor-reported success 均不直接构成功能知识。每个候选在执行前同时生成并冻结一句 expected observable outcome；只有执行后证据支持该结果的候选才进入持久功能模型。
- 三项并列且相互依赖的核心贡献已确定：evidence-grounded knowledge admission、execution-grounded open-ended functional model induction、environmental risk awareness for open-ended exploration。
- C1–C3 的接口已明确：C2 发现候选、生成执行前 expected outcome，并产生交互轨迹和前后观察；C3 在已选验证动作执行前生成并关联环境风险判断；C1 使用冻结的主张与执行后证据验证 functional outcome，并据此输出 proposed → admitted / rejected。VLM 是当前可替换的生成器和判断器，不是贡献本身。
- C1 自然实验固定同一组候选和轨迹，比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission；主指标为 admitted knowledge precision、supported knowledge retention 和 admission yield，验证器一致性及 executor–outcome disagreement 为诊断。
- C1 正式实验固定为 SauceDemo 与 Practice Shopping；RealWorld 的一次非正式资格检查因证据完整性不足而排除，不进入任何正式统计。受控挑战集仅在自然负样本不足时再考虑，不与自然样本混合报告。
- 风险机制在每个普通探索或 replay 动作执行前，将当前截图、已选 high-level action label 和完整风险库交给独立 VLM 作上下文条件判断，保存本次交互的二元风险标记、一个主要风险类型和页面证据。
- 风险检测以 shadow mode 运行：判断不拦截动作；检测失败时 fail-open 并记录错误，保证探索链路可继续。
- 当前风险贡献聚焦检测、记录和可审查性，不主张已经拦截危险动作或保证探索安全。
- 已核实 Web 开放探索、Web 状态机记忆和自动探索安全均有直接相关工作，因此不将“Web 环境”或“首次考虑探索安全”作为创新主张。
- C3 的差异化定位收紧为：在 task-free/open-ended 功能归纳中，将已选动作的风险判断与功能假设、执行轨迹和结果证据关联保存。
- 下游规划与行为验证用于检验模型价值；PDDL、SafeSym、VLM、浏览器执行器和 persistent frontier 均不作为独立创新。
- C1 正式结果已归档：45 条候选功能中有 33 条人工支持知识。Evidence-grounded admission 的 precision 为 96.97%，supported knowledge retention 为 96.97%，高于 proposal-as-fact 的 73.33% precision 和 executor-success-as-fact 的 82.50% precision。该结论目前仅限 C1 的两个正式网站和冻结设置。
- C2 主实验已收敛为 Random、Linear、Full 三条件比较，唯一主指标为有交互证据支持的功能覆盖率；覆盖增长、有效尝试率以及 replay 成本与新增覆盖作为辅助分析。该实验用于评估可靠知识归纳是否保留有用的功能发现能力，而非宣称通用探索能力领先。Replay GUI 动作不计入普通候选 attempt 预算，但单独限额和报告。
- C2 formal v2 的 18 条运行已执行，覆盖账本 v1 已人工确认并冻结。网站 macro-average 为 Random 28.8%、Linear 42.6%、Full 54.5%，Full 相对 Linear 为 +11.9 pp；replay GUI 成本单列。SauceDemo Linear/Full 的登录失败 run_03 原件已归档，重跑结果已提升为标准 `run_03`。最终报告为 `paper/experiments/results/E004/c2_final_results.md`。

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
- C2 三条件开关、随机 seed、replay GUI 动作计数、恢复后 attempt 关联、完整 attempt 导出和离线指标/绘图脚本已实现并通过回归；pilot 与 formal v2 的 18 条运行、覆盖映射与最终汇总均已冻结。
- 冻结可复现环境、模型版本、配置、轨迹与结果工件格式。
- 将 ICLR 模板示例整理为匿名主稿骨架，并开始逐节写作；当前尚无本地 LaTeX 编译器。

## 下一步

1. 在 `manuscript/iclr2027_conference.tex` 中建立匿名论文骨架，将章节正文拆分到 `manuscript/sections/`，并替换模板示例内容。
2. 优先撰写 Introduction、Problem Formulation 与 Method；写作时以 `00_scope.md`、`01_contributions.md` 和 `04_method.md` 为事实边界。
3. 将 C2 冻结结果写入匿名主稿的实验与结果章节，并保持描述统计口径。
4. 执行 E002 / C3 pilot 与正式评测，报告风险 precision/recall/F1、类型准确率、上下文消融及记录完整率。
5. C1–C3 完成后更新摘要结果句；不得把 shadow-mode 风险感知写成端到端安全提升。
