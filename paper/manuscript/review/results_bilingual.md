# VERA Results: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX draft; the Chinese text is a semantic translation for author review. All numbers come from the frozen C1--C3 final reports.
>
> **Snapshot notice:** This file preserves the pre-compression review version and will be regenerated after the revised English structure is approved.

## Knowledge Admission Reliability / 知识准入可靠性

**English**

**Outcome evidence provides the most reliable admission boundary in our controlled comparison.** Admitting every proposal yields 73.33% precision, and requiring executor-reported success raises precision to 82.50%. Evidence-grounded admission reaches 96.97% precision while retaining 96.97% of the claims supported by human review. It admits 33 of the 45 candidates: 32 are human-supported, compared with all 33 supported claims admitted by each weaker rule.

| Admission rule | Admitted | Precision | Supported retention |
| --- | ---: | ---: | ---: |
| Proposal as fact | 45 | 73.33% | 100.00% |
| Executor success as fact | 40 | 82.50% | 100.00% |
| Evidence grounded | 33 | **96.97%** | 96.97% |

**中文**

**在受控比较中，结果证据提供了最可靠的知识准入边界。** 准入全部候选时 precision 为 73.33%；要求执行器报告成功后，precision 提高到 82.50%。基于证据的准入达到 96.97% precision，同时保留了 96.97% 的人工支持主张。它在 45 条候选中准入 33 条，其中 32 条得到人工支持；相比之下，两种较弱规则都准入了全部 33 条人工支持主张。

**English**

The comparison isolates admission rather than discovery: all rules receive the same candidates and interaction traces. The result therefore shows why neither proposal nor executor status is an adequate functional truth label. The evidence rule removes most unsupported candidates without turning incomplete or failed attempts into negative claims about the function. Its remaining errors are local rather than systematic: one claim was admitted without direct evidence that all required fields had been completed, and one visibly supported sorting function was missed. Thus, evidence grounding substantially improves admitted-knowledge precision on this frozen set, but does not make verification infallible.

**中文**

该比较隔离的是准入规则而不是发现过程：所有规则接收相同的候选和交互轨迹。因此，结果说明候选提出和执行器状态都不足以充当功能事实标签。证据规则去除了大部分未获支持的候选，同时没有把证据不完整或执行失败自动视为反对该功能的负面结论。剩余错误是局部的：一条主张在缺少“所有必填字段均已完成”的直接证据时被错误准入，另一个具有可见排序变化的功能则被遗漏。因此，在该冻结数据集上，证据 grounding 大幅提高了准入知识的 precision，但验证仍不是绝对无误的。

## Evidence-Supported Functional Coverage / 证据支持的功能覆盖

**English**

**Persisting unresolved verification opportunities increases supported functional coverage under the ordinary-attempt budget.** Full obtains a website macro-average of 54.5%, compared with 42.6% for Linear and 28.8% for Random. The central controlled comparison is Full versus Linear: adding the persistent frontier and replay corresponds to an 11.9 percentage-point gain while retaining the same candidate representation, dependency-aware selection, executor, and evidence admission rule.

| Policy | Practice Shopping | SauceDemo | Macro average |
| --- | ---: | ---: | ---: |
| Random | 33.3% | 24.2% | 28.8% |
| Linear | 45.8% | 39.4% | 42.6% |
| Full | **50.0%** | **59.1%** | **54.5%** |

**中文**

**在普通尝试预算下，持久保存未解决的验证机会提高了证据支持功能覆盖。** Full 的网站 macro-average 为 54.5%，Linear 为 42.6%，Random 为 28.8%。核心受控比较是 Full 与 Linear：在候选表达、依赖感知选择、执行器和证据准入规则相同的条件下，加入持久 frontier 和 replay 对应 11.9 个百分点的覆盖增益。

**English**

The gain is larger on SauceDemo, where leaving a location more often creates a need to restore prior context. Functions were first covered after replay in Practice Shopping Full run 2 (two functions after one replay GUI action) and in SauceDemo Full runs 2 and 3 (three functions in each run after 20 and 28 replay GUI actions, respectively). This pattern is consistent with replay recovering verification opportunities that Linear abandons after a location transition.

Replay is not free interaction. All three SauceDemo Full runs used replay and accumulated 76 replay GUI actions; these actions are outside the ordinary candidate-attempt budget and are reported separately. The result therefore supports persistent recovery as a mechanism for extending evidence-supported coverage, not a claim of greater total-interaction efficiency or general exploration optimality.

**中文**

该增益在 SauceDemo 上更大，因为离开某个位置后更经常需要恢复先前上下文。Practice Shopping Full run 2 有两个功能首次在一次 replay GUI 动作后得到覆盖；SauceDemo Full run 2 和 run 3 各有三个功能首次在 replay 后得到覆盖，对应 20 和 28 个 replay GUI 动作。这一模式与“replay 恢复 Linear 在位置转移后放弃的验证机会”相一致。

Replay 并不是免费的交互。SauceDemo 的三条 Full 运行都使用了 replay，累计产生 76 个 replay GUI 动作；这些动作不计入普通候选尝试预算，因此被单独报告。结果支持将持久恢复视为扩展证据支持覆盖的机制，但不支持总交互效率更高或一般探索最优性的主张。

## Context-Conditioned Risk Awareness / 上下文条件风险感知

**English**

**VERA produces pre-execution risk records for its exploration actions, and visual context most clearly improves the grounding of risk type.** On the 106 exploration-linked Full actions, the complete input condition obtains 86.5% pooled precision, 100.0% recall, and 92.8% F1. Its site-macro primary type accuracy is 85.0%. This establishes that the recording protocol operates on actions arising in the evaluated exploration workflow, although the action set contains only 32 risk-positive cases and covers a narrow subset of the risk taxonomy.

The external context-challenge comparison provides the stronger test of visual grounding. Adding the screenshot raises acceptable-type accuracy from 27.7% to 63.1%, a 35.4 percentage-point difference whose cluster-bootstrap 95% interval is [+21.7, +49.3] percentage points. Binary recall rises by 12.3 points and F1 by 5.2 points, while precision falls by 4.5 points.

| Input | Precision | Recall | F1 | Type accuracy |
| --- | ---: | ---: | ---: | ---: |
| Text only | 77.6% | 58.5% | 66.7% | 27.7% |
| Context conditioned | 73.0% | 70.8% | 71.9% | **63.1%** |
| Difference | -4.5 pp | +12.3 pp | +5.2 pp | +35.4 pp |

**中文**

**VERA 能够为探索动作生成执行前风险记录，而视觉上下文最明确地改善了风险类型 grounding。** 在 106 条探索关联 Full 动作上，完整输入条件的 pooled precision 为 86.5%、recall 为 100.0%、F1 为 92.8%；网站 macro primary type accuracy 为 85.0%。这说明风险记录协议能够作用于评测探索流程自然产生的动作，不过该集合只有 32 条风险正例，并且只覆盖风险分类体系中的较窄部分。

外部 context-challenge 提供了更强的视觉 grounding 检验。加入截图后，acceptable-type accuracy 从 27.7% 提高到 63.1%，增加 35.4 个百分点；cluster bootstrap 95% 区间为 [+21.7, +49.3] 个百分点。二元 recall 提高 12.3 个百分点，F1 提高 5.2 个百分点，而 precision 下降 4.5 个百分点。

**English**

The bootstrap intervals for binary recall and F1 differences cross zero, so their positive point estimates are not statistically resolved in this sample. The supported conclusion is consequently narrower: current visual context substantially improves expression of the relevant environmental consequence, while binary detection exhibits higher recall at lower precision. These external actions were supplied to the assessor and are not evidence that the VERA explorer would itself propose them.

**中文**

二元 recall 和 F1 差异的 bootstrap 区间跨越 0，因此其正向点估计在该样本上没有得到统计上的明确支持。可支持的结论相应更窄：当前视觉上下文明显改善了相关环境后果的类型表达，而二元检测体现为更高 recall、较低 precision 的权衡。这些外部动作是供应给判断器的，不能作为 VERA explorer 会主动提出它们的证据。

## Error Analysis / 错误分析

**English**

Across the studies, the remaining errors locate different breaks in the evidence-production chain. In C1, the false admission arose from insufficiently direct outcome evidence, whereas the missed supported claim arose despite a visible ordering change. These cases motivate retaining the evidence and judgment rather than collapsing the model to a binary list of functions.

In the external C3 set, context corrected 16 binary decisions but introduced 14 new binary errors. It recovered 14 positives while adding eight false alarms, often because the judge treated entry into a consequential workflow as if the immediate action completed the consequence. By contrast, context corrected 25 risk-type decisions and introduced only two new type errors. This asymmetry explains why consequence typing provides clearer evidence of contextual grounding than the binary metrics. The evaluated records describe potential risk before execution; because they do not alter actions, these results do not measure intervention effectiveness or harm reduction.

**中文**

不同实验中的剩余错误对应证据生产链上的不同断点。C1 的错误准入来自不够直接的结果证据，而被遗漏的 supported claim 实际具有可见的排序变化。这些案例说明模型应保留证据和判断，而不是压缩成一个二元功能列表。

在外部 C3 数据集中，上下文纠正了 16 个二元判断，同时引入了 14 个新的二元错误。它恢复了 14 个正例，但新增 8 个误报；常见原因是判断器把“进入后果敏感工作流”误认为当前动作已经完成了相应后果。相比之下，上下文纠正了 25 个风险类型判断，只引入 2 个新的类型错误。这种不对称解释了为什么后果类型表达比二元指标提供了更清楚的上下文 grounding 证据。本文评测的记录描述执行前潜在风险，并不改变动作，因此这些结果不衡量干预有效性或实际伤害降低。
