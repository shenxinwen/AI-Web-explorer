# 论文状态

> 最后更新：2026-09-21
>
> 维护规则：只记录当前有效结论、证据缺口和下一步；详细内容写入对应专题文件。

## 投稿目标

- 目标会议：ICLR 2027
- 论文题目：VERA: Verification and Environmental Risk Awareness for Functional Model Induction through Open-Ended Web Exploration
- 当前阶段：C1、C2、C3 的正式实验与结果包均已冻结，论文级状态文档已对齐；ICLR 2027 官方 LaTeX 模板已放入 `manuscript/`，下一阶段是搭建匿名主稿并写入三项贡献的有界结果。

## 写作状态

- 正式 LaTeX 入口：`manuscript/iclr2027_conference.tex`。
- 原始模板备份：`manuscript/iclr2027_conference_template.tex`；后续不在该文件上撰写正文。
- 投稿模式：保持 `\iclrfinalcopy` 注释，作者身份不写入匿名投稿版本。
- 标题已暂定为 VERA 正式标题；摘要结构已暂定，现可根据 C1–C3 冻结结果统一形成结果句，但尚未写入匿名主稿。
- Keywords 暂定为：`web agents, open-ended web exploration, GUI agents, functional model induction, evidence-grounded verification, knowledge admission, environmental risk awareness`。
- TL;DR 暂定为：`VERA builds reliable functional models through open-ended web exploration by assessing interaction risks in context and admitting only evidence-supported functions, while preserving useful functional coverage.`
- `manuscript/sections/` 尚未开始写作；模板示例正文尚未替换。
- 当前本地环境未检测到 `latexmk` 或 `pdflatex`，现阶段使用 Overleaf 编译；若后续安装本地 TeX 工具链，再补充本地编译命令。

## 当前有效结论

- 研究问题：智能体如何通过开放式 Web 探索归纳可信的功能模型，同时使其自主证据采集交互可能带来的环境风险显式化并可供审查？开放探索提高自动化与功能发现能力，但同时引入两类关联风险：未经支持的主张可能污染持久知识，验证这些主张的自主交互也可能对环境产生重要后果。
- 统一主线：VERA 将开放探索视为证据生产过程，并区分“所得知识是否可信”与“获得知识的交互是否具有环境风险”。C1 通过执行后证据验证控制知识准入，C3 在执行前记录上下文相关风险，C2 是连接二者的候选发现与证据生产机制。安全是研究动机和长期目标；本文当前完成并评价的是知识可靠性与环境风险感知，而非端到端安全控制。功能覆盖用于检查这些目标是否以过度放弃发现能力为代价，不用于主张通用探索领先。
- 核心知识单元是 location-conditioned functional claim `h=(semantic location, high-level function, frozen expected observable outcome)`；location constraint 与 observed direct action dependency 作为适用性和探索选择元数据保存，不被本次 outcome verification 自动视为已验证的普遍 precondition。模型另表达 functional outcome、三类 evidence judgment、二元 admission indicator 和 interaction evidence。
- 风险判断对象是 observation-conditioned selected browser action `ρ_t=R(o_t,a_t,K)`，不是抽象 high-level function 或整个多动作验证尝试。普通探索记录链接 functional claim、GUI observation、轨迹和结果证据；replay 对每个 action 单独判断并链接 replay step。
- C1 已收敛为 evidence-grounded functional verification and knowledge admission：候选发现与 executor-reported success 均不直接构成功能知识。每个候选在执行前同时生成并冻结一句 expected observable outcome；只有执行后证据支持该结果的候选才进入持久功能模型。
- 三条相互依赖的机制与证据轨道已确定：evidence-grounded knowledge admission 处理功能模型归纳中的认知风险；context-conditioned environmental risk awareness 处理证据生产行为的可感知与可审查性；execution-grounded open-ended exploration 作为二者共享的候选发现与证据生产基础。三者共同服务于“可信功能模型归纳与环境风险感知”这一统一问题，而不是三个松散并列的系统目标。
- C1–C3 的接口已明确：C2 发现候选、生成执行前 expected outcome，并产生交互轨迹和前后观察；C3 在已选验证动作执行前生成并关联环境风险判断；C1 使用冻结的主张与执行后证据产生三类 evidence judgment，并据此设置二元 admission indicator。VLM 是当前可替换的生成器和判断器，不是贡献本身。
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
- C3 正式结果已冻结为两条互补证据轨道。探索关联评测含 106 条 C2 Full 普通探索动作，Full pooled precision/recall/F1 为 86.5%/100.0%/92.8%，但四条件二元 F1 差异均未获得明确区分。外部 context-challenge 含 100 条样本；Context-conditioned 相对 Text-only 的 recall、F1、acceptable-type accuracy 分别提高 12.3、5.2、35.4 pp，precision 下降 4.5 pp。二元差异区间跨 0，类型准确率差异区间为 [+21.7, +49.3] pp。最终报告为 `paper/experiments/results/E002/c3_final_results.md`。
- C3 错误分析显示视觉上下文纠正 16 个二元判断并引入 14 个错误；主要收益是消解模糊动作并改善风险后果类型表达，主要代价是把进入或准备工作流误判为已经产生下游影响。

## 已有资产

- 早期项目大纲（归档）：`archive/大纲v3.md`
- 项目实验记录：`../docs/experiments/`
- 项目设计与实现记录：`../docs/`

## 主要缺口

- C1 的 expected outcome、执行实例、before/after evidence、功能级聚合、人工 gold、三种准入策略和离线指标均已完成；结果及错误案例见 `experiments/results/E003/`。
- 核实相关工作及正式引用，明确最接近方法和可比实验设定。
- 逐字段人工标注指南已建立；主文将冻结实现字段与人工标签归并为 Supported、Unsupported、Unresolved 三类 evidence judgment，并单独表达二元 admission indicator；该论文级抽象不新增运行时功能，也不修改冻结工件。
- C2 三条件开关、随机 seed、replay GUI 动作计数、恢复后 attempt 关联、完整 attempt 导出和离线指标/绘图脚本已实现并通过回归；pilot 与 formal v2 的 18 条运行、覆盖映射与最终汇总均已冻结。
- 补全统一可复现环境说明；C1–C3 的模型、配置、轨迹、人工 gold、指标和结果工件已经分别冻结。
- 将 ICLR 模板示例整理为匿名主稿骨架，并开始逐节写作；当前尚无本地 LaTeX 编译器。

## 下一步

1. 在 `manuscript/iclr2027_conference.tex` 中建立匿名论文骨架，将章节正文拆分到 `manuscript/sections/`，并替换模板示例内容。
2. 优先撰写 Introduction、Problem Formulation 与 Method；写作时以 `00_scope.md`、`01_contributions.md` 和 `04_method.md` 为事实边界。
3. 将 C1–C3 冻结结果写入匿名主稿的实验与结果章节；C3 明确区分探索关联评测和外部 context challenge。
4. 基于冻结结果更新摘要结果句；将 C3 的主要证据表述为类型 grounding 改善和 recall/precision 权衡，不宣称二元增益显著。
5. 完成相关工作引用与复现环境说明；不得把 shadow-mode 风险感知写成端到端安全提升。
