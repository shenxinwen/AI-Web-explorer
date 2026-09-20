# 实验设置

## 实验问题

### RQ1：Evidence-Grounded Knowledge Admission

在给定相同候选功能、执行前冻结的 expected outcomes 和冻结交互轨迹时，相比将候选发现或 executor-reported success 直接视为事实，基于动作前后证据的 functional outcome 验证能否提高准入知识准确性，同时保留已获得支持的有效功能知识？

### RQ2：Execution-Grounded Model Induction

在相同 Web 应用、探索起点和普通候选动作预算下，执行驱动探索能否持续产生支持或否定功能假设的交互证据，并在证据准入约束下保留有用的功能发现能力？依赖感知选择以及 persistent frontier/replay 对跨位置未完成假设的恢复、增量覆盖和额外 GUI 成本分别有什么影响？

### RQ3：Environmental Risk Awareness

风险感知模块能否根据执行前 GUI observation 和动作语义，准确识别自动探索生成的已选交互在当前上下文中可能带来的环境风险，并给出有界面证据支持的风险分类？

### Overall Claim：Reliability and Risk Awareness without Abandoning Exploration

C1–C3 的综合证据用于检验：VERA 能否提高功能知识准入的可靠性、使自主探索动作的潜在环境风险可感知和可追溯，同时在固定预算下仍保留有用的功能发现能力。当前 shadow-mode 风险判断不改变执行，因此该综合 claim 不等同于端到端安全性提升，也不检验风险控制与覆盖率之间的执行策略权衡。

### Auxiliary Evaluation：Downstream Planning and Behavior Verification

经过保守投影的功能模型能否支持新目标下的路径规划，并减少规划或验证过程中使用未经证据支持的功能知识？该实验用于评价 C1 与 C2 产物的外部效用，不作为独立贡献或替代 C2 的过程评测。

## 任务与数据

- 主实验使用已有运行经验的 SauceDemo 与 Practice Shopping，从入口 URL 和干净浏览器会话开始。
- RQ1 使用两站点正式运行产生的全部自然探索轨迹；旧调试运行和为增加困难样本而构造的数据不混入主统计，也不预设必须达到 200–300 条 attempts。
- Pilot 为每网站、每条件 1 次、最多 10 个 action attempts；正式实验为每网站、每条件 3 次、每次最多 25 个 attempts。
- RQ1 以每次运行内去重后的功能知识为统计对象，action attempt 只作为验证证据来源；RQ3 使用两条互补证据轨道：106 条 C2 Full 普通探索动作，以及 100 条外部 screenshot-action context 样本；RQ2 以独立 run 为单位。
- AI 生成初始标注，人工逐项审查并修订；正式标注前先用 20 个样本检查字段和规则是否可执行。该流程不等同于双人独立标注。
- 完整冻结协议见 [`experiments/protocol_v1.md`](experiments/protocol_v1.md)。
- 逐字段定义与论文级 verification state 的离线派生规则见 [`experiments/annotation_guide_v1.md`](experiments/annotation_guide_v1.md)；工件核查见 [`experiments/pilot_readiness_audit.md`](experiments/pilot_readiness_audit.md)。
- 下游任务包括：给定新目标或 PDDL problem 的规划，以及规划动作与模型约束/观察结果的一致性验证。
- 若资源允许，可加入规划结果驱动真实浏览器执行，但不作为当前必要贡献。

## 对比方法

- 直接采用 VLM 提议、缺少真实 outcome verification 的模型。
- C1：在同一组冻结候选和轨迹上比较 proposal-as-fact、executor-success-as-fact 与 evidence-grounded admission；外部方法不作为 C1 主实验的硬性数值基线。
- C2：Random、Linear 与 Full。Random 不检查依赖且不 replay；Linear 检查已观察依赖并确定性选择，但不返回旧位置；Full 仅在 Linear 上增加 persistent frontier 与 replay。该内部比较用于隔离证据生产机制，并评估可靠知识归纳是否保留有用覆盖；不以复现或击败外部探索器作为主实验成立条件。
- C3 探索关联评测保留 Action only、Action + taxonomy、Action + visual 和 Full 四条件诊断；外部主比较固定为 Text-only（动作 label + taxonomy）与 Context-conditioned（截图 + 动作 label + taxonomy）。Taxonomy 在外部主比较中是共享的形式化表达词汇，不作为独立消融变量。
- SeerGuard、OS-Sentinel、OSGuard 和 WebGuard 用于相关工作、协议参照或外部样本来源，不作为直接数值 baseline；它们的任务条件、动作空间和标签语义与 C3 不同。

## 指标与统计规则

### 功能模型质量

- admitted knowledge precision：准入知识中由人工确认真实存在且核心功能结果得到 before/after evidence 支持的比例；
- supported knowledge retention：人工确认获得支持的候选知识中被当前准入策略保留的比例；
- admission yield：全部有效候选中被准入的比例；
- functional outcome verification accuracy 或 macro-F1：系统 outcome judgment 与人工标签的一致性；
- executor–outcome disagreement rate、证据链完整率和无效样本率作为诊断统计。

RQ1 不使用候选功能准确率或 supported core-function recall 作为主指标，避免把 C2 的候选发现能力混入知识准入效果。Knowledge precision 与 unsupported admission rate 互为补数，不作为两个独立主指标重复报告。

RQ1 中一条功能知识由 `site + semantic_location + canonical_action_id` 标识；同一运行中的重复 attempts 合并为一条功能。每次运行独立计算指标，再报告每个网站 3 次运行的平均值和跨网站 macro-average。

### 执行驱动归纳

- 功能覆盖率：获得交互证据支持并匹配冻结功能清单的功能数 / 清单总数，是唯一主指标，同时报告 `x/n` 与百分比；
- 覆盖增长曲线：随普通候选动作 attempts 变化的功能覆盖率；
- 有效尝试率：带来新增已支持功能的普通候选 attempt 比例；
- replay 成本与贡献：额外 replay GUI 动作数及 replay 后新增覆盖功能数。

失败、无变化、证据不完整、依赖违规、重复尝试、停止原因和未完成候选恢复情况仅作诊断。Replay 动作不占普通候选动作预算，但必须单独限额并报告；因此 Full 的覆盖提升不自动等同于总 GUI 动作效率提升。

### 风险与副作用

- 风险识别 precision、recall 和 F1；
- 在风险样本上的 acceptable risk-type accuracy；复合风险允许人工 gold 给出多个可接受类型，模型仍输出一个主要类型；
- 风险判断证据与 GUI 上下文的一致性；
- 相似动作在不同页面上下文中的判断差异；
- 误报、漏报和错误分类案例。

### 下游效用

- 给定目标的规划成功率与路径可执行性；
- 规划/验证中使用未经证据支持知识的频率；
- 规划动作与位置约束、直接动作依赖、观察结果的一致性。

### 统计规则

探索运行正式实验每条件运行 3 次并报告逐网站结果和网站 macro-average；C3 外部样本以 context pair 为 cluster、非配对样本为 singleton，进行 10,000 次 cluster bootstrap。当前采用 AI 初标加人工逐项审查，以人工审核后的标签作为 gold；该流程不是双人独立标注，因此不报告 Cohen's kappa。置信区间跨 0 的差异只报告为点估计方向，不宣称统计显著。

## 消融与稳健性检查

核心消融：

1. w/o evidence-based outcome verification（主要对应 C1）；
2. w/o persistent frontier（主要对应 C2）；
3. C3 的 Text-only / Context-conditioned 比较，用于隔离执行前视觉上下文的贡献；taxonomy 作为共享输出词汇，不再承担单独的外部消融主张。

待考虑的稳健性检查：

- 不同 VLM 或候选生成提示；
- 不同执行预算与网站动态性；
- executor failure 与环境不支持的混淆；
- verification threshold 对覆盖率和可靠性的影响；
- 风险类别定义和判断阈值对识别结果的影响。

当前不以真实确认、拦截或危险行为减少作为必要实验结论。

“减少错误尝试”和“减少重复探索”只在相应指标与实验结果支持后报告。

详细实验登记见 `experiments/registry.md`。
