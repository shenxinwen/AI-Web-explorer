# 位置作用域开放探索修复设计

## 目标

在不重写现有探索器的前提下，修复首次实现中阻断真实实验的接线、安全、预算和恢复问题，使其满足已批准的 feasibility 验收标准。

本轮保留已经通过测试的 `LocationExplorationMemory`、位置内 canonical action 去重、候选持久化、targeted/supplement scan 与 Minimal Semantic PDDL 投影。只替换或收紧错误边界，不建立第二套并行实现。

## 修复顺序

### 1. 真实业务事实与最终提交授权

Explorer 必须同时保存 `SemanticExperimentProfile` 对象和 prompt context。动作完成后的最终 `observable_change` 由浏览器结构变化、URL、DOM/state delta、VLM change kind 和 VLM observable flag 确定。

若启用了 experiment profile，则必须调用 `verify_experiment_planning_delta()`，输入：

- 通用 structured delta；
- VLM candidate added/removed facts；
- VLM evidence；
- 最终 observable change。

只有 allow-list 内、确有变化且有非空证据的业务事实可以晋升为 verified facts。离线集成测试不得在页面 signature 中直接预置 `checkout_info_complete`、`payment_info_complete` 或 `order_submitted`。

最终提交授权采用 fail-closed：只有以下三项同时成立才允许 prompt 出现最终下单许可：

1. profile 为 `practice_shopping_feasibility`；
2. 显式传入 `--allow-test-site-final-order`；
3. 起始 URL 的规范化 origin 与 path 为 `https://practiceautomatedtesting.com/shopping`。

生成测试数据本身不得携带授权语义。任一条件缺失时拒绝最终提交；flag 用于其他 profile 或 URL 时 CLI/runner 直接报错。

### 2. 运行时语义契约

`SemanticExperimentProfile.action_role_examples` 只能使用 `SEMANTIC_ACTION_ROLES` 中的值。当前映射统一为：

- sort/filter/search/paginate -> `presentation_capability`
- open product/close detail -> `navigation`
- add to cart -> `state_mutation`
- open checkout/open empty cart -> `guarded_navigation`
- checkout/payment form completion -> `form_completion`
- place order -> `commit`

运行时必须对 VLM semantic observation 执行 fail-closed 过滤：

- source/target location 必须属于 profile `allowed_locations`；
- completion facts 必须属于 `completion_fact_ids`；
- business facts必须属于 `business_fact_ids`；
- presentation action 只能保持原位置；
- 被拒绝字段及原因写入 trace，不进入 edge/PDDL。

### 3. 预算、恢复与 replay

以下预算跨 checkpoint/resume 累计：

- 正式动作最多 20；
- 连续无语义进展最多 3；
- 每候选最多 2 次；
- 每 frontier replay 失败最多 2；
- replay 总数最多 4；
- VLM scan 最多 2 次；
- 每位置最多 8 个候选。

所有 `explore_one_step()` 的正式动作必须通过同一个预算入口计数，包括 replay 成功后的后续动作。恢复时只执行剩余正式动作额度，不能重新获得 20 步。

location-scoped 模式下，持久化 candidate status/attempts 是 retry 权威；legacy `ResumePolicy` 不得阻止 `retryable_no_change` 或 `retryable_failure` 的第二次尝试。

Replay 只改变浏览器位置和 Explorer 的临时 current pointer，不得修改节点、边、planning facts、candidate memory 或 edge metadata。replay audit/metrics 只能写运行级 checkpoint metadata。恢复验证只要求：

- 目标 semantic location；
- frontier 后续候选显式要求的 verified business facts。

普通累计 completion facts 不参与恢复验证。

### 4. 候选 preflight 与最终证据

候选执行前进行轻量、无 VLM preflight，结果只有：

- `available`：有明确可见目标；
- `stale`：明确证明目标已消失或禁用；
- `unknown`：无法通过 DOM 确认。

只有 `stale` 会直接标记 `stale/disabled` 且不消耗正式动作；`available` 和 `unknown` 均交给 Stagehand。不得根据文本模糊匹配把 unknown 错判 stale。

最终离线端到端测试必须覆盖：shopping 普通能力、加购、targeted scan、checkout 表单、payment、place order、confirmation、合法 PDDL、必要业务前提，以及 replay 前后完整 graph JSON 不变（运行级 replay metrics 除外）。

## 非目标

- 不重写 Semantic Planning/PDDL compiler；
- 不增加站点 selector、CSS/XPath 或商品级硬编码；
- 不运行真实网站或付费 VLM 实验；
- 不扩大当前四类位置和既定事实词表；
- 不清理与本修复无关的旧代码。

## 合并门禁

每个阶段独立提交并通过定向测试。全部阶段完成后必须通过完整非浏览器测试、`git diff --check`，并由主会话审查。真实实验只能在代码验收通过后启动。
