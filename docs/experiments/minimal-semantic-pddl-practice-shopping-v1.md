# Minimal Semantic PDDL：PracticeAutomatedTesting Shopping V1

日期：2026-08-12

## 范围与安全边界

本实验使用 `https://practiceautomatedtesting.com/shopping`，采用开放式
`observed_action` 探索、最多 5 个候选、Visual Delta、frontier replay 和
checkpoint/resume。命令没有传入任何 `place_order`、付款或最终提交选项；实验
未提交订单。

配置从本机已有 `.env` 进程内读取，实际源码来自当前 worktree；Stagehand 使用
主仓库已有兼容 `AsyncStagehand` 的本地 `.venv`，没有下载新的运行时依赖。

## 执行记录

1. 当前 worktree `.venv` 的 `stagehand==4.0.0` 不提供项目适配层所需的
   `AsyncStagehand`，首次尝试在启动前失败，未访问网站。
2. 改用主仓库已有本地 `.venv` 后，首次 5-step run 达到超时上限，但已写入
   `graph.json` checkpoint；没有清空重跑。
3. 从同一 `graph.json` 使用 `--resume-graph` 和 frontier replay 继续 3 步，成功
   写回同一 graph；再继续 1 步以验证修复后的 semantic observation compact
   持久化路径。

关键配置：

```text
--business-profile ecommerce_checkout
--openai-visual-delta
--stagehand-execution-mode observed_action
--max-candidates 5
--frontier-replay
--steps 5 / --resume-graph ... --steps 3 / --resume-graph ... --steps 1
```

## 真实观察结果

最终 Raw Graph 为 9 steps、10 nodes、9 edges。观察到的动作包括搜索、商品详情、
加入购物车和筛选；没有观察到 `open_checkout`。checkpoint 中记录了
`replay_attempt_count=10`、`replay_success_count=2`、`replay_failure_count=8`。

截图 VLM 确实返回了位置、completion fact 和 evidence 字段，但部分真实返回的
`action_role` 是 `business_intent`、`target`、`filtering` 或 `filter`，不在受限的
语义 role contract 中。因此确定性 parser 将这些观察安全降级为 `unknown`，没有
把未经合同验证的结果写入 `WebKobeEdge.semantic_observation` 或 Minimal Semantic
PDDL。该偏差保留在 `stagehand_trace*.json` 与 `graph_evidence.json` 中。

这意味着本次真实 graph 的语义投影报告为：

```json
{
  "included_raw_edge_ids": [],
  "fallback_projection": "location",
  "fallback_reason": "no_usable_semantic_actions"
}
```

没有据此虚构 `at-checkout`、`cart-has-items` 或独立 cart/order-review location。

## 产物

- Raw Graph：[graph.json](minimal-semantic-pddl-practice-shopping-v1/graph.json)
- Raw evidence：[graph_evidence.json](minimal-semantic-pddl-practice-shopping-v1/graph_evidence.json)
- 初次 trace：[stagehand_trace.json](minimal-semantic-pddl-practice-shopping-v1/stagehand_trace.json)
- Resume traces：[stagehand_trace_resume.json](minimal-semantic-pddl-practice-shopping-v1/stagehand_trace_resume.json)、[stagehand_trace_resume2.json](minimal-semantic-pddl-practice-shopping-v1/stagehand_trace_resume2.json)
- Semantic projection：[semantic_projection](minimal-semantic-pddl-practice-shopping-v1/semantic_projection)
- Location V1 fallback：[location_fallback](minimal-semantic-pddl-practice-shopping-v1/location_fallback)

## SafeSym

对真实 graph 的语义主路径无法生成 problem，因为语义观察全部被严格 role
contract 排除；因此没有把 Location V1 的结果冒充 Minimal Semantic PDDL 成功。

对同一 Raw Graph 的明确 Location V1 fallback 运行了 SafeSym smoke：

```text
parser: pass
safety injection: pass
base planner: pass
safe planner: pass
safety actions inserted: none (本图未包含敏感动作)
```

SafeSym 报告在
`minimal-semantic-pddl-practice-shopping-v1/location_fallback/safesym_smoke_report.json`。

## 已知限制

- 本次 live run 没有到达 `open_checkout`，所以不能声称真实站点已验证
  `shopping -> checkout`；应在保留的 graph 上继续 resume，而不是重置。
- 当前 VLM 对新增 role contract 的遵循度不足，真实语义 graph 因此安全降级。
- 合成 fixture 已验证 `add-to-cart -> open-checkout` 的最短两步路径、能力事实
  与业务事实分离，以及文档域复用同一 builder/compiler；这些是离线验收证据，
  不是本次 live site 的观察替代品。
