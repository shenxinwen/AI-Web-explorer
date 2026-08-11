# Generalized Location PDDL V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将无任务目标的 Web-KOBE 探索产物确定性地编译为通用 `location + at(?location)` PDDL，并让 SafeSym 对显式 start/goal 查询实际求出计划。

**Architecture:** 保留现有 Explorer、Raw Graph 和 Planning Abstraction；新增一个只消费 Planning Graph 的纯函数式 Location PDDL compiler，并让 Phase A CLI 调用它。探索到规划查询保持单向数据流，task/goal 不得进入候选生成、动作选择或 Stagehand prompt。

**Tech Stack:** Python 3.11、dataclasses、pytest、现有 WebKobeGraph/PlanningAbstraction、SafeSym parser、Fast Downward。

## Global Constraints

- 不修改用户 `.env`，不把 API key、模型地址或请求头写入产物。
- 不在 projector 中硬编码电商、文档、会议、登录、搜索、筛选等领域 action/page 名称。
- Location V1 的 PDDL schema 固定为 `location` 类型、location constants 和 `(at ?location - location)`。
- 只有 execution trace 成功、状态可投影、source/target 存在且 source != target 的 Planning edge 进入 domain。
- VLM、embedding、Visual Delta、profile facts、supporting facts 和 evidence sidecar 不进入 PDDL。
- start/goal 只在 Planning Graph 冻结后用于 problem 生成，不得反向影响探索。
- 保留 `web-kobe-phase-a`、`compile_phase_a_domain()` 和现有 graph loader 的兼容入口。
- 旧 fact-rich `compile_web_kobe_graph_to_pddl()` 保留为诊断兼容路径；本计划不扩展或重写它。
- 每项实现按红灯、最小实现、绿灯执行；不顺手修复 target matching、Visual Delta 或 observer 稳定性问题。

---

## File Structure

- Create: `src/ai_web_explorer/safesym_bridge/location_pddl.py`
  - Location V1 的命名、edge eligibility、domain/problem 渲染、可达性和 projection report。
- Create: `tests/safesym_bridge/test_location_pddl.py`
  - 纯 compiler 的格式、确定性、排除规则、problem 和领域无关测试。
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py`
  - 让 `compile_phase_a_domain()` 成为新 compiler 的兼容 wrapper；保留旧 loader/诊断函数。
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
  - Phase A 写出 `projection_report.json`，并在显式提供 start/goal 时写 `problem.pddl`。
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py`
  - 固定 Phase A 新产物、可选 problem、错误参数和 sidecar 独立性。
- Modify: `tests/safesym_bridge/test_business_affordance.py`
  - 强化 task/goal 不进入开放式候选 prompt 的合同。
- Modify: `tests/safesym_bridge/test_web_kobe_safesym_smoke.py`
  - 用 Location V1 产物覆盖 SafeSym parse/inject/solve 调用链。
- Modify: `docs/safesym-bridge.md`
  - 记录 Location V1 格式、Phase A 查询参数和真实 SafeSym 验收命令。

---

### Task 1: 建立纯 Location PDDL compiler

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/location_pddl.py`
- Create: `tests/safesym_bridge/test_location_pddl.py`
- Reference: `src/ai_web_explorer/grounded_web/graph.py`
- Reference: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py:758-759`

**Interfaces:**
- Consumes: `WebKobeGraph` Planning Graph；可选 `edge_mappings: Sequence[Mapping[str, Any]]`。
- Produces: `LocationDomainProjection`、`LocationProblemProjection`、`compile_location_domain()`、`compile_location_problem()`。

- [ ] **Step 1: 写 domain 和 report 的失败测试**

在 `tests/safesym_bridge/test_location_pddl.py` 建立最小 graph fixture，并固定公开接口：

```python
from dataclasses import replace

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeEdge, WebKobeGraph, WebKobeNode
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_domain


def _node(node_id: str, label: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        node_label=label,
        page_description=label,
        page_frame=PageFrame(
            page_id=node_id,
            page_type="generic",
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=label,
        ),
        state_schema={},
        last_state_snapshot={},
    )


def _edge(source: str, action: str, target: str, *, status: str = "verified", success: bool = True) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action,
        action=BrowserAction("business_intent", None, action, canonical_action_name=action),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "business_intent", None, action, {}, source, target, success
        ),
        status=status,
    )


def test_compile_location_domain_uses_one_typed_location_predicate():
    graph = WebKobeGraph(
        app="generic_site",
        start_node_id="raw-home",
        total_steps_completed=1,
        nodes=[_node("raw-home", "Home"), _node("raw-details", "Details")],
        edges=[_edge("raw-home", "open_details", "raw-details")],
    )

    result = compile_location_domain(graph)

    assert "(:types location)" in result.domain
    assert "(at ?location - location)" in result.domain
    assert "home - location" in result.domain
    assert "details - location" in result.domain
    assert "(at_home)" not in result.domain
    assert "(:action open_details" in result.domain
    assert "(at home)" in result.domain
    assert "(not (at home))" in result.domain
    assert "(at details)" in result.domain
    assert result.report["schema_version"] == "location-pddl-projection-v1"
    assert result.report["actions"][0]["planning_edge_id"] == graph.edges[0].edge_id
```

- [ ] **Step 2: 运行测试并确认红灯**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py::test_compile_location_domain_uses_one_typed_location_predicate -q
```

Expected: collection FAIL，错误为 `ModuleNotFoundError: ai_web_explorer.safesym_bridge.location_pddl`。

- [ ] **Step 3: 实现最小公开类型和 domain 编译**

在 `location_pddl.py` 定义以下公开接口：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ai_web_explorer.grounded_web.graph import WebKobeGraph


LOCATION_PROJECTION_SCHEMA_VERSION = "location-pddl-projection-v1"
PROJECTABLE_EDGE_STATUSES = frozenset({
    "verified",
    "succeeded",
    "succeeded_with_observed_change",
    "succeeded_with_navigation",
})


@dataclass(frozen=True)
class LocationDomainProjection:
    domain: str
    report: dict[str, Any]


@dataclass(frozen=True)
class LocationProblemProjection:
    problem: str
    start_location: str
    goal_location: str
```

公开函数签名固定为：

```python
compile_location_domain(
    graph: WebKobeGraph,
    *,
    edge_mappings: Sequence[Mapping[str, Any]] = (),
    domain_name: str = "web_kobe_location",
) -> LocationDomainProjection

compile_location_problem(
    graph: WebKobeGraph,
    *,
    start_node_id: str,
    goal_node_id: str,
    domain_name: str = "web_kobe_location",
    problem_name: str = "web_kobe_location_problem",
) -> LocationProblemProjection
```

最小 domain 渲染必须使用 `(:requirements :strips :typing)`、`(:types location)`、typed constants 和唯一
`(at ?location - location)` predicate。节点和 edge 在渲染前分别按 `node_id`、`edge_id` 排序。

名称规范化只允许 ASCII 小写字母、数字和下划线；空名称回退到 `location_{digest}` 或 `action_{digest}`，其中
`digest` 严格等于对应稳定 ID 的 SHA-256 前 8 位。冲突名称追加相同规则生成的稳定摘要，不能依赖列表索引。

- [ ] **Step 4: 运行单测并确认绿灯**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py::test_compile_location_domain_uses_one_typed_location_predicate -q
```

Expected: `1 passed`。

- [ ] **Step 5: 写 edge 排除、provenance 和确定性的失败测试**

追加测试，构造 successful cross-edge、self-loop、failed edge、missing-target edge，并传入两个 raw edge mapping：

```python
def test_location_domain_is_deterministic_and_reports_excluded_edges():
    base = _graph_with_cross_self_failed_and_missing_edges()
    mappings = [
        {"planning_edge_id": base.edges[0].edge_id, "raw_edge_id": "raw-edge-b"},
        {"planning_edge_id": base.edges[0].edge_id, "raw_edge_id": "raw-edge-a"},
    ]

    first = compile_location_domain(base, edge_mappings=mappings)
    shuffled = replace(base, nodes=list(reversed(base.nodes)), edges=list(reversed(base.edges)))
    second = compile_location_domain(shuffled, edge_mappings=list(reversed(mappings)))

    assert first.domain == second.domain
    assert first.report == second.report
    assert first.report["actions"][0]["raw_edge_ids"] == ["raw-edge-a", "raw-edge-b"]
    assert {item["reason"] for item in first.report["excluded_edges"]} == {
        "planning_self_loop",
        "unverified_transition",
        "missing_location_reference",
    }
```

同时断言 supporting facts、planning facts、Visual Delta facts 和 action 名称文本不会成为 predicate。

- [ ] **Step 6: 运行测试并确认红灯原因**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py -q
```

Expected: 新测试 FAIL，因为排除报告、稳定冲突处理或 provenance 尚未完成。

- [ ] **Step 7: 完成 edge eligibility 和 projection report**

实现结构化排除顺序：

```python
def _exclusion_reason(edge, known_node_ids: set[str]) -> str | None:
    if edge.source_node_id not in known_node_ids or edge.target_node_id not in known_node_ids:
        return "missing_location_reference"
    if edge.source_node_id == edge.target_node_id:
        return "planning_self_loop"
    if not edge.execution_trace.success or edge.status not in PROJECTABLE_EDGE_STATUSES:
        return "unverified_transition"
    if not (edge.action.canonical_action_name or edge.action.semantic_id).strip():
        return "invalid_action_identity"
    return None
```

report 固定包含：

```python
{
    "schema_version": LOCATION_PROJECTION_SCHEMA_VERSION,
    "domain_name": domain_name,
    "locations": [
        {"planning_node_id": node_id, "pddl_constant": constant}
    ],
    "actions": [
        {
            "planning_edge_id": edge_id,
            "pddl_action": action_name,
            "source_location": source_constant,
            "target_location": target_constant,
            "raw_edge_ids": sorted(raw_edge_ids),
        }
    ],
    "excluded_edges": [
        {"planning_edge_id": edge_id, "reason": reason}
    ],
}
```

所有列表按稳定 ID 排序；report 不包含截图、prompt、embedding 或 sidecar 内容。

- [ ] **Step 8: 运行 compiler 测试**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py -q
```

Expected: 全部通过。

- [ ] **Step 9: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/location_pddl.py tests/safesym_bridge/test_location_pddl.py
git commit -m "feat: add deterministic location PDDL compiler"
```

---

### Task 2: 将 Phase A 接到 Location compiler

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py:845-893`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py:538-566`
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py:73-115`
- Test: `tests/safesym_bridge/test_web_kobe_pddl_projector.py`

**Interfaces:**
- Consumes: Task 1 的 `compile_location_domain(graph, edge_mappings=artifacts.report.edge_mappings)`。
- Produces: 兼容的 `compile_phase_a_domain(graph) -> str`；Phase A 新增 `projection_report.json`。

- [ ] **Step 1: 修改 CLI 测试以定义新产物合同**

在 `test_phase_a_cli_writes_raw_planning_report_and_domain_only` 中把期望文件集合改为：

```python
assert {path.name for path in output_dir.iterdir()} == {
    "raw_graph.json",
    "planning_graph.json",
    "planning_abstraction_report.json",
    "projection_report.json",
    "domain.pddl",
}
domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
projection = json.loads((output_dir / "projection_report.json").read_text(encoding="utf-8"))
assert "(:types location)" in domain
assert "(at ?location - location)" in domain
assert projection["schema_version"] == "location-pddl-projection-v1"
assert not (output_dir / "problem.pddl").exists()
```

保留 compact/full 输入生成相同 domain 的断言，并增加两个 projection report 相等断言。

- [ ] **Step 2: 运行测试并确认红灯**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_behavior_state_graph_cli.py::test_phase_a_cli_writes_raw_planning_report_and_domain_only -q
```

Expected: FAIL，因为尚未写 `projection_report.json`，domain 仍使用多个 `at_*` predicates。

- [ ] **Step 3: 把 `compile_phase_a_domain` 改为兼容 wrapper**

删除该函数内部复制/清洗 graph 后再调用 legacy `_compile_domain()` 的路径，替换为：

```python
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_domain


def compile_phase_a_domain(
    graph: WebKobeGraph,
    *,
    options: PddlProjectionOptions | None = None,
) -> str:
    del options
    return compile_location_domain(graph).domain
```

保留函数签名中的 `options` 只为兼容旧调用方；Location V1 不读取这些 fact options。

- [ ] **Step 4: 让 Phase A CLI 一次编译并写 domain/report**

在 `cli.py` 的 Phase A 分支调用：

```python
projection = compile_location_domain(
    artifacts.planning_graph,
    edge_mappings=artifacts.report.edge_mappings,
)
(args.output / "domain.pddl").write_text(projection.domain, encoding="utf-8")
(args.output / "projection_report.json").write_text(
    json.dumps(projection.report, indent=2, ensure_ascii=False, sort_keys=True),
    encoding="utf-8",
)
```

不要从 `graph_evidence.json` hydrate provenance；只用 abstraction report 的 edge mappings。

- [ ] **Step 5: 运行 Phase A 和 projector 回归**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py -q
```

Expected: Phase A 测试通过；legacy fact-rich projector 测试继续通过。若旧测试只断言 Phase A 的 `at_*` 格式，
只把这些断言迁移到 typed `at` 格式，不删除 legacy `compile_web_kobe_graph_to_pddl()` 的诊断测试。

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/location_pddl.py src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_web_kobe_pddl_projector.py
git commit -m "feat: project Phase A through location PDDL"
```

---

### Task 3: 增加显式 start/goal problem 查询

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/location_pddl.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py:223-242,538-566`
- Modify: `tests/safesym_bridge/test_location_pddl.py`
- Modify: `tests/safesym_bridge/test_behavior_state_graph_cli.py`

**Interfaces:**
- Consumes: Task 1 的稳定 location name map 和 projectable transition 集合。
- Produces: `compile_location_problem()`；`web-kobe-phase-a --start-node ID --goal-node ID` 可选参数。

- [ ] **Step 1: 写 problem、可达性和参数配对的失败测试**

追加 compiler 测试：

```python
def test_compile_location_problem_uses_explicit_reachable_nodes():
    graph = _three_location_graph()
    result = compile_location_problem(
        graph,
        start_node_id="home-id",
        goal_node_id="details-id",
    )
    assert "(:domain web_kobe_location)" in result.problem
    assert "(:init (at home))" in result.problem
    assert "(:goal (at details))" in result.problem


def test_compile_location_problem_rejects_unreachable_goal():
    graph = _graph_with_disconnected_goal()
    with pytest.raises(ValueError, match="goal_unreachable"):
        compile_location_problem(
            graph,
            start_node_id="home-id",
            goal_node_id="isolated-id",
        )
```

追加 CLI 测试：两参数都存在时写 `problem.pddl`；只给其中一个时 `main()` 通过 argparse error 路径退出且错误文本
包含 `--start-node and --goal-node must be provided together`。

- [ ] **Step 2: 运行测试并确认红灯**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_behavior_state_graph_cli.py -q
```

Expected: 新 problem/CLI 测试失败，因为公开函数尚未实现、Phase A parser 尚无参数。

- [ ] **Step 3: 实现纯图可达性和 problem 渲染**

可达性只能遍历与 domain 相同的 projectable non-self-loop transitions：

```python
def _is_reachable(graph: WebKobeGraph, start: str, goal: str) -> bool:
    adjacency: dict[str, set[str]] = {}
    known = {node.node_id for node in graph.nodes}
    for edge in graph.edges:
        if _exclusion_reason(edge, known) is None:
            adjacency.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
    pending = [start]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(adjacency.get(current, ()), reverse=True))
    return False
```

start 不存在时执行 `raise ValueError(f"unknown_start_location: {start_node_id}")`；goal 不存在时执行
`raise ValueError(f"unknown_goal_location: {goal_node_id}")`；不可达时执行
`raise ValueError(f"goal_unreachable: {start_node_id} -> {goal_node_id}")`。

- [ ] **Step 4: 加 Phase A 可选查询参数**

给 `web-kobe-phase-a` parser 增加：

```python
web_kobe_phase_a_parser.add_argument("--start-node")
web_kobe_phase_a_parser.add_argument("--goal-node")
```

Phase A 完成 Planning Graph 后才验证并编译 problem。两参数都未提供时保持 domain-only；只提供一个时调用
`web_kobe_phase_a_parser.error("--start-node and --goal-node must be provided together")`；两者都有时写
`problem.pddl`。不得把这两个参数传给
`build_planning_state_graph()`、Explorer 或任何 VLM/Stagehand provider。

- [ ] **Step 5: 运行定向测试**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py -q
```

Expected: 全部通过。

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/location_pddl.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_behavior_state_graph_cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: generate explicit location planning problems"
```

---

### Task 4: 固定探索自主性和跨领域泛化合同

**Files:**
- Modify: `tests/safesym_bridge/test_business_affordance.py:52-75`
- Modify: `tests/safesym_bridge/test_location_pddl.py`
- Verify only: `src/ai_web_explorer/grounded_web/business_affordance.py`
- Verify only: `src/ai_web_explorer/grounded_web/explorer.py`
- Verify only: `src/ai_web_explorer/grounded_web/stagehand_prompt.py`

**Interfaces:**
- Consumes: 当前 `VisualAffordanceRequest.goal` 兼容字段和 Task 1 compiler。
- Produces: task/goal 单向隔离与三类领域 graph 的回归门禁；正常情况下不修改 Explorer。

- [ ] **Step 1: 强化开放式候选 prompt 合同**

将现有 `test_visual_affordance_prompt_keeps_vlm_stateless_about_graph_and_profile` 参数化为两个完全不同的 goal：

```python
@pytest.mark.parametrize(
    "external_goal",
    ["Reach checkout immediately", "Delete the selected document"],
)
def test_visual_affordance_prompt_ignores_external_task_goal(external_goal):
    request = VisualAffordanceRequest(
        goal=external_goal,
        current_screenshot_path="current.png",
        current_signature={"url_path": "/current"},
    )
    seen = {}

    def provider(prompt, *, current_screenshot_path):
        seen["prompt"] = prompt
        return '{"page_mode":"uncertain","regions":[]}'

    summarize_visual_affordances(request, provider=provider)

    assert external_goal not in seen["prompt"]
    assert "goal_location" not in seen["prompt"]
    assert "pddl" not in seen["prompt"].lower()
```

这是一项兼容合同；当前实现预期直接通过。若失败，只移除 task/goal 向候选 prompt 的数据流，不增加新的探索策略。

- [ ] **Step 2: 写跨领域 compiler 参数化测试**

用相同 builder 构造以下三组纯数据，禁止新增领域配置：

```python
@pytest.mark.parametrize(
    ("labels", "action"),
    [
        (("catalog", "details"), "open_item"),
        (("documents", "editor"), "open_document"),
        (("meeting_list", "meeting_room"), "join_meeting"),
    ],
)
def test_location_compiler_is_domain_agnostic(labels, action):
    graph = _two_location_graph(labels=labels, action=action)
    result = compile_location_domain(graph)
    assert "(at ?location - location)" in result.domain
    assert f"(:action {action}" in result.domain
    assert "cart_has_items" not in result.domain
```

再增加静态检查测试，读取 `location_pddl.py` 并断言不存在设计禁止的领域 token：

```python
def test_location_compiler_has_no_domain_action_rules():
    source = Path(location_pddl.__file__).read_text(encoding="utf-8").lower()
    for token in ("checkout", "cart", "login", "search", "filter", "payment"):
        assert token not in source
```

- [ ] **Step 3: 运行合同测试**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_location_pddl.py tests/safesym_bridge/test_stagehand_prompt.py -q
```

Expected: 全部通过。不要修改 checkout benchmark prompt；它是独立历史 benchmark，不属于通用探索路径。

- [ ] **Step 4: 静态核对 goal 没有进入通用探索执行 prompt**

Run:

```powershell
rg -n "request\.goal|self\.goal|goal_location|problem\.pddl" src/ai_web_explorer/grounded_web/business_affordance.py src/ai_web_explorer/grounded_web/explorer.py src/ai_web_explorer/grounded_web/stagehand_prompt.py
```

Expected: `request.goal` 不出现在 Visual Affordance prompt payload；显式 start/goal/problem 只存在于
`safesym_bridge`，不出现在通用探索候选或执行 prompt。`self.goal` 作为兼容 exploration context 可以存在，但不得
包含规划 query 或被序列化到 Visual Affordance prompt。

- [ ] **Step 5: Commit**

```powershell
git add tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_location_pddl.py
git commit -m "test: preserve open-ended exploration and PDDL generality"
```

---

### Task 5: SafeSym 消费、求解与文档验收

**Files:**
- Modify: `tests/safesym_bridge/test_web_kobe_safesym_smoke.py`
- Modify: `docs/safesym-bridge.md`
- Verify: `src/ai_web_explorer/safesym_bridge/web_kobe_safesym_smoke.py`
- Verify external: `C:/Users/moon/Desktop/Projects/SafeSym`
- Verify external: `C:/Users/moon/Desktop/Projects/AutoWebWorld/downward/fast-downward.py`

**Interfaces:**
- Consumes: Phase A 输出的 `domain.pddl`、可选 `problem.pddl`。
- Produces: SafeSym parser/inject/solve 证据和最终回归报告；不修改 SafeSym 源码。

- [ ] **Step 1: 把 SafeSym smoke fixture 改为 Location V1**

将 `_write_base_pddl()` 中 domain/problem 改成：

```lisp
(define (domain web_kobe_location)
  (:requirements :strips :typing)
  (:types location)
  (:constants start goal - location)
  (:predicates (at ?location - location))
  (:action go_goal
    :parameters ()
    :precondition (and (at start))
    :effect (and (not (at start)) (at goal))
  )
)
```

```lisp
(define (problem web_kobe_location_problem)
  (:domain web_kobe_location)
  (:init (at start))
  (:goal (at goal))
)
```

保留 fake runner 对 parse、inject、base solve 和 safe solve 的断言。

- [ ] **Step 2: 运行 SafeSym smoke 单测**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_web_kobe_safesym_smoke.py -q
```

Expected: 全部通过。

- [ ] **Step 3: 更新 bridge 文档**

在 `docs/safesym-bridge.md` 记录：

- Phase A domain 使用 `location + at(?location)`；
- `web-kobe-phase-a` 默认只生成 domain；
- 显式 `--start-node` 和 `--goal-node` 才生成 problem；
- start/goal 是事后规划查询，绝不传回 Explorer；
- `projection_report.json` 的审计用途；
- SafeSym 真实求解命令。

命令使用已核实路径：

```powershell
.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir 'outputs/experiments/practice_automated_testing/location_pddl_v1_review' `
  --safesym-root 'C:\Users\moon\Desktop\Projects\SafeSym' `
  --rules 'C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json' `
  --fast-downward 'C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py'
```

该目录与本计划真实验收目录保持一致。

- [ ] **Step 4: 运行完整非浏览器测试**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_local_shop_fixture.py
```

Expected: 不少于当前基线 `325 passed, 2 skipped`，且新增测试全部通过；记录精确结果。

- [ ] **Step 5: 对一个现有 Raw Graph 生成 Planning Graph、domain 和 problem**

先用不带 start/goal 的 Phase A 命令生成 Planning Graph：

```powershell
$inputGraph='outputs/experiments/practice_automated_testing/trial_20260811_gemini_relay/graph.json'
$queryDir='outputs/experiments/practice_automated_testing/location_pddl_v1_review'
.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a --graph $inputGraph --output $queryDir
```

读取 `$queryDir/planning_graph.json`，选择其 `meta.start_node_id` 为 start，并选择从 start 经 projectable edge
可达的非 start node 为 goal。随后使用相同 raw graph 和明确 ID 重新运行：

```powershell
$planning=Get-Content -Raw -Encoding utf8 "$queryDir/planning_graph.json" | ConvertFrom-Json
$actualStart=[string]$planning.meta.start_node_id
$actualGoal=[string](
  $planning.edges |
    Where-Object { $_.source_node_id -eq $actualStart -and $_.target_node_id -ne $actualStart -and $_.execution_trace.success } |
    Select-Object -First 1 -ExpandProperty target_node_id
)
if (-not $actualGoal) { throw 'No reachable non-self-loop goal in generated Planning Graph' }
.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a --graph $inputGraph --output $queryDir --start-node $actualStart --goal-node $actualGoal
```

该流程必须使用刚生成 Planning Graph 中的真实完整 ID，不得根据 label 猜测 ID。

- [ ] **Step 6: 运行真实 SafeSym parse/inject/solve**

Run:

```powershell
.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke --task-dir 'outputs/experiments/practice_automated_testing/location_pddl_v1_review' --safesym-root 'C:\Users\moon\Desktop\Projects\SafeSym' --rules 'C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json' --fast-downward 'C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py'
```

Expected: report 中 `safesym_parse_ready=true`、`base_plan_ready=true`。安全注入和 safe solve 也必须运行并如实
记录；如果当前 constraint rules 对纯 location domain 不插入检查，`safety_actions_inserted=false` 是可接受结果，
但 `safety_injection_ready` 和 `safe_plan_ready` 仍应为 true。

- [ ] **Step 7: 检查产物与工作区**

Run:

```powershell
git diff --check
git status --short
rg -n "checkout|cart|login|search|filter|payment" src/ai_web_explorer/safesym_bridge/location_pddl.py
```

Expected: `git diff --check` 无输出；源码领域 token 搜索无输出；工作区只包含本计划预期代码、测试、文档和本轮
新实验输出。不要提交 `location_pddl_v1_review` 实验目录，除非仓库现有实验产物政策明确要求审查样本入库。

- [ ] **Step 8: Commit 文档与 smoke fixture**

```powershell
git add tests/safesym_bridge/test_web_kobe_safesym_smoke.py docs/safesym-bridge.md
git commit -m "docs: verify SafeSym location planning workflow"
```

---

## Final Review Handoff

执行会话完成后必须向审查会话报告：

- 每个 commit SHA 和对应任务；
- 定向测试与完整非浏览器测试的精确结果；
- Location V1 domain/problem 路径；
- `projection_report.json` 中 projected/excluded edge 数量；
- SafeSym smoke report 的全部布尔状态；
- 实际 start/goal Planning node ID 和 Fast Downward 返回的 plan；
- `git status --short` 与 `git diff --check` 结果；
- 是否修改了计划外文件，以及原因。

审查会话负责独立检查实现、重新运行测试、核对没有领域硬编码，并决定是否接受到 main。执行会话不得自行处理
target matching、Visual Delta taxonomy、observer stabilization 或多分支探索。
