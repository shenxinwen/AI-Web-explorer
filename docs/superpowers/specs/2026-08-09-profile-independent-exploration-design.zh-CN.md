# 探索逻辑与 Business Profile 解耦设计

## 问题

当前 `WebKobeExplorer` 只有在同时配置 `business_profile` 和 Visual Affordance provider 时才生成业务动作候选。target embedding matching 也要求存在 `planning_transition`。

因此，不指定 profile 的通用网站探索即使已经配置截图 VLM 和 embedding，也会出现：

```text
不生成业务候选 -> 当前节点立即耗尽
没有 planning transition -> 不执行 target embedding matching
```

这与当前职责边界不一致。VLM 应根据当前可见页面提出动作；embedding memory 应根据页面状态匹配节点。两者都不应依赖 profile facts。

## 本次方案

### Visual Affordance

- `_record_source_business_affordances()` 只要求 Visual Affordance provider，不再要求 `business_profile`。
- `VisualAffordanceRequest` 删除没有进入提示词的 `profile` 和 `current_planning_facts` 字段。
- VLM prompt、候选上限、候选冻结、状态命名和解析行为保持不变。

### Target matching

- `_match_existing_target_node()` 不再因为 `planning_transition is None` 直接退出。
- 构建 target state summary 时，如果存在 planning transition，继续使用 `post_facts`；否则使用空 facts。
- embedding 阈值、context marker 检查、source node 保护和 known revisit evidence 门槛保持不变。

## 影响范围

修改：

- `src/ai_web_explorer/grounded_web/business_affordance.py`
- `src/ai_web_explorer/grounded_web/explorer.py`
- 对应测试

不修改：

- profile fact verifier
- `PlanningState` / `PlanningTransition` 数据结构
- Visual Delta
- graph schema
- source matching
- PDDL projector
- Stagehand 执行逻辑

## 测试

- 没有 business profile、但配置截图 VLM 时，节点仍能获得业务候选。
- 没有 planning transition 时，target embedding matching 仍会运行，并继续受 known revisit evidence 限制。
- 有 planning transition 时，target summary 仍包含其 `post_facts`。
- Visual Affordance prompt 继续不包含 profile facts 或 planning facts。
- 现有电商 profile 探索测试保持通过。

## 副作用

以前不指定 profile 的通用探索会立即停止；修改后会真正生成并执行可见业务候选。这是预期行为。

没有 profile 时不会产生结构化 planning facts，因此当前 Phase A domain 仍主要表达状态节点和业务转换，不会凭空增加 planner-facing facts。

## 本次不做

- 不调整 source 节点“先写入、后匹配”的顺序。
- 不修正 `visit_count` 语义。
- 不拆分 `WebKobeExplorer`。
- 不清理旧 BusinessTransition / PDDL 兼容路径。
- 不增加 embedding 缓存。

这些项目留在后续定期健康检查中逐项评估。
