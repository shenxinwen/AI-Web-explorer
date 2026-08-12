# Resumable Web Exploration V1 Design

## 1. 目标

把当前一次性的 `web-kobe-stagehand-explore` 运行改造成可中断、可恢复的探索任务。模型超时、额度不足、进程退出或人工暂停后，下一次运行应复用已经保存的 Raw Graph，从入口重放回一个可信断点，然后继续新增探索，而不是从零重新生成候选和重复所有历史动作。

V1 的成功标准是：已有图可以独立加载；浏览器可以从入口恢复到最近可信断点；历史失败动作可以进行有限重试；新增步骤继续原子写入 checkpoint；恢复失败不会破坏原始图。

## 2. 核心语义

恢复不是浏览器会话恢复。旧浏览器进程、DOM 对象、Cookie 内存状态和页面句柄都不可信。每次恢复都创建新浏览器，并执行：

```text
load checkpoint graph
  -> validate graph and resume policy
  -> start a fresh browser at start URL
  -> reset and validate entry state
  -> choose a reachable resume target
  -> replay stored successful transitions
  -> validate arrival at the target node
  -> retry the interrupted/failed action once, or continue untried candidates
  -> checkpoint every newly completed attempt
```

`--steps N` 表示本次恢复运行最多新增的执行尝试数，不包含历史 `total_steps_completed`，也不包含为了回到断点而执行的 replay 动作。

## 3. CLI 合约

在现有命令上增加显式恢复输入：

```powershell
web-kobe-stagehand-explore `
  --url 'https://practiceautomatedtesting.com/shopping' `
  --resume-graph 'previous/graph.json' `
  --output 'resumed/graph.json' `
  --steps 6 `
  --resume-failed-max-attempts 2 `
  --frontier-replay
```

规则：

- `--resume-graph` 可选；未提供时保持当前全新探索行为。
- 恢复必须启用 frontier replay；若用户未显式提供 `--frontier-replay`，CLI 在 resume 模式自动启用，并在报告中记录。
- `--resume-failed-max-attempts` 是同一 `(source_node_id, canonical_action_id)` 的全局最大执行尝试数，默认 `2`，必须大于等于 `1`。
- `--resume-graph` 与 `--output` 可以是同一路径。写入继续使用原子替换；首次新增 checkpoint 前发生的启动或恢复失败不会截断旧文件。
- 也允许不同路径。恢复输入始终只读；加载成功后先将恢复基线原子写入新输出，保证即使尚未新增动作，新输出也是可加载 checkpoint。
- `--clean-output-dir` 与 `--resume-graph` 互斥，避免在读取前删除恢复输入或配套证据。
- 模型、API、中转服务和本次新增步数可以与历史运行不同。

## 4. 持久化恢复状态

Raw Graph 已经保存节点、候选、canonical edges、`execution_events`、重放稳定性、总步数和 meta。V1 只新增通用恢复游标，不保存浏览器对象：

```json
{
  "meta": {
    "resume_cursor_node_id": "node-id",
    "resume_preferred_action_id": "optional-action-id"
  }
}
```

- 每个完成的探索尝试后，`resume_cursor_node_id` 记录 explorer 认为的当前节点。
- 成功动作后，游标通常是 target；失败或 no-op 后，游标通常仍是 source。
- `resume_preferred_action_id` 只在最新动作是仍可重试的 `failed_execution` 时保存，用于恢复后优先重试一次。
- 旧图没有游标时，从最后一个 `execution_event` 推导：成功事件取 target，失败/no-op 事件取 source；没有事件时取 `start_node_id`。
- 游标只是恢复提示，不是可信事实。它必须能从 start 通过 replayable、非 unstable 的边到达，否则进入 fallback 选择。

不新增 Cookie、localStorage、DOM、selector 或模型会话字段。登录态和外部服务状态恢复不属于 V1。

## 5. Graph hydration

新增一个明确的恢复入口，例如：

```python
WebKobeGraphManager.from_graph(graph: WebKobeGraph) -> WebKobeGraphManager
WebKobeExplorer.restore_graph(graph: WebKobeGraph) -> None
```

恢复必须原样保留：

- 节点顺序、候选及 visit 信息；
- canonical edges 和 replay validation metadata；
- 有序 `execution_events`，包括重复尝试；
- `total_steps_completed` 与 graph meta；
- start node ID；
- 已经观察过候选的节点集合，避免恢复后重新请求 VLM。

hydration 不得通过普通 `add_edge()` 重建历史，否则会重复追加 execution events 或改变 visit count。应由专门的构造路径复制已验证数据。

恢复时不把旧 `exploration_summary.steps_completed` 当作本轮进度。最终 summary 同时保留累计总步数，并报告本轮新增步数和 `stop_reason`。

## 6. 恢复目标选择

恢复目标按以下顺序选择：

1. 可达且仍有 eligible action 的持久化 `resume_cursor_node_id`；
2. 最后一个仍允许重试的失败事件 source；
3. 现有 frontier selector 返回的可达非入口 frontier；
4. 入口节点作为 fallback；
5. 没有 eligible frontier 时，以 `resume_frontier_exhausted` 正常终止。

路径只允许使用当前 `REPLAYABLE_EDGE_STATUSES` 中、`execution_trace.success=True` 且未标为 `unstable` 的边。恢复不会因为“它是上次断点”而绕过 fail-closed 规则。

选中目标后，执行现有 reset + replay + target validation。若 replay 动作失败或目标状态不匹配：

- 将失败边维持/标记为 `unstable`；
- 本轮 block 该目标；
- 重新选择另一个可达 frontier；
- 不新增虚假的成功 execution event；
- 所有可选目标失败后安全停止。

## 7. 失败动作的有限重试

当前逻辑只要 source 上存在某 action edge，就视为 tried。Resume V1 必须让 frontier 选择与 explorer 动作选择共享同一个 eligibility 判定，避免 selector 认为可重试、explorer 却跳过。

对 `(source_node_id, canonical_action_id)` 汇总 `execution_events`：

- 没有历史事件：eligible；
- 任一事件成功、导航成功或 no-op：not eligible；
- 所有事件均为 `failed_execution`，且尝试数小于 `resume_failed_max_attempts`：resume 模式下 eligible；
- 尝试数达到上限：not eligible；
- replay 本身不追加 execution event，也不消耗业务动作尝试次数。

该规则不解析 `Request timed out`、余额不足或网站错误字符串，不依赖业务领域。默认最大次数为 2，因此已有一次失败的 `add_to_cart` 可以再试一次，而永久无效动作不会在同一图上无限重试。

若断点带有 eligible 的 `resume_preferred_action_id`，恢复到目标后优先选择该动作一次；尝试结束后清除 preference，后续恢复按统一 eligibility 计算。

## 8. Checkpoint 一致性

每个新执行尝试完成后，按现有原子 checkpoint 流程保存：

1. embedding records（启用时）；
2. Stagehand trace；
3. graph evidence sidecar；
4. compact graph 作为最后提交标记。

Stagehand trace 必须优先从 `execution_events` 生成，不能只遍历 canonical `edges`，否则同一动作的失败后重试会在 trace 中丢失。

中断边界：

- 动作完成并生成 execution event 后才更新正式 graph checkpoint；
- 动作进行中被杀死时，不虚构失败或成功，恢复到上一个完成 checkpoint；
- 失败动作本身是完成的尝试，应写入 checkpoint 并可按策略重试；
- 输入损坏、app/start 不兼容或恢复参数非法时，在启动浏览器前失败。

## 9. 兼容与验证

恢复前验证：

- schema 可加载；
- `graph.app` 与 `--app-name` 一致；
- start node 存在；
- `--url` 的 origin/path 与 start node reference URL 一致；
- edge source/target 均指向现有节点；
- execution events 可引用 canonical edge 或保持自身完整执行证据；
- 输出路径安全且不会被 clean 逻辑删除。

旧图兼容：

- 没有 `execution_events` 时，用 canonical edges 作为一次性历史回退；
- 没有 resume cursor 时按第 4 节推导；
- 没有新 meta 字段时不改变普通加载、PDDL 或 retrospective analysis 行为。

测试层次：

1. GraphManager hydration roundtrip 不重复事件、不改变 graph；
2. 断点推导覆盖成功、失败、空图和旧图；
3. eligibility 覆盖首次、失败一次、失败两次、成功、no-op；
4. resume 优先回到失败 source 并重试 preferred action；
5. unstable 必经边导致目标不可恢复并 fallback；
6. 中断前旧 checkpoint 保持可读；
7. CLI 同路径和不同路径恢复；
8. 本地 Playwright fixture 执行“第一轮失败/中断 -> 第二轮加载 -> replay -> 新边”；
9. 真实购物网站用已有 `add_to_cart` 失败图恢复一次，观察是否到达详情并重新执行该动作。

## 10. V1 明确不做

- 不恢复关闭的浏览器进程或 Stagehand session；
- 不持久化登录态、Cookie、localStorage 或服务端事务状态；
- 不保存/优先使用具体 selector、XPath 或 Playwright 命令；
- 不刷新旧节点的 VLM 候选；
- 不做跨图自动语义合并；
- 不并发运行多个 writer，也不实现文件锁；
- 不自动绕过 unstable 边；
- 不因为恢复而改变 Surface/Trace PDDL 语义；
- 不自动执行购买、支付、删除等高风险最终动作；既有安全边界保持不变。

## 11. 后续优化

V1 验证成功后可按收益逐步增加：

- 保存成功动作的 concrete selector/arguments，优先用确定性 Playwright 低成本重放；
- selector 失效时回退 Stagehand semantic replay；
- 为需要登录的网站引入显式、加密的 browser storage state；
- 按动作族而非精确 semantic ID 进行 coverage 和软降权；
- 支持版本化 checkpoint 历史，而不只保存 latest；
- 多次恢复运行的实验 lineage 和成本指标。

