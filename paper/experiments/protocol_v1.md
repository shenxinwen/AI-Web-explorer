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
- 统计单位：RQ1/RQ3 以 action attempt 为基本单位；RQ2 以独立 run 为基本单位，避免把同一轨迹内动作误当作独立重复。

## 2. RQ1 / C1：功能知识质量

### 数据

使用完整方法正式运行得到的冻结轨迹。每个样本包含候选功能、执行器记录、before/after observation、outcome judgment、由冻结规则离线派生的 verification state 和 evidence reference。派生规则见 `annotation_guide_v1.md`，不要求为实验新增运行时状态字段。

### 对比

1. **Proposal-as-fact：** 所有 VLM 候选直接作为有效功能知识。
2. **Executor-success-as-fact：** executor 报告完成即作为成功功能知识。
3. **Evidence-grounded model：** 依据 outcome、verification state 和 evidence 准入知识。

三种条件消费完全相同的候选和冻结轨迹，隔离知识判定方式；不把重新探索产生的差异混入 RQ1。

### 人工标注

每个 action attempt 标注：功能是否在该位置真实存在、executor 是否完成动作、observable functional outcome（Success/Failure/Uncertain）、location transition、声明的直接依赖是否被该轨迹支持、现有 evidence 是否足以支持结论。

### 主要指标

- admitted functional knowledge precision；
- unsupported knowledge admission rate；
- outcome accuracy；
- evidence-chain completeness。

使用冻结的 `core_functions/*.csv` 和 `core_function_matching_v1.md` 计算 supported core-function recall。该指标只表示预先定义的核心功能覆盖率，不称为全站 recall。Dependency accuracy 作为次要指标。

## 3. RQ2 / C2：执行驱动持续归纳

### 对比

1. **Linear / no replay：** 离开当前位置后不通过 persistent frontier 恢复未完成候选。
2. **Full method：** 保留 persistent frontier，并通过 replay 恢复上下文后继续探索。

不在主实验中强行复现 UIExplore-AlGo、GUI-explorer 等异构系统；它们使用不同环境、动作空间或移动 GUI。若 UIExplore-Bench 能在不修改核心方法的条件下接入，则仅作为追加实验。

### 主要指标

- interaction-supported functions at budget；
- supported core-function recall at budget；
- supported functions / action attempts；
- unfinished-hypothesis revisit rate；
- revisited-hypothesis completion rate。

绘制随 attempt budget 变化的 supported-knowledge growth curve。重复探索率仅作描述性指标，不预设完整方法一定降低重复。

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
- 全部样本由一名标注者标注，至少 25% 由第二名标注者独立复标；分歧由讨论仲裁。
- 二元标签报告 Cohen's kappa；多类 outcome/risk type 报告 macro-F1 或一致率。
- 报告每个网站和总体结果；总体值按网站 macro-average。
- 对主要比例指标报告 bootstrap 95% confidence interval；小样本不强制显著性检验。
- 失败分析至少区分：候选幻觉、executor/outcome 混淆、视觉变化不足、dependency 误判、风险误报、风险漏报和风险类型错误。

## 6. 辅助下游实验

只选择每个网站 3–5 个目标，比较完整模型与 proposal-as-fact 模型生成的路径是否使用未获证据支持的知识，以及路径是否符合位置约束和观察到的直接依赖。不要求建立通用规划系统，也不作为核心 claim 的必要条件。

## 7. Pilot 通过条件

Pilot 通过需同时满足：

1. 两个网站均能产生可解析的 action、before/after observation、outcome、派生 verification state 所需实现字段和 risk record；
2. RQ1 三种准入条件能从同一轨迹离线计算；
3. no-replay 与 full 条件能够被明确配置或从运行行为中区分；
4. 两名标注者能使用指南完成 20 个样本，且主要标签没有系统性歧义；
5. 所有主要指标都能由保存工件计算。

Pilot 若未通过，只修复协议、日志或标注阻塞项；不新增论文贡献或扩展框架功能。
