# VERA Results: Bilingual Review Draft

> Review artifact only. The English text mirrors the current compressed LaTeX manuscript; the Chinese text is a semantic translation. All numbers come from frozen C1--C3 reports.

## Knowledge Admission Reliability / 知识准入可靠性

**English**

**Outcome evidence provides the most reliable admission boundary in our controlled comparison.** Admitting every proposal yields 73.33% precision; requiring executor-reported success raises it to 82.50%. Evidence-grounded admission reaches 96.97% precision while retaining 96.97% of human-supported claims. It admits 33 of 45 candidates, of which 32 are human-supported.

| Admission rule | Admitted | Precision | Supported retention |
| --- | ---: | ---: | ---: |
| Proposal as fact | 45 | 73.33% | 100.00% |
| Executor success as fact | 40 | 82.50% | 100.00% |
| Evidence grounded | 33 | **96.97%** | 96.97% |

All rules receive the same candidates and traces, isolating admission from discovery. The evidence rule removes most unsupported candidates without treating failed or incomplete attempts as negative functional claims. One claim was admitted without direct evidence that all required fields were completed, and one visibly supported sorting claim was missed. Evidence grounding therefore improves precision on this frozen set but remains fallible.

**中文**

**在受控比较中，结果证据提供了最可靠的知识准入边界。** 准入所有候选时 precision 为 73.33%；要求执行器报告成功后提高到 82.50%。基于证据的准入达到 96.97% precision，同时保留 96.97% 的人工支持主张。它在 45 条候选中准入 33 条，其中 32 条得到人工支持。

所有规则接收相同候选和轨迹，因此比较隔离了准入规则。证据规则移除了大多数未支持候选，同时没有把失败或不完整尝试当作反对功能的负面主张。一条主张在缺少所有必填字段均完成的直接证据时被错误准入，一条具有可见排序变化的主张则被遗漏。因此，证据 grounding 在该冻结集合上提高了 precision，但仍会出错。

## Evidence-Supported Functional Coverage / 证据支持的功能覆盖

**English**

**Persisting unresolved verification opportunities increases supported coverage under the ordinary-attempt budget.** Full obtains 54.5% website macro-average coverage, compared with 42.6% for Linear and 28.8% for Random. The central Full-versus-Linear comparison corresponds to an 11.9 percentage-point gain while holding representation, dependency-aware selection, executor, and admission fixed.

| Policy | Practice Shopping | SauceDemo | Macro average |
| --- | ---: | ---: | ---: |
| Random | 33.3% | 24.2% | 28.8% |
| Linear | 45.8% | 39.4% | 42.6% |
| Full | **50.0%** | **59.1%** | **54.5%** |

The gain is larger on SauceDemo, where restoring prior context is more often needed. Functions were first covered after replay in Practice Shopping Full run 2 and SauceDemo Full runs 2 and 3. All three SauceDemo Full runs used replay and accumulated 76 replay GUI actions outside the ordinary-attempt budget. The result supports persistent recovery as a coverage mechanism, not greater total-interaction efficiency or general exploration optimality.

**中文**

**在普通尝试预算下，持久保存未解决验证机会提高了证据支持覆盖。** Full 的网站 macro-average coverage 为 54.5%，Linear 为 42.6%，Random 为 28.8%。在保持候选表达、依赖感知选择、执行器和准入规则不变的情况下，Full 相对 Linear 对应 11.9 个百分点增益。

增益在 SauceDemo 上更大，因为它更经常需要恢复先前上下文。Practice Shopping Full run 2 以及 SauceDemo Full run 2 和 run 3 都有功能首次在 replay 后得到覆盖。SauceDemo 三条 Full 运行都使用了 replay，累计产生普通尝试预算之外的 76 个 replay GUI 动作。结果支持把持久恢复视为覆盖机制，但不说明总交互效率更高或通用探索更优。

## Context-Conditioned Risk Awareness / 上下文条件风险感知

**English**

**VERA produces pre-execution risk records for exploration actions, and visual context most clearly improves risk-type grounding.** On 106 exploration-linked Full actions, the complete condition obtains 86.5% pooled precision, 100.0% recall, and 92.8% F1; site-macro primary type accuracy is 85.0%. This establishes operation on workflow actions, although only 32 are risk-positive and the taxonomy coverage is narrow.

On the external set, screenshots raise acceptable-type accuracy from 27.7% to 63.1%, a 35.4-point difference with cluster-bootstrap 95% interval [+21.7, +49.3]. Recall rises 12.3 points and F1 5.2 points, while precision falls 4.5 points.

| Input | Precision | Recall | F1 | Type accuracy |
| --- | ---: | ---: | ---: | ---: |
| Text only | 77.6% | 58.5% | 66.7% | 27.7% |
| Context conditioned | 73.0% | 70.8% | 71.9% | **63.1%** |
| Difference | -4.5 pp | +12.3 pp | +5.2 pp | +35.4 pp |

Context corrected 16 binary decisions but introduced 14 new errors, often by treating entry into a consequential workflow as completion of its consequence. It corrected 25 type decisions while introducing only two new type errors. Binary recall and F1 intervals cross zero; the supported conclusion is therefore that context improves consequence expression while binary detection shows higher recall at lower precision. External actions were supplied rather than proposed by VERA, and the records do not measure intervention effectiveness.

**中文**

**VERA 能够为探索动作生成执行前风险记录，而视觉上下文最明确地改善风险类型 grounding。** 在 106 条探索关联 Full 动作上，完整条件得到 86.5% pooled precision、100.0% recall 和 92.8% F1；网站 macro primary type accuracy 为 85.0%。这说明协议能作用于真实工作流动作，但其中只有 32 条风险正例，taxonomy 覆盖范围较窄。

在外部集合上，加入截图使 acceptable-type accuracy 从 27.7% 提高到 63.1%，增加 35.4 个百分点，cluster-bootstrap 95% 区间为 [+21.7, +49.3]。Recall 提高 12.3 点，F1 提高 5.2 点，precision 下降 4.5 点。

上下文纠正了 16 个二元判断，同时引入 14 个新错误，常见原因是把进入重要工作流误认为已经完成相应后果。它纠正 25 个类型判断，只引入两个新的类型错误。二元 recall 和 F1 区间跨 0；因此可支持的结论是上下文改善后果表达，而二元检测表现为更高 recall、较低 precision。外部动作由实验提供而非 VERA 提出，风险记录也不衡量干预效果。
