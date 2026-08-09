# Graph 节点 Embedding 完整覆盖设计

## 问题

当前探索只在动作完成后为 target 节点记录 state embedding。初始节点没有前一条动作，因此从未成为 target，也不会进入 embedding memory。页面以后恢复到初始状态时，target matching 无法选择一个没有 embedding 记录的节点，只能创建重复节点。

本轮实验已经验证该现象：初始 `shopping` 节点不在 `state_embeddings.json` 中；清空搜索后，matcher 只能命中刚离开的 source 并被 source 保护拒绝，随后创建了重复的普通商品列表节点。

## 目标

保持一个简单约束：

> 每个正式加入当前 graph 的节点，都应在本次探索的 state embedding memory 中拥有一条记录。

## 设计

节点第一次成为当前 source 时，使用当下已经取得的 snapshot 和 interactables 检查 embedding memory：

- 已有该 `node_id` 的记录：不重复调用 embedding API。
- 没有记录：构建现有 state summary，生成并保存 embedding。
- 未启用 exploration memory 或没有 embedding provider：保持现有行为。
- embedding 调用失败：沿用当前 runner 的失败边界，不伪造记录。

复用现有 embedding 生成和替换逻辑，把 `_record_target_embedding` 收束为可以记录任意 graph 节点的通用内部方法。target 节点仍在动作后记录；初始节点和其他特殊 source 通过首次 source 检查补齐。

第一版不因同一节点的观察内容变化自动重算 embedding。它只保证存在性，避免额外 API 调用和摘要漂移。

## 不改变的部分

- 不调整 embedding 相似度阈值。
- 不修改 source-node 保护和 target matching 接受规则。
- 不新增 graph、node、edge 或 PDDL 字段。
- embedding 不参与 node identity。
- 不改变 forward-only 探索和终止条件。

## 验收

- 初始节点在第一次执行动作前已经拥有 embedding 记录。
- 已有 embedding 的 source revisit 不会再次调用 provider。
- 动作后的新 target 节点仍会记录 embedding。
- 未启用 embedding 时不发生额外调用。
- 实验写出时，启用 state embeddings 的正常路径中，graph node IDs 都能在 embedding records 中找到。
- 使用与本轮相同的搜索、清空流程复测时，恢复后的普通列表能够匹配回初始节点，不再创建重复节点。
