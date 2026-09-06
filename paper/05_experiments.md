# 实验设置

## 实验问题

### RQ1：Functional Model Quality

在给定相同候选功能和交互证据时，evidence-grounded functional model 是否比直接采用 VLM 提议或 executor success 具有更可靠的功能、结果与直接动作依赖知识？

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
- 全部样本单人标注，至少 25% 双人独立复标并仲裁；正式标注前试标 20 个样本。
- 完整冻结协议见 [`experiments/protocol_v1.md`](experiments/protocol_v1.md)。
- 逐字段定义与论文级 verification state 的离线派生规则见 [`experiments/annotation_guide_v1.md`](experiments/annotation_guide_v1.md)；工件核查见 [`experiments/pilot_readiness_audit.md`](experiments/pilot_readiness_audit.md)。
- 下游任务包括：给定新目标或 PDDL problem 的规划，以及规划动作与模型约束/观察结果的一致性验证。
- 若资源允许，可加入规划结果驱动真实浏览器执行，但不作为当前必要贡献。

## 对比方法

- 直接采用 VLM 提议、缺少真实 outcome verification 的模型。
- C1：executor-success-as-fact、w/o outcome verification，以及 GUI-explorer 风格的 transition knowledge；VeriGUI 用于 outcome-verification 定位比较。
- C2：linear/no replay 与完整 persistent-frontier 方法；UIExplore-AlGo、GUI-explorer 作为非阻塞追加对照。
- C3：通用 VLM zero-shot、OS-Sentinel/SeerGuard 类执行前判断，以及完整方法的输入消融；OSGuard 可作为补充外部数据，但需处理其依赖用户指令的标签差异。
- 完整方法与三项核心消融。
- 完整方法：截图 + 动作 label + 风险库。
- w/o visual context：动作 label + 风险库。
- w/o taxonomy：截图 + 动作 label。

## 指标与统计规则

### 功能模型质量

- 功能结论准确性；
- functional outcome 判断准确性；
- observed direct action dependency 准确性；
- 未经证据支持知识的错误准入率；
- 证据可追溯性/证据链完整率；
- 有效功能模型覆盖率。

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

正式实验每条件运行 3 次，报告逐网站结果和网站 macro-average；主要比例指标报告 bootstrap 95% confidence interval。二元人工标签报告 Cohen's kappa。小样本不强制显著性检验，不得仅报告最优运行。

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
