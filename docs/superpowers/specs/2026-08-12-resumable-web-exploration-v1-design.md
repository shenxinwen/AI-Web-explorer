# Resumable Web Exploration V1 Design

## 1. 目标

把一次性的 `web-kobe-stagehand-explore` 运行改造成可中断、可恢复的探索任务。模型超时、额度不足、进程退出或人工暂停后，新运行复用已经保存的 Raw Graph，从入口重放回最近可信且可重放的断点，再继续新增探索，而不是从零生成候选并重复全部历史动作。

V1 的成功标准：

- 已有图可以无损加载为运行时探索内存；
- 新浏览器可以从入口恢复到一个稳定可达 frontier；
- 经用户显式授权的历史失败动作可以有限重试；
- 新执行尝试继续原子写入 checkpoint；
- 启动、重放或恢复失败不会破坏原始图；
- 无法恢复到原断点时明确 fallback 或停止，不伪造成功。

## 2. 核心语义

恢复不是浏览器会话恢复。旧浏览器进程、DOM 对象、Cookie 内存状态和页面句柄都不可信。每次恢复都创建新浏览器，并执行：

```text
load checkpoint graph
  -> validate graph and resume policy
  -> start a fresh browser at start URL
  -> reset and validate entry state
  -> choose a stable reachable resume target
  -> replay stored successful transitions
  -> validate arrival at the target node
  -> continue untried actions, or retry an explicitly authorized failed action
  -> checkpoint every newly completed attempt
```

`--steps N` 表示本次运行最多新增的业务动作尝试数，不包含历史 `total_steps_completed`，也不包含为了回到断点而执行的 replay 动作。

## 3. CLI 合约

```powershell
web-kobe-stagehand-explore `
  --url 'https://practiceautomatedtesting.com/shopping' `
  --resume-graph 'previous/graph.json' `
  --output 'resumed/graph.json' `
  --steps 6 `
  --resume-retry-action add_to_cart `
  --resume-action-max-attempts 2 `
  --frontier-replay
```

规则：

- `--resume-graph` 可选；未提供时保持当前全新探索行为。
- resume 模式自动启用 frontier replay，并在运行报告中记录；不要求用户重复传 `--frontier-replay`。
- `--resume-retry-action` 可重复提供。每个 action ID 只授权该 ID 在历史中最近一个失败或 outcome-unknown 的 `(source_node_id, action_id)` 实例，不会把所有节点上的同名动作全部解锁。默认不自动重试任何历史失败或 inflight 动作。
- `--resume-action-max-attempts` 是已获授权 action 的同一 `(source_node_id, canonical_action_id)` 全局最大尝试数，默认 `2`，必须大于等于 `2`。没有 retry action 时该参数不改变 eligibility。
- `--resume-graph` 与 `--output` 可以是同一路径。继续使用原子替换；首次新增 checkpoint 前的失败不会截断旧文件。
- 也允许不同路径。恢复输入始终只读；加载成功后先将基线图原子写入新输出，使新输出在尚未新增动作时也可加载。
- `--clean-output-dir` 与 `--resume-graph` 互斥。
- 模型、API、中转服务、本次步数和截图目录可以与历史运行不同。

CLI 解析恢复图后先把 action ID 解析成精确的 authorized attempt key 集合。找不到对应失败/inflight 实例、同一 action ID 出现无法按事件顺序消歧，或目标 source 不可稳定到达时，必须明确报错或跳过，不能扩大到其他同名动作。

显式 retry action 是对“精确重试一个历史动作”的本次人工授权，不会授权新动作或其他节点上的同名动作。若调用方使用带有最终购买等安全边界的 benchmark/profile，该边界仍优先，resume 参数不能绕过。

通用 `web-kobe-stagehand-explore` 当前没有完整的跨领域动作风险分类器，因此 V1 不宣称能自动判断任意 retry 是否安全。真实 retry 验收只在用户明确指定的受控测试网站和动作上进行；为通用探索补齐风险分类属于独立工作，不能靠动作名 denylist 假装解决。

## 4. 为什么失败动作不能默认重试

`failed_execution` 不等于“动作确定没有发生”。超时可能发生在远端已经点击之后、结果返回之前。盲目重试可能重复加购、提交订单、发送消息或删除数据。

因此 V1 采用：

```text
默认：继续未尝试动作，不重试历史失败动作
显式授权：只允许指定 canonical action ID 在全局上限内重试
```

系统不解析 `Request timed out`、余额不足或网站错误文本来猜测安全性。用户在受控测试站可以显式授权 `add_to_cart`；生产或高风险动作不得仅凭 resume 参数自动重试。

## 5. Write-ahead 执行标记

只在动作完成后 checkpoint 存在 exactly-once 缺口：浏览器动作可能已经产生副作用，但进程在追加 execution event 前退出。恢复后该 action 看起来仍是“未尝试”，会被普通 selector 自动再次执行。

因此 V1 在正式执行业务动作前，先原子写入一个通用 inflight marker：

```json
{
  "meta": {
    "inflight_action": {
      "attempt_id": "uuid",
      "source_node_id": "node-id",
      "action_id": "canonical-action-id"
    }
  }
}
```

执行协议：

```text
select action
  -> persist inflight_action
  -> execute action
  -> append execution_event with the same attempt_id
  -> clear inflight_action
  -> persist completed checkpoint
```

- 正常成功、明确失败或捕获到 timeout 时，均追加完成事件并清除 marker。
- 进程在任意中间点被杀死时，marker 留在最后 checkpoint，表示执行结果未知。
- 遗留 inflight action 不能作为普通“未尝试动作”自动执行；只有本次 `--resume-retry-action` 显式授权且未达到上限时才可重试。
- 遗留 marker 本身计作一次不确定尝试，参与全局最大尝试数，避免反复崩溃导致无限重试。
- replay 动作不写业务 inflight marker；其失败按第 9 节处理。
- `attempt_id` 是通用执行关联 ID，不是 PDDL/checkpoint 序号，也不改变 canonical edge identity。
- 完成后的 execution event 在 `execution_trace.metadata.attempt_id` 保存同一个 ID，使恢复和审计可以区分 marker 已提交但完成 checkpoint 未提交的尝试。

这不能提供外部系统级 exactly-once，但可以防止本地恢复逻辑把“可能已经执行”误判成“从未执行”。

## 6. 持久化恢复游标

Raw Graph 已保存节点、候选、canonical edges、`execution_events`、重放稳定性、总步数和 meta。V1 只新增一个通用恢复游标：

```json
{
  "meta": {
    "resume_cursor_node_id": "node-id"
  }
}
```

- 每个完成的探索尝试后，游标记录 explorer 认为的当前节点。
- 成功动作后通常是 target；失败或 no-op 后通常仍是 source。
- 旧图没有游标时，从最后一个 `execution_event` 推导：成功取 target，失败/no-op 取 source；没有事件时取 `start_node_id`。
- 最近失败 action 可从 `execution_events` 推导，但它只是诊断和运行时 preference 的候选，不能替代本次 CLI 的显式 retry 授权。
- 游标只是恢复提示，不是可信事实。它必须能从 start 经非 unstable 的 replayable edges 到达。

不新增 Cookie、localStorage、DOM、selector、模型会话或 retry 授权字段。授权是每次运行的 CLI 输入，不持久化到图中。

## 7. Graph hydration

新增明确的恢复入口，例如：

```python
WebKobeGraphManager.from_graph(graph: WebKobeGraph) -> WebKobeGraphManager
WebKobeExplorer.restore_graph(graph: WebKobeGraph) -> None
```

恢复必须防御性复制并原样保留：

- 节点顺序、候选和 visit 信息；
- canonical edges 与 replay validation metadata；
- 有序 `execution_events`，包括重复尝试；
- `total_steps_completed` 和 graph meta；
- start node ID；
- 遗留 `inflight_action`；
- 已经生成过候选的节点集合，避免恢复后重复请求 VLM。

hydration 不得通过普通 `add_edge()` 重建历史，否则会重复追加 execution events 或改变 visit count。

恢复时不把旧 `exploration_summary.steps_completed` 当作本轮进度。最终 summary 报告：历史基线总步数、累计总步数、本轮新增步数和本轮 `stop_reason`。

累计 replay 次数从旧 meta 初始化后继续增加。`blocked_replay_node_ids` 和连续无进展计数属于本轮瞬态状态，恢复时重置，不能永久屏蔽因临时服务故障而失败的 frontier。

## 8. 恢复目标选择

按以下顺序选择：

1. 可达且仍有 eligible action 的 `resume_cursor_node_id`；
2. 最近一个已被本次 CLI 授权、仍允许重试的失败事件 source；
3. 现有 selector 返回的可达非入口 frontier；
4. 入口节点 fallback；
5. 没有 eligible frontier 时以 `resume_frontier_exhausted` 正常终止。

路径只允许使用当前 `REPLAYABLE_EDGE_STATUSES` 中、`execution_trace.success=True` 且未标为 `unstable` 的边。不能因为某节点是上次断点而绕过 fail-closed。

选中目标后，执行 reset + replay + target validation。

## 9. Replay 失败的持久化边界

当前实现把任何 replay action failure 都永久标记为 `unstable`。这对可恢复任务过强：模型超时、额度不足或 transport failure 没有反证历史 transition，却会永久“毒死”路径。

V1 调整为：

- replay 动作执行失败：本轮 block 目标，保留 edge 原有 validation 状态，不新增 execution event；
- replay 动作报告成功，但观察到的 target 与历史 target 不匹配：持久标记 edge 为 `unstable`；
- entry reset 或 entry validation 失败：本轮恢复失败，不修改历史 transition；
- 所有目标均不可恢复：安全停止并保留 checkpoint。

这仍然 fail-closed：失败路径本轮不会继续使用；只有实际观测反证 transition 时才永久降级。

## 10. 共享的动作 eligibility

frontier selector 与 explorer action selector 必须共享同一个判定，否则会出现 selector 认为可重试、explorer 却跳过。

按 `(source_node_id, canonical_action_id)` 汇总 `execution_events`：

- 无历史事件：eligible；
- 无历史事件但存在匹配的遗留 `inflight_action`：outcome unknown，默认 not eligible；显式授权且计入该 inflight 尝试后仍低于上限时 eligible；
- 任一事件成功、导航成功或 no-op：not eligible；
- 所有事件均为 `failed_execution`，action ID 获本次 retry 授权，且次数小于上限：eligible；
- 所有事件均失败但未获授权：not eligible；
- 次数达到上限：not eligible；
- replay 不追加 execution event，也不消耗业务动作次数。

最近失败 action 已获授权且 eligible 时，恢复到其 source 后优先执行一次。preference 仅存在于本轮内存，尝试结束后清除。

## 11. Checkpoint 一致性

每个新业务尝试包含两次原子提交。第一次在执行前保存 inflight marker；第二次在执行完成后保存 execution event 并清除 marker。完成 checkpoint 继续按现有顺序保存：

1. embedding records（启用时）；
2. Stagehand trace；
3. graph evidence sidecar；
4. compact graph 作为最后提交标记。

Stagehand trace 必须优先从 `execution_events` 生成，不能只遍历 canonical `edges`，否则同一动作失败后重试会丢失历史。

中断语义：

- 动作执行前必须先提交 inflight marker；
- 动作进行中进程被杀死时，不虚构失败或成功，保留 outcome-unknown marker；
- provider 明确返回失败或 timeout 被 runner 捕获后形成的 `failed_execution` 是一个完成尝试，应写入 checkpoint；
- 输入损坏或参数非法时，在启动浏览器前失败。

## 12. 输入兼容与验证

恢复前验证：

- schema 可加载；
- `graph.app` 与 `--app-name` 一致；
- start node 存在；
- edge source/target 均指向现有节点；
- execution events 保持完整执行证据；
- 输出路径不会被 clean 逻辑删除。

CLI URL 只做语法检查，不要求与历史 start reference URL 字面一致，因为合法重定向、规范化路径和登录入口可能改变 URL。浏览器 reset 后必须使用现有 `validate_current_node(start_node_id)` 验证真实入口状态。

旧图兼容：

- 没有 `execution_events` 时，用 canonical edges 作为一次性历史回退；
- 没有 inflight marker 的旧图按当前 completed-event 语义读取，无法追溯旧运行中已经丢失的半完成动作；
- 没有 resume cursor 时按第 6 节推导；
- 没有新 meta 字段时不改变普通加载、PDDL 或 retrospective analysis。

## 13. 验证计划

1. GraphManager hydration roundtrip 不重复事件、不改变 graph；
2. pre-action checkpoint 写入 inflight，completed checkpoint 用同一 attempt ID 追加 event 并清除；
3. 模拟执行前、执行中、执行后提交前崩溃，恢复均不自动重复 outcome-unknown action；
4. 断点推导覆盖成功、失败、inflight、空图和旧图；
5. eligibility 覆盖首次、未授权失败、授权失败一次、inflight、达到上限、成功和 no-op；
6. resume 只对显式授权的失败/inflight action 建立一次性 preference；
7. replay provider failure 只 block 本轮，target mismatch 才持久 unstable；
8. unstable 必经边导致目标不可恢复并 fallback；
9. 历史 replay 指标累计，本轮 blocked/无进展状态重置；
10. 中断前旧 checkpoint 保持可读；
11. CLI 同路径与不同路径恢复；
12. 本地 Playwright fixture 执行“第一轮中断/失败 -> 第二轮加载 -> replay -> 新边”；
13. 真实网站正向验收使用一张从 start 到断点不存在 unstable 必经边的图；
14. 当前购物图作为负向样例，验证 unstable 路径不会被强行恢复。

## 14. 当前购物实验的实际限制

当前 `frontier_replay_v1_mini_breadth_prompt_review_20260812` 图中，入口到商品详情路径的第一条 `apply_filters` edge 已被历史 replay 标为 `unstable`。因此 V1 按正确的 fail-closed 规则不能承诺重放到该图的 `add_to_cart` source；它应 fallback 到其他稳定可达 frontier，或报告没有可恢复路径。

这说明“有 checkpoint”不等于“一定能恢复到任意 checkpoint”。恢复收益取决于路径可重放性。当前图适合作为 unstable fallback 的负向验收；正向真实验收需要稳定路径。后续保存 concrete selector/arguments 可以提升可重放率，但 V1 不应绕过 unstable 标记伪造成功。

## 15. V1 明确不做

- 不恢复关闭的浏览器进程或 Stagehand session；
- 不持久化登录态、Cookie、localStorage 或服务端事务状态；
- 不保存或优先使用具体 selector、XPath、Playwright 命令；
- 不刷新旧节点的 VLM 候选；
- 不做跨图自动语义合并；
- 不支持多个 writer 并发写同一 checkpoint，也不实现文件锁；
- 不自动绕过 unstable 边；
- 不改变 Surface/Trace PDDL 语义；
- 不通过 resume retry 扩大高风险动作权限。
- 不在 V1 内构造跨领域高风险动作分类器；通用生产安全仍是独立前置能力。

## 16. 后续优化

- 保存成功动作的 concrete selector/arguments，优先确定性 Playwright 重放；
- selector 失效时回退 Stagehand semantic replay；
- 为登录网站引入显式、加密的 browser storage state；
- 按动作族进行 coverage 和软降权；
- 保存版本化 checkpoint 历史，而不只保留 latest；
- 记录跨多次恢复运行的 lineage、replay 成本和节省的 VLM 调用量。
