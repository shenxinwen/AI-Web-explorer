# SafeSym Bridge

SafeSym Bridge 将动态网页探索结果投影为最小、可验证的语义 PDDL。当前只保留一条生产路径：

```text
WebKobeGraph
  -> semantic planning graph
  -> domain.pddl + optional problem.pddl
  -> SafeSym smoke / planner
```

## 1. 生成探索图

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore `
  --url https://www.saucedemo.com/ `
  --app-name saucedemo `
  --goal "explore the shopping and checkout flow" `
  --output artifacts/saucedemo/web_kobe_graph.json
```

Explorer 使用 semantic location 候选池进行正常探索。当前位置候选耗尽而其他 frontier 仍有未完成候选时，controller 可触发 replay。replay 只恢复上下文，随后仍由 Explorer 发现和执行后续动作。

## 2. 投影 Minimal Semantic PDDL

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-semantic-pddl `
  --graph artifacts/saucedemo/web_kobe_graph.json `
  --output artifacts/saucedemo/pddl `
  --goal-location checkout_complete
```

输出：

- `semantic_planning_graph.json`
- `semantic_projection_report.json`
- `domain.pddl`
- `problem.pddl`（提供目标时）

投影只接收具有可用 semantic location、动作语义和结果证据的内容；没有可用语义动作时 fail closed，不回退到旧的页面节点或 trace PDDL。

## 3. SafeSym smoke

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir artifacts/saucedemo/pddl `
  --safesym-root D:/path/to/SafeSym
```

Smoke 用于检查 PDDL 解析、SafeSym 注入兼容性，并在配置 planner 时验证 base/safe planning。

## 设计边界

- `BusinessFlowProfile` 只参与本地结构化事实验证和 planner projection。
- replay 不生成候选、不更新图、不验证业务目标，也不承担规划。
- 正常探索以 semantic location 为主；replay 可使用规范化 URL identity 辅助选择已知 frontier，但不会把 URL 规则扩散到探索逻辑。
- 旧 Trace/Location/Surface PDDL 及对应 CLI 已移除，不再作为兼容回退路径。
