# Profile-Independent Exploration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Visual Affordance 候选生成和 target embedding matching 在没有 business profile 时仍能工作。

**Architecture:** 删除 Visual Affordance request 中未使用的 profile/planning 字段，并把 explorer 的候选生成门槛收窄为“存在 provider”。target matching 继续使用同一套 embedding、source 保护和 revisit evidence，只把缺失 planning transition 时的 facts 视为空列表。

**Tech Stack:** Python、dataclasses、pytest

## Global Constraints

- 不修改 profile verifier、PlanningState/PlanningTransition 数据结构、Visual Delta、graph schema、source matching、PDDL 或 Stagehand。
- 不调整 embedding 阈值、context marker、source node 保护或 known revisit evidence 门槛。
- 不处理 source 写入顺序、visit_count、Explorer 拆分或 embedding 缓存。
- 按 TDD 先证明现有 profile 依赖，再做最小实现。

---

### Task 1: 删除 Visual Affordance Request 的旧 Profile 字段

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/business_affordance.py:7-20`
- Modify: `tests/safesym_bridge/test_business_affordance.py`

**Interfaces:**
- Produces: `VisualAffordanceRequest(goal: str, current_screenshot_path: str, current_signature: dict[str, Any] | None = None, max_actions: int = 5)`。
- Preserves: `_prompt_for_request()` 的 JSON 内容和 `summarize_visual_affordances()` 行为。

- [ ] **Step 1: 更新测试构造方式并增加 prompt 隔离断言**

把 `tests/safesym_bridge/test_business_affordance.py` 中所有 `VisualAffordanceRequest(...)` 的 `profile=ecommerce_checkout_profile()` 和 `current_planning_facts=...` 参数删除。若该文件因此不再使用 `ecommerce_checkout_profile`，同步删除 import。

在现有 `test_visual_affordance_prompt_requests_top_level_state_label` 的 provider 中增加：

```python
assert "profile" not in payload
assert "current_planning_facts" not in payload
assert "planning_facts" not in json.dumps(payload)
```

另外增加接口回归测试：

```python
def test_visual_affordance_request_has_no_profile_or_planning_state_fields():
    field_names = {
        field.name for field in dataclasses.fields(VisualAffordanceRequest)
    }
    assert "profile" not in field_names
    assert "current_planning_facts" not in field_names
```

并在测试文件增加 `import dataclasses`。

- [ ] **Step 2: 运行 business affordance 测试，确认生产接口尚未完成清理**

Run:

```powershell
pytest tests/safesym_bridge/test_business_affordance.py -q
```

Expected: 新增接口回归测试失败，因为旧 dataclass 仍包含两个字段。

- [ ] **Step 3: 删除旧字段和 import**

在 `business_affordance.py`：

- 删除 `BusinessFlowProfile` import。
- 从 `VisualAffordanceRequest` 删除 `profile`。
- 从 `VisualAffordanceRequest` 删除 `current_planning_facts`。
- 保留 `goal`、`current_screenshot_path`、`current_signature`、`max_actions`。

目标结构：

```python
@dataclass(frozen=True)
class VisualAffordanceRequest:
    goal: str
    current_screenshot_path: str
    current_signature: dict[str, Any] | None = None
    max_actions: int = 5
```

- [ ] **Step 4: 运行 Task 1 测试**

Run:

```powershell
pytest tests/safesym_bridge/test_business_affordance.py -q
```

Expected: 全部通过。

---

### Task 2: 解除 Explorer 的候选生成和 Target Matching Profile 门槛

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/explorer.py:519-552,622-680`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes: Task 1 的精简 `VisualAffordanceRequest`。
- Preserves: `_match_existing_target_node(..., planning_transition: PlanningTransition | None, ...)` 签名。
- Produces: `planning_transition=None` 时使用空 planning facts 的 target summary。

- [ ] **Step 1: 写没有 profile 也能生成候选的失败测试**

在 `test_web_kobe_explorer.py` 增加：

```python
def test_record_source_business_affordances_does_not_require_business_profile():
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(current_screenshot_path)
        return _business_affordance_response("search_items")

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))

    explorer._record_source_business_affordances(
        source_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert provider_calls == ["outputs/before_0001.png"]
    assert [item.action_name for item in node.business_affordances] == [
        "search_items"
    ]
```

- [ ] **Step 2: 写没有 planning transition 也执行 target matching 的失败测试**

新增 `test_target_matching_runs_without_planning_transition`。参考现有 `test_target_matching_reuses_existing_business_state_node`，构造 `source` 与 `known` 之间已有 edge、known embedding 和相同 embedding provider，然后调用：

```python
matched_node, match = explorer._match_existing_target_node(
    target_node=_selection_node("new_candidate"),
    after=StateSnapshot(
        page_id="known",
        url="https://example.test/known",
        title="Known",
        signature={},
    ),
    after_interactables=[],
    planning_transition=None,
    source_node_id="source",
)

assert match is not None
assert match.status == "same"
assert matched_node.node_id == "known"
```

测试必须保留已知 edge，避免绕过 `_has_known_revisit_evidence()`。

- [ ] **Step 3: 运行新增测试并确认旧实现失败**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_explorer.py -k "does_not_require_business_profile or without_planning_transition" -v
```

Expected: 两个测试失败；候选为空，target match 为 `None`。

- [ ] **Step 4: 实现候选生成解耦**

在 `_record_source_business_affordances()`：

```python
if self.visual_delta_provider is None:
    return
```

删除 `active_facts` 的构造，并按 Task 1 的新接口创建 request：

```python
VisualAffordanceRequest(
    goal=self.goal,
    current_screenshot_path=before_screenshot_path,
    current_signature=before.signature,
    max_actions=self.max_candidates,
)
```

- [ ] **Step 5: 实现 target matching 解耦**

从 `_match_existing_target_node()` 的提前退出条件删除：

```python
or planning_transition is None
```

构建 summary 时使用：

```python
active_planning_facts=(
    planning_transition.post_facts
    if planning_transition is not None
    else []
),
```

不要改变后续 match、source protection 或 revisit evidence 逻辑。

- [ ] **Step 6: 运行定向测试**

Run:

```powershell
pytest tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: 全部通过。

- [ ] **Step 7: 搜索残留接口并运行完整回归**

Run:

```powershell
rg -n "VisualAffordanceRequest\(" src tests
rg -n "current_planning_facts|request\.profile" src tests
pytest -q --ignore=tests/test_local_shop_fixture.py
git diff --check
git status --short
```

Expected:

- 所有 request 构造都符合新接口。
- `current_planning_facts` 和 `request.profile` 无活跃引用。
- Python 回归全部通过（当前基线为 `309 passed, 2 skipped`）。
- `git diff --check` 无输出。
- 只修改计划列出的四个生产/测试文件；若测试 import 清理计入同一测试文件，不算偏离。

- [ ] **Step 8: 提交实现**

```powershell
git add src/ai_web_explorer/grounded_web/business_affordance.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_business_affordance.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "Decouple exploration from business profiles"
```
