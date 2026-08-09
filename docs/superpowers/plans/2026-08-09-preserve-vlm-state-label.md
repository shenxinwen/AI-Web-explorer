# Preserve VLM State Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 防止节点 revisit 时，本地兜底名称覆盖已经接受的最早 VLM 状态名称。

**Architecture:** 在 `graph_manager.py` 内集中处理三个命名字段的合并。现有节点若已由 `visual_affordance_vlm` 命名，则整组保留；否则继续采用当前“新数据优先、旧数据兜底”的行为。

**Tech Stack:** Python、dataclasses、pytest

## Global Constraints

- 只修改节点命名字段的合并行为：`node_label`、`state_summary`、`naming_provenance`。
- 不修改节点 ID、节点匹配、embedding、业务动作、边记录或 PDDL 投影。
- 已接受的最早 VLM 名称优先于本地兜底名称。
- 本次不拆分节点查找与节点更新流程；该项只作为未来优化。

---

### Task 1: 按命名来源合并节点名称

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/graph_manager.py:55-65,118-150`
- Test: `tests/safesym_bridge/test_web_kobe_graph_manager.py`

**Interfaces:**
- Consumes: `WebKobeNode.naming_provenance` 中的 `source` 值，以及节点的 `node_label`、`state_summary`。
- Produces: `_merge_node_naming(existing: WebKobeNode, incoming: WebKobeNode) -> tuple[str | None, str | None, dict[str, Any] | None]`，供 `identify_or_add_node()` 使用。

- [ ] **Step 1: 写出失败的回归测试**

在 `tests/safesym_bridge/test_web_kobe_graph_manager.py` 中增加以下测试。测试名称可以保持如下写法，节点构造沿用现有 `_node()` 和 `replace()`：

```python
def test_identify_or_add_node_upgrades_fallback_naming_to_vlm():
    manager = WebKobeGraphManager(app="example")
    fallback = replace(
        _node("listing", {}),
        node_label="shopping",
        state_summary="Local fallback summary.",
        naming_provenance={"source": "deterministic_fallback"},
    )
    vlm_named = replace(
        _node("listing", {}),
        node_label="product_list",
        state_summary="Visible product list.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )

    manager.identify_or_add_node(fallback)
    manager.identify_or_add_node(vlm_named)

    node = manager.node_for_id("listing")
    assert node.node_label == "product_list"
    assert node.state_summary == "Visible product list."
    assert node.naming_provenance == {"source": "visual_affordance_vlm"}


def test_identify_or_add_node_preserves_first_vlm_naming_on_revisit():
    manager = WebKobeGraphManager(app="example")
    first_vlm = replace(
        _node("listing", {}),
        node_label="product_list",
        state_summary="Visible product list.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )
    local_revisit = replace(
        _node("listing", {}),
        node_label="shopping",
        state_summary="Local fallback summary.",
        naming_provenance={"source": "deterministic_fallback"},
    )
    later_vlm = replace(
        _node("listing", {}),
        node_label="different_product_state",
        state_summary="Different VLM summary.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )

    manager.identify_or_add_node(first_vlm)
    manager.identify_or_add_node(local_revisit)
    manager.identify_or_add_node(later_vlm)

    node = manager.node_for_id("listing")
    assert node.node_label == "product_list"
    assert node.state_summary == "Visible product list."
    assert node.naming_provenance == {"source": "visual_affordance_vlm"}


def test_identify_or_add_node_keeps_existing_non_vlm_merge_behavior():
    manager = WebKobeGraphManager(app="example")
    first = replace(
        _node("listing", {}),
        node_label="first_fallback",
        naming_provenance={"source": "deterministic_fallback"},
    )
    incoming = replace(
        _node("listing", {}),
        node_label="latest_fallback",
        naming_provenance={"source": "deterministic_fallback"},
    )

    manager.identify_or_add_node(first)
    manager.identify_or_add_node(incoming)

    node = manager.node_for_id("listing")
    assert node.node_label == "latest_fallback"
    assert node.naming_provenance == {"source": "deterministic_fallback"}
```

- [ ] **Step 2: 运行新增测试并确认旧实现失败**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_graph_manager.py -k "naming or vlm" -v
```

Expected: `preserves_first_vlm_naming_on_revisit` 失败，实际名称被更新为 `different_product_state`；另外两个测试通过。

- [ ] **Step 3: 实现最小命名合并函数**

在 `_merge_business_affordances()` 后增加：

```python
def _merge_node_naming(
    existing: WebKobeNode,
    incoming: WebKobeNode,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    existing_source = (existing.naming_provenance or {}).get("source")
    if existing_source == "visual_affordance_vlm":
        return (
            existing.node_label,
            existing.state_summary,
            existing.naming_provenance,
        )
    return (
        incoming.node_label or existing.node_label,
        incoming.state_summary or existing.state_summary,
        incoming.naming_provenance or existing.naming_provenance,
    )
```

在 `identify_or_add_node()` 找到 `existing` 后、调用 `replace()` 前解包：

```python
node_label, state_summary, naming_provenance = _merge_node_naming(
    existing,
    node,
)
```

并把 `replace()` 中原来的三个表达式替换为：

```python
node_label=node_label,
state_summary=state_summary,
naming_provenance=naming_provenance,
```

- [ ] **Step 4: 运行 graph manager 测试**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_graph_manager.py -v
```

Expected: 全部通过。

- [ ] **Step 5: 运行 explorer 命名相关测试**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_explorer.py -k "state_label or naming or revisit" -v
```

Expected: 全部通过，已有的 VLM 命名、无效标签兜底和 revisit 行为没有回归。

- [ ] **Step 6: 运行完整测试并检查工作区**

Run:

```powershell
pytest -q
git diff --check
git status --short
```

Expected: 测试全部通过；`git diff --check` 无输出；只有本任务涉及的两个文件发生变化。

- [ ] **Step 7: 提交实现**

```powershell
git add src/ai_web_explorer/grounded_web/graph_manager.py tests/safesym_bridge/test_web_kobe_graph_manager.py
git commit -m "Preserve VLM state labels on revisit"
```
