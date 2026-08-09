# 保留 VLM 状态名称设计

## 问题

节点第一次被观察时，本地语义草稿会先给出一个兜底名称。随后 VLM 可以把它升级为更可读的状态名称。

同一节点再次被访问时，系统会再次生成本地语义草稿。当前 `WebKobeGraphManager.identify_or_add_node()` 总是优先采用新传入的 `node_label`、`state_summary` 和 `naming_provenance`，因此本地兜底名称会覆盖已经保存的 VLM 名称。

上轮实验也符合这个模式：多次访问的节点最终显示为 `deterministic_fallback`，最后一个未再次更新的节点保留了 `visual_affordance_vlm`。

## 本次方案

在节点合并时，把三个命名字段作为一组，并根据 `naming_provenance.source` 决定优先级：

1. 现有节点已经由 `visual_affordance_vlm` 命名时，保留现有的 `node_label`、`state_summary` 和 `naming_provenance`。
2. 现有节点只有本地兜底名称，而新数据来自 `visual_affordance_vlm` 时，允许 VLM 名称覆盖兜底名称。
3. 两边都不是 VLM 名称时，保持当前合并行为，避免改变其他旧流程。
4. 两边都是 VLM 名称时，保留最早接受的名称，避免 revisit 导致名称漂移。

简单说，优先级是：已经接受的最早 VLM 名称 > 本地兜底名称 > 节点 ID。

## 影响范围

只调整 graph manager 合并节点时的：

- `node_label`
- `state_summary`
- `naming_provenance`

不改变节点 ID、节点匹配、embedding、业务动作生成、动作选择、边记录或 PDDL 投影。

## 测试

在 graph manager 单元测试中覆盖：

- 本地兜底名称可以被 VLM 名称升级。
- 已有 VLM 名称不会被后续本地草稿覆盖。
- 后续不同的 VLM 名称不会替换最早接受的 VLM 名称。
- 普通非 VLM 合并行为保持不变。

## 副作用

如果第一次接受的 VLM 名称不够理想，本轮探索不会自动改名。这符合当前“统一保留最早名称”的约定。未来如有需要，可以单独增加离线重命名，不放进本次修改。

## 未来优化（本次不做）

把“查找/匹配节点”和“更新节点内容”拆开：先判断当前观察是否命中旧节点，再决定哪些字段可以写入。这样本地临时草稿不会在匹配阶段直接修改 graph。

这会影响 explorer 与 graph manager 的调用边界，改动和回归范围更大，因此等简单闭环稳定后再做。
