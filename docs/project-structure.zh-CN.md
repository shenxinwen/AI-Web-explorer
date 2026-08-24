# 项目结构（当前主线）

## 运行时分层

```text
CLI / browser_runner
        |
        v
WebKobeExplorationController ---- frontier replay / resume
        |
        v
WebKobeExplorer
  |-- screenshot + VLM candidate observation
  |-- semantic-location candidate pool
  |-- dependency-aware local selection
  |-- Stagehand action execution
  |-- VLM action-outcome observation
  `-- WebKobeGraph update
        |
        v
semantic planning graph -> Minimal Semantic PDDL -> SafeSym
```

## 关键目录

### `src/ai_web_explorer/grounded_web/`

- `explorer.py`：正常探索闭环；管理页面观察、候选选择、动作执行、outcome 和图更新。
- `controller.py`：步数预算、终止判断和 frontier replay 调度。
- `location_exploration.py`：semantic location 候选池、requires、完成/失败和尝试次数。
- `frontier_replay.py`：reset 起始 URL 并重放已保存的 semantic-action path；不承担探索。
- `resume.py`：从图中寻找仍有未完成候选的 frontier，并构造 replay path。
- `action_outcome.py`：将动作后截图整理为语义位置、完成事实和结果证据。
- `business_affordance.py`：从截图观察候选业务动作。
- `web_kobe_graph.py`：图模型与序列化结构。

### `src/ai_web_explorer/safesym_bridge/`

- `browser_runner.py`：Playwright、Stagehand、Explorer、断点和 replay 的运行编排。
- `cli.py`：三个公开命令入口。
- `graph_loader.py`：WebKobeGraph JSON 读取。
- `semantic_planning.py`：从探索图生成语义规划图。
- `minimal_semantic_pddl.py`：生成 Minimal Semantic PDDL。
- `web_kobe_safesym_smoke.py`：SafeSym 解析、注入与 planner smoke。
- `business_profile.py`：本地结构化事实验证和 planner projection 辅助。

### `scripts/`

- `run_saucedemo_open_exploration_observe_act.py`：当前 SauceDemo 动态探索实验入口。

### `tests/safesym_bridge/`

测试按当前组件边界组织。replay、Explorer、browser runner、semantic planning、Minimal Semantic PDDL 和 SafeSym smoke 均有独立覆盖。已删除仅验证旧 Trace/Location/Surface PDDL 或旧固定图命令的测试。

## 数据所有权

- 候选池以 semantic location 为键，保存候选、requires、完成状态、失败状态和尝试次数。
- WebKobeGraph 保存观察节点、已执行边、semantic location 和运行时 checkpoint。
- replay 读取图和候选池，但不得修改 graph、edge、candidate pool、扫描状态或正式尝试次数。
- replay 成功后把控制权交回 Explorer，由 Explorer 继续正常探索。

## 公开 CLI

```text
web-kobe-stagehand-explore
web-kobe-semantic-pddl
web-kobe-safesym-smoke
```

其他旧命令不再是公开接口。
