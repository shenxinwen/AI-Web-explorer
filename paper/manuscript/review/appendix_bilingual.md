# VERA Appendix: Bilingual Review Draft

> Review artifact only. The English text mirrors the current LaTeX Appendix; the Chinese text is a semantic translation.

## Additional method and protocol details / 补充方法与协议细节

**English**

VERA assesses semantic browser actions submitted to the executor, not every atomic mouse or keyboard event used internally to realize them. Ordinary verification links one such action to a frozen claim and outcome evidence. Replay consists of previously observed semantic actions; every replay step receives its own risk record and is counted separately from ordinary candidate attempts. If risk inference fails, execution continues and the error is retained in the audit record. Formal RQ1/RQ2 runs use clean browser sessions, restored resettable state, three runs per application--condition pair, and at most 25 ordinary candidate attempts. Configurations record model settings, viewport, seeds, retry rules, stopping conditions, and replay limits.

**中文**

VERA 判断提交给执行器的语义浏览器动作，而不是执行器内部每个原子鼠标或键盘事件。普通验证把一个语义动作与冻结主张和结果证据关联。Replay 由先前观察到的语义动作组成；每个 replay 步骤分别生成风险记录，并与普通候选尝试分开计数。如果风险推理失败，执行继续，同时错误保留在审计记录中。正式 RQ1/RQ2 运行使用干净浏览器会话和恢复后的可重置状态；每个应用—条件组合运行三次，最多 25 个普通候选尝试。配置记录模型设置、viewport、seed、重试规则、停止条件和 replay 限额。

## Prompts, schemas, taxonomy, and annotation / 提示词、schema、分类体系与标注

**English**

The artifact package includes functional-claim and evidence schemas, versioned prompts, and `risk_taxonomy_v1.json`. Risk outputs contain binary `potential_risk`, one primary `risk_type` when applicable, and brief GUI-grounded evidence. The same taxonomy is shared across C3 conditions. Initial annotations were generated with AI assistance and then reviewed item by item by a human author under frozen guides; this is not independent double annotation. C1 gold is aggregated by application, location, and action identifier; C2 uses frozen function inventories and a reviewed mapping ledger; C3 permits multiple acceptable types for compound external cases.

External C3 intervals use 10,000 cluster-bootstrap samples, treating each candidate context pair as one cluster and each diversity case as a singleton (seed 20260920). Intervals crossing zero are reported as unresolved point-estimate directions.

**中文**

工件包包含功能主张与证据 schema、版本化提示词和 `risk_taxonomy_v1.json`。风险输出包含二元 `potential_risk`、适用时的一个主要 `risk_type`，以及简短 GUI grounding 证据。C3 各条件共享同一 taxonomy。初始标注由 AI 辅助生成，再由一名作者依据冻结指南逐项审查；这不是双人独立标注。C1 gold 按应用、位置和动作标识聚合；C2 使用冻结功能清单和人工审查映射账本；C3 允许外部复合样本具有多个可接受类型。

外部 C3 区间使用 10,000 次 cluster bootstrap，把每个候选上下文 pair 作为一个 cluster、每条 diversity 样本作为 singleton，seed 为 20260920。区间跨 0 的差异被报告为未明确的点估计方向。

## Result artifacts and cases / 结果工件与案例

**English**

Machine-readable metrics, reviewed gold, manifests, and complete reports are under `paper/experiments/results/E002--E004`, including failures, incomplete evidence, and negative examples. The C1 false admission concerns a form-completion claim without direct evidence that every required field was completed; the missed claim concerns sorting despite a visible ordering change. A recurring external C3 error treats entry into a consequential workflow as if the immediate action completed its downstream consequence, although context corrects substantially more type decisions than it introduces.

**中文**

机器可读指标、人工审查 gold、manifest 和完整报告位于 `paper/experiments/results/E002--E004`，其中保留执行失败、证据不完整和负例。C1 的错误准入涉及一条缺少“所有必填字段均完成”直接证据的表单完成主张；遗漏主张涉及已经出现可见顺序变化的排序功能。外部 C3 的常见错误是把进入重要工作流误认为当前动作已经完成下游后果，不过上下文纠正的类型判断明显多于其引入的类型错误。
