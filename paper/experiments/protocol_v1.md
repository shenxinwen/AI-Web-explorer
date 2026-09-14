# 最小可投稿实验协议 v1

> 冻结日期：2026-09-06
>
> 目标：以最小但完整的受控实验支持 C1–C3。Pilot 只验证协议和指标可执行，不作为论文结果；除非 pilot 暴露无法计算的指标，否则正式实验不再扩展方法或网站范围。

## 1. 实验对象与公共设置

- Web 应用：SauceDemo（`https://www.saucedemo.com/`）和 Practice Shopping（`https://practiceautomatedtesting.com/shopping`）。二者均已有项目运行经验。
- 起点：每次从对应入口 URL 和干净会话开始；SauceDemo 使用公开测试账号。
- 模型与 prompt：正式运行前记录 provider、精确模型名、日期、temperature 和 prompt/taxonomy 版本；同一 RQ 的各条件保持一致。
- 本文件冻结实验设计；精确模型版本、运行命令和环境快照在 pilot 前另存为冻结运行配置。
- 正式探索预算：每个网站、每个条件、每次运行最多 25 个已选 high-level action attempts；每个条件运行 3 次。
- Pilot 预算：每个网站、每个条件 1 次、最多 10 个 attempts。
- 重置：每次运行使用新浏览器上下文；能够重置的站点状态在运行前恢复。无法保证的动态变化写入异常日志。
- 统计单位：RQ1 以单次运行内去重后的功能知识为评价对象，action attempt 只提供验证证据；RQ3 以 action attempt 为基本单位；RQ2 以独立 run 为基本单位。

## 2. RQ1 / C1：功能结果验证与知识准入

### 数据

使用 SauceDemo 与 Practice Shopping 的完整方法正式运行得到的全部自然冻结轨迹。旧调试运行和人为补充的困难样本不混入主统计，也不为达到预设 attempt 数量而选择性抽样。每个候选在执行前同时生成并冻结一句可观察的 `expected_outcome`。每个样本包含候选功能、expected outcome、executor-reported status、before/after observation、系统 outcome judgment 和 evidence reference。RQ1 明确区分候选发现、交互执行完成和获得可观察结果支持的功能知识。

一条功能知识在单次运行内由 `site + semantic_location + canonical_action_id` 唯一标识。同一功能的多个 attempts 合并，不能作为多条知识重复计数；不同运行保持为独立重复。

### 对比

1. **Proposal-as-fact：** 所有 VLM 候选直接作为有效功能知识。
2. **Executor-success-as-fact：** executor 报告完成即作为成功功能知识。
3. **Evidence-grounded admission：** 仅当 `evidence_complete=true` 且系统 `predicted_outcome=success` 时准入知识。

三种条件消费完全相同的候选和冻结轨迹，隔离知识判定方式；不把重新探索产生的差异混入 RQ1。

同一功能存在多次 attempts 时，三种策略按“是否获得过相应支持”聚合：proposal-as-fact 在功能被提出后即准入；executor-success-as-fact 在至少一次 attempt 报告执行成功后准入；evidence-grounded admission 在至少一次 evidence-complete attempt 被系统判定 outcome success 后准入。

### 人工标注

每个有效 action attempt 的人工判断聚焦于：候选功能是否真实存在，以及 before/after evidence 是否足以支持该功能的核心语义结果。证据必须与所选动作相关，并足以区分功能结果与任意页面变化；页面或 URL 发生变化本身不是成功证据。执行前冻结的 `expected_outcome` 用作验证锚点以限制事后解释，但不要求证据逐字满足其中过窄或无关的展示细节。人工 gold 中，`function_exists=yes` 且 `functional_outcome=success` 定义为 supported knowledge。

Executor-reported status、系统 outcome judgment 和三种准入结果在 AI 初标及人工审核 C1 gold 时隐藏，完成 gold 后再从运行记录合并；证据工件完整性直接从运行记录读取。缺少必要运行工件、无法形成结果判断的样本作为无效样本单独报告。expected outcome 本身模糊、错误、过窄或不可观察时不删除样本，也不事后改写；在 `notes` 中记录并进入错误分析。

功能级 gold 由其 attempts 聚合：至少一次有效 attempt 同时满足 `function_exists=yes` 与 `functional_outcome=success`，该功能即视为 supported knowledge；若同一功能的存在性标签互相冲突，必须人工复核后再计算。

### 主要指标与诊断

- **Admitted knowledge precision：** 准入知识中属于人工 supported knowledge 的比例，是 C1 的核心指标；
- **Supported knowledge retention：** 全部人工 supported knowledge 中被该策略准入的比例；
- **Admission yield：** 全部有效候选中被该策略准入的比例。

另报告 functional outcome verification accuracy 或 macro-F1、executor–outcome disagreement rate、evidence-chain completeness、无效样本率和 expected-outcome 质量错误分析。Admission F1 仅作为可选汇总，不取代 precision、retention 和 yield 三项有独立解释的主指标。Knowledge precision 与 unsupported admission rate 互为补数，只选择前者作为主表指标。候选功能准确率、core-function recall 和 dependency accuracy 不作为 RQ1 主指标；它们分别属于候选发现、端到端覆盖或其他模型内容。

RQ1 首先只评估自然探索轨迹。受控挑战集暂不构建；仅在自然负样本不足以解释准入行为时，作为后续独立数据集考虑，且不得与自然样本混合统计。

## 3. RQ2 / C2：执行驱动持续归纳

### 对比

1. **Random：** 在当前位置的未完成高层候选中按冻结 seed 随机选择，不检查动作依赖，不 replay；保留与其他条件相同的候选生命周期记录。
2. **Linear / no replay：** 检查动作依赖并按现有确定性顺序选择；离开当前位置后不恢复未完成候选。
3. **Full method：** 与 Linear 完全相同，唯一增加 persistent frontier 与 replay 恢复。

不在主实验中强行复现 UIExplore-AlGo、GUI-explorer 等异构系统；它们使用不同环境、动作空间或移动 GUI。若 UIExplore-Bench 能在不修改核心方法的条件下接入，则仅作为追加实验。

### 主要指标

- 功能覆盖率（主指标，报告 x/n 与百分比）；
- 覆盖增长曲线：横轴为累计普通候选 attempts，纵轴为功能覆盖率；
- 有效尝试率：首次带来一个清单内 supported function 的普通候选 attempts / 全部普通候选 attempts；
- replay 成本与贡献：额外 replay GUI 动作数，以及成功恢复后首次新增覆盖的清单内功能数。

普通候选 attempt 的 pilot/formal 上限分别为 10/25。Replay GUI 动作不占候选 attempt 预算，但单独限制并报告；同时报告 total GUI actions 与 cost-aware efficiency。绘制随普通 candidate attempt 变化的 supported-knowledge growth curve。失败、无变化、证据不完整、依赖违规、重复、停止原因和 replay-mediated gains 均作诊断指标。

## 4. RQ3 / C3：已选动作风险识别

### 数据

从 RQ2 的普通探索和 replay 中提取执行前样本，每个样本只包含当时可用的 screenshot、selected high-level action label、taxonomy version 和风险输出。若自然轨迹中的风险正例不足 30 个，补充人工构造的 screenshot-action context pairs；补充样本只用于离线风险识别，不执行对应危险动作。

目标数据规模至少 100 个样本，其中尽量包含不少于 30 个风险正例，并分别报告自然探索样本与补充样本结果。

### 对比

1. **Action only：** action label，不提供截图或 taxonomy。
2. **Without visual context：** action label + taxonomy。
3. **Without taxonomy：** screenshot + action label。
4. **Full：** screenshot + action label + taxonomy。

SeerGuard、OS-Sentinel 和 OSGuard 用于相关工作及协议参照，不作为 v1 必须复现的数值 baseline，因为它们依赖用户指令、移动环境或不同标签空间。

### 人工标注与指标

标注 `potential_risk`、一个主要 `risk_type` 和 evidence 是否能在截图中得到支持。主要指标为 risk precision、recall、F1 和 risk-positive 样本上的 type accuracy；evidence grounding agreement、普通探索/replay logging coverage 和失败案例作为补充。

## 5. 标注与统计

- 使用 `annotation_guide_v1.md` 并在正式标注前试标 20 个样本。
- AI 生成第一次标注，人工审查全部样本并作最终修订；AI 初标不作为独立人工标注者，当前不报告 Cohen's kappa。
- 系统预测相对人工 gold 的多类 outcome/risk type 表现报告 macro-F1 或一致率。
- 报告每个网站和总体结果；总体值按网站 macro-average。
- RQ1 先对每次独立运行计算指标，再对同一网站的 3 次运行取平均；不把不同运行中数量不等的功能直接混成一个样本池。
- 对主要比例指标报告 bootstrap 95% confidence interval；小样本不强制显著性检验。
- 失败分析至少区分：候选幻觉、executor/outcome 混淆、视觉变化不足、dependency 误判、风险误报、风险漏报和风险类型错误。

## 6. 辅助下游实验

只选择每个网站 3–5 个目标，比较完整模型与 proposal-as-fact 模型生成的路径是否使用未获证据支持的知识，以及路径是否符合位置约束和观察到的直接依赖。不要求建立通用规划系统，也不作为核心 claim 的必要条件。

## 7. Pilot 通过条件

Pilot 通过需同时满足：

1. 两个网站均能产生可解析的 action、执行前冻结的 expected outcome、executor-reported status、before/after observation、outcome judgment、证据完整性检查所需字段和 risk record；
2. RQ1 三种准入条件能从同一轨迹离线计算；
3. no-replay 与 full 条件能够被明确配置或从运行行为中区分；
4. AI 初标与人工审查流程能完成 20 个样本，且主要标签没有系统性歧义；
5. 所有主要指标都能由保存工件计算。

Pilot 若未通过，只修复协议、日志或标注阻塞项；不新增论文贡献或扩展框架功能。
