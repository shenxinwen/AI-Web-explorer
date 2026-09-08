# 实验设置

## 实验问题

### RQ1：Evidence-Grounded Knowledge Admission

在给定相同候选功能、执行前冻结的 expected outcomes 和冻结交互轨迹时，相比将候选发现或 executor-reported success 直接视为事实，基于动作前后证据的 functional outcome 验证能否提高准入知识准确性，同时保留已获得支持的有效功能知识？

### RQ2：Execution-Grounded Model Induction

在相同 Web 应用、探索起点和交互预算下，执行驱动的探索循环与 persistent frontier 是否能够获得更多经交互支持的功能知识，并正确保留和恢复未完成假设？

### RQ3：Risk-Aware Exploration

风险感知模块能否准确识别自动探索生成的已选动作可能带来的风险，并给出有 GUI 上下文证据支持的风险分类？

### Auxiliary Evaluation：Downstream Planning and Behavior Verification

经过保守投影的功能模型能否支持新目标下的路径规划，并减少规划或验证过程中使用未经证据支持的功能知识？该实验用于评价 C1 与 C2 产物的外部效用，不作为独立贡献或替代 C2 的过程评测。

## 任务与数据

- 主实验使用已有运行经验的 SauceDemo 与 Practice Shopping，从入口 URL 和干净浏览器会话开始。
- Pilot 为每网站、每条件 1 次、最多 10 个 action attempts；正式实验为每网站、每条件 3 次、每次最多 25 个 attempts。
- RQ1/RQ3 以 action attempt 为单位，RQ2 以独立 run 为单位。
- AI 生成初始标注，人工逐项审查并修订；正式标注前先用 20 个样本检查字段和规则是否可执行。该流程不等同于双人独立标注。
- 完整冻结协议见 [`experiments/protocol_v1.md`](experiments/protocol_v1.md)。
- 逐字段定义与论文级 verification state 的离线派生规则见 [`experiments/annotation_guide_v1.md`](experiments/annotation_guide_v1.md)；工件核查见 [`experiments/pilot_readiness_audit.md`](experiments/pilot_readiness_audit.md)。
- 下游任务包括：给定新目标或 PDDL problem 的规划，以及规划动作与模型约束/观察结果的一致性验证。
- 若资源允许，可加入规划结果驱动真实浏览器执行，但不作为当前必要贡献。

## 对比方法

- 直接采用 VLM 提议、缺少真实 outcome verification 的模型。
- C1：在同一组冻结候选和轨迹上比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission；外部方法不作为 C1 主实验的硬性数值基线。
- C2：linear/no replay 与完整 persistent-frontier 方法；UIExplore-AlGo、GUI-explorer 作为非阻塞追加对照。
- C3：通用 VLM zero-shot、OS-Sentinel/SeerGuard 类执行前判断，以及完整方法的输入消融；OSGuard 可作为补充外部数据，但需处理其依赖用户指令的标签差异。
- 完整方法与三项核心消融。
- 完整方法：截图 + 动作 label + 风险库。
- w/o visual context：动作 label + 风险库。
- w/o taxonomy：截图 + 动作 label。

## 指标与统计规则

### 功能模型质量

- admitted knowledge precision：准入知识中由人工确认真实存在且 functional outcome 成功的比例；
- supported knowledge retention：人工确认获得支持的候选知识中被当前准入策略保留的比例；
- admission yield：全部有效候选中被准入的比例；
- functional outcome verification accuracy 或 macro-F1：系统 outcome judgment 与人工标签的一致性；
- executor–outcome disagreement rate、证据链完整率和无效样本率作为诊断统计。

RQ1 不使用候选功能准确率或 supported core-function recall 作为主指标，避免把 C2 的候选发现能力混入知识准入效果。Knowledge precision 与 unsupported admission rate 互为补数，不作为两个独立主指标重复报告。

### 执行驱动归纳

- 固定预算下 interaction-supported function coverage；
- 随交互预算变化的知识增长曲线；
- 单位交互获得的有效证据数；
- 未完成假设的保留、重访与完成率。

### 风险与副作用

- 风险识别 precision、recall 和 F1；
- 在风险样本上的 risk type 准确率；
- 风险判断证据与 GUI 上下文的一致性；
- 相似动作在不同页面上下文中的判断差异；
- 误报、漏报和错误分类案例。

### 下游效用

- 给定目标的规划成功率与路径可执行性；
- 规划/验证中使用未经证据支持知识的频率；
- 规划动作与位置约束、直接动作依赖、观察结果的一致性。

### 统计规则

正式实验每条件运行 3 次，报告逐网站结果和网站 macro-average；主要比例指标报告 bootstrap 95% confidence interval。当前采用 AI 初标加人工审查，不报告 Cohen's kappa；小样本不强制显著性检验，不得仅报告最优运行。

## 消融与稳健性检查

核心消融：

1. w/o evidence-based outcome verification（主要对应 C1）；
2. w/o persistent frontier（主要对应 C2）；
3. w/o visual context / w/o taxonomy risk detection。

待考虑的稳健性检查：

- 不同 VLM 或候选生成提示；
- 不同执行预算与网站动态性；
- executor failure 与环境不支持的混淆；
- verification threshold 对覆盖率和可靠性的影响；
- 风险类别定义和判断阈值对识别结果的影响。

当前不以真实确认、拦截或危险行为减少作为必要实验结论。

“减少错误尝试”和“减少重复探索”只在相应指标与实验结果支持后报告。

详细实验登记见 `experiments/registry.md`。
