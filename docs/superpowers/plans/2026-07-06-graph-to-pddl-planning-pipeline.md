# Graph to PDDL Planning Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SauceDemo-focused path that compiles `WebObservedGraph` into PDDL domain/problem files that can pass through SafeSym safety injection and be solved by Fast Downward.

**Architecture:** Add a focused `pddl_compiler.py` module that converts graph nodes, graph edges, and two SauceDemo form-fill actions into readable PDDL text. Keep CLI orchestration in `cli.py`, graph construction in existing modules, and external SafeSym/Fast Downward verification as an integration step outside the unit-test-only compiler.

**Tech Stack:** Python 3, dataclasses, pytest, existing `ai_web_explorer.safesym_bridge` modules, SafeSym external project for integration verification, Fast Downward external planner.

## Global Constraints

- First implementation is SauceDemo-specific.
- Do not implement generic website PDDL compilation.
- Do not implement LLM or embedding-based node merging.
- Do not integrate the main `ExploreLoop`.
- Do not implement automatic discovery of arbitrary form fields.
- Do not implement rich numeric reasoning.
- Do not store screenshot, DOM, or trace evidence.
- Preserve `order_place_confirm` as an action name so SafeSym constraint rules can match it.
- Represent cart count as `state_cart_count_positive`, not value-specific numeric predicates.
- Use test-driven development: failing test, minimal implementation, passing test, commit.

---

## File Structure

- Create `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`
  - Owns graph-to-PDDL conversion.
  - Exposes `compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts`.
  - Exposes `write_pddl_artifacts(graph: WebObservedGraph, output_dir: Path) -> PddlArtifacts`.
  - Contains small private helpers for predicate naming, precondition/effect mapping, and PDDL formatting.

- Create `tests/safesym_bridge/test_pddl_compiler.py`
  - Tests compiler behavior directly without shelling out to SafeSym or Fast Downward.
  - Checks actions, predicates, problem init, problem goal, and cart-count representation.

- Modify `src/ai_web_explorer/safesym_bridge/cli.py`
  - Adds `pddl` subcommand.
  - Builds SauceDemo graph from current fixed MVP transitions.
  - Writes `domain.pddl` and `problem.pddl`.

- Modify `tests/safesym_bridge/test_cli.py`
  - Adds CLI test for `pddl` subcommand.

- Optionally create `docs/safesym_bridge/graph_to_pddl.md`
  - Short operator note after the implementation works.
  - This is optional because the existing design/spec already documents the shape.

---

### Task 1: Add PDDL compiler data structure and problem skeleton

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`
- Create: `tests/safesym_bridge/test_pddl_compiler.py`

**Interfaces:**
- Consumes: `WebObservedGraph` from `ai_web_explorer.safesym_bridge.observed_graph`.
- Produces:
  - `PddlArtifacts(domain: str, problem: str)`
  - `compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts`

- [ ] **Step 1: Write the failing test**

Add this test file:

```python
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import compile_graph_to_pddl
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def _compile_saucedemo():
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    return compile_graph_to_pddl(graph)


def test_compile_graph_to_pddl_returns_domain_and_problem_text():
    artifacts = _compile_saucedemo()

    assert artifacts.domain.startswith("(define (domain saucedemo)")
    assert artifacts.problem.startswith("(define (problem saucedemo-problem)")
    assert "(:domain saucedemo)" in artifacts.problem
    assert "(:objects" in artifacts.problem
    assert "login inventory cart checkout_info checkout_overview checkout_complete" in artifacts.problem
    assert "(:init" in artifacts.problem
    assert "(at login)" in artifacts.problem
    assert "(and" in artifacts.problem
    assert "(at checkout_complete)" in artifacts.problem
    assert "(state_order_created)" in artifacts.problem
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_returns_domain_and_problem_text -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `pddl_compiler.py` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_web_explorer.safesym_bridge.observed_graph import WebObservedGraph


@dataclass(frozen=True)
class PddlArtifacts:
    domain: str
    problem: str


def compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts:
    domain = "\n".join(
        [
            f"(define (domain {graph.app})",
            "  (:requirements :strips)",
            "  (:predicates",
            "    (at ?page)",
            "    (state_order_created)",
            "  )",
            ")",
            "",
        ]
    )
    problem = "\n".join(
        [
            f"(define (problem {graph.app}-problem)",
            f"  (:domain {graph.app})",
            "  (:objects",
            "    login inventory cart checkout_info checkout_overview checkout_complete",
            "  )",
            "  (:init",
            f"    (at {graph.start_node})",
            "  )",
            "  (:goal",
            "    (and",
            "      (at checkout_complete)",
            "      (state_order_created)",
            "    )",
            "  )",
            ")",
            "",
        ]
    )
    return PddlArtifacts(domain=domain, problem=problem)


def write_pddl_artifacts(graph: WebObservedGraph, output_dir: Path) -> PddlArtifacts:
    artifacts = compile_graph_to_pddl(graph)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "domain.pddl").write_text(artifacts.domain, encoding="utf-8")
    (output_dir / "problem.pddl").write_text(artifacts.problem, encoding="utf-8")
    return artifacts
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_returns_domain_and_problem_text -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/pddl_compiler.py tests/safesym_bridge/test_pddl_compiler.py
git commit -m "feat: add graph pddl compiler skeleton"
```

---

### Task 2: Map graph state into stable PDDL predicates

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`
- Modify: `tests/safesym_bridge/test_pddl_compiler.py`

**Interfaces:**
- Consumes: `compile_graph_to_pddl(graph: WebObservedGraph) -> PddlArtifacts`
- Produces:
  - `state_is_logged_in`
  - `state_username_filled`
  - `state_password_filled`
  - `state_checkout_info_filled`
  - `state_checkout_started`
  - `state_order_review_ready`
  - `state_order_created`
  - `state_cart_count_positive`

- [ ] **Step 1: Write the failing test**

Append to `tests/safesym_bridge/test_pddl_compiler.py`:

```python
def test_compile_graph_to_pddl_declares_stable_state_predicates():
    artifacts = _compile_saucedemo()

    expected_predicates = [
        "(state_is_logged_in)",
        "(state_username_filled)",
        "(state_password_filled)",
        "(state_checkout_info_filled)",
        "(state_checkout_started)",
        "(state_order_review_ready)",
        "(state_order_created)",
        "(state_cart_count_positive)",
    ]
    for predicate in expected_predicates:
        assert predicate in artifacts.domain

    assert "state_cart_count_is_value" not in artifacts.domain
    assert "state_cart_count_is_value" not in artifacts.problem
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_declares_stable_state_predicates -v
```

Expected: FAIL because the skeleton only declares `state_order_created`.

- [ ] **Step 3: Implement predicate mapping helpers**

Update `pddl_compiler.py` with these helpers:

```python
BOOLEAN_STATE_PREDICATES = {
    "$.is_logged_in": "state_is_logged_in",
    "$.username_filled": "state_username_filled",
    "$.password_filled": "state_password_filled",
    "$.checkout_info_filled": "state_checkout_info_filled",
    "$.checkout_started": "state_checkout_started",
    "$.order_review_ready": "state_order_review_ready",
    "$.order_created": "state_order_created",
}

CART_COUNT_POSITIVE = "state_cart_count_positive"


def _state_predicates_for_graph(graph: WebObservedGraph) -> list[str]:
    predicates: set[str] = set()
    for node in graph.nodes:
        for path in node.state_schema:
            if path == "$.cart_count":
                predicates.add(CART_COUNT_POSITIVE)
            elif path in BOOLEAN_STATE_PREDICATES:
                predicates.add(BOOLEAN_STATE_PREDICATES[path])
    return sorted(predicates)
```

Then change `compile_graph_to_pddl()` so `(:predicates ...)` includes:

```python
state_predicates = _state_predicates_for_graph(graph)
predicate_lines = ["    (at ?page)"] + [
    f"    ({predicate})" for predicate in state_predicates
]
```

Build the domain using `predicate_lines`.

- [ ] **Step 4: Run the predicate test**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_declares_stable_state_predicates -v
```

Expected: PASS.

- [ ] **Step 5: Run all compiler tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/pddl_compiler.py tests/safesym_bridge/test_pddl_compiler.py
git commit -m "feat: map graph state to pddl predicates"
```

---

### Task 3: Generate graph edge actions and SauceDemo fill actions

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`
- Modify: `tests/safesym_bridge/test_pddl_compiler.py`

**Interfaces:**
- Consumes:
  - `WebObservedGraph.edges`
  - edge `preconditions`
  - edge `effects`
- Produces:
  - PDDL actions for graph edges.
  - PDDL actions `login_fill_credentials` and `checkout_info_fill`.

- [ ] **Step 1: Write the failing action coverage test**

Append:

```python
def test_compile_graph_to_pddl_emits_expected_actions():
    artifacts = _compile_saucedemo()

    expected_actions = [
        "(:action login_fill_credentials",
        "(:action login_submit",
        "(:action product_add_to_cart",
        "(:action cart_open",
        "(:action cart_checkout_start",
        "(:action checkout_info_fill",
        "(:action checkout_info_submit",
        "(:action order_place_confirm",
    ]
    for action in expected_actions:
        assert action in artifacts.domain
```

- [ ] **Step 2: Write the failing reachability test**

Append:

```python
def test_fill_actions_make_submit_preconditions_reachable():
    artifacts = _compile_saucedemo()

    assert "(:action login_fill_credentials" in artifacts.domain
    assert "(state_username_filled)" in artifacts.domain
    assert "(state_password_filled)" in artifacts.domain
    assert "(:action checkout_info_fill" in artifacts.domain
    assert "(state_checkout_info_filled)" in artifacts.domain

    login_submit_start = artifacts.domain.index("(:action login_submit")
    login_submit_chunk = artifacts.domain[login_submit_start : login_submit_start + 500]
    assert "(state_username_filled)" in login_submit_chunk
    assert "(state_password_filled)" in login_submit_chunk

    checkout_submit_start = artifacts.domain.index("(:action checkout_info_submit")
    checkout_submit_chunk = artifacts.domain[
        checkout_submit_start : checkout_submit_start + 500
    ]
    assert "(state_checkout_info_filled)" in checkout_submit_chunk
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_emits_expected_actions tests\safesym_bridge\test_pddl_compiler.py::test_fill_actions_make_submit_preconditions_reachable -v
```

Expected: FAIL because the compiler does not emit actions yet.

- [ ] **Step 4: Add condition/effect mapping helpers**

Add:

```python
def _predicate_for_condition(path: str, value: object) -> tuple[str, bool] | None:
    if path == "$.cart_count":
        if isinstance(value, (int, float)):
            return CART_COUNT_POSITIVE, value > 0
        return None
    if path in BOOLEAN_STATE_PREDICATES and isinstance(value, bool):
        return BOOLEAN_STATE_PREDICATES[path], value
    return None


def _format_positive_atoms(atoms: list[str], indent: str) -> list[str]:
    return [f"{indent}({atom})" for atom in atoms]


def _format_effect_atoms(add_atoms: list[str], delete_atoms: list[str], indent: str) -> list[str]:
    lines = [f"{indent}({atom})" for atom in add_atoms]
    lines.extend(f"{indent}(not ({atom}))" for atom in delete_atoms)
    return lines
```

Add action formatter:

```python
def _format_action(
    *,
    name: str,
    preconditions: list[str],
    add_effects: list[str],
    delete_effects: list[str],
) -> str:
    precondition_lines = _format_positive_atoms(preconditions, "      ")
    effect_lines = _format_effect_atoms(add_effects, delete_effects, "      ")
    return "\n".join(
        [
            f"  (:action {name}",
            "    :precondition",
            "      (and",
            *precondition_lines,
            "      )",
            "    :effect",
            "      (and",
            *effect_lines,
            "      )",
            "  )",
        ]
    )
```

- [ ] **Step 5: Add fill action generation**

Add:

```python
def _saucedemo_fill_actions() -> list[str]:
    return [
        _format_action(
            name="login_fill_credentials",
            preconditions=["at login"],
            add_effects=["state_username_filled", "state_password_filled"],
            delete_effects=[],
        ),
        _format_action(
            name="checkout_info_fill",
            preconditions=["at checkout_info"],
            add_effects=["state_checkout_info_filled"],
            delete_effects=[],
        ),
    ]
```

Important: `_format_positive_atoms()` wraps each atom in parentheses, so passing `"at login"` produces `(at login)`.

- [ ] **Step 6: Add graph edge action generation**

Add:

```python
def _edge_action_preconditions(edge) -> list[str]:
    atoms = [f"at {edge.source}"]
    for condition in edge.preconditions:
        mapped = _predicate_for_condition(condition["path"], condition["value"])
        if mapped is None:
            continue
        predicate, is_positive = mapped
        if is_positive:
            atoms.append(predicate)
    return atoms


def _edge_action_effects(edge) -> tuple[list[str], list[str]]:
    add_effects: list[str] = []
    delete_effects: list[str] = []
    if edge.source != edge.target:
        delete_effects.append(f"at {edge.source}")
        add_effects.append(f"at {edge.target}")
    else:
        add_effects.append(f"at {edge.target}")

    for effect in edge.effects:
        if effect.get("op") != "set":
            continue
        mapped = _predicate_for_condition(effect["path"], effect["value"])
        if mapped is None:
            continue
        predicate, is_positive = mapped
        if is_positive:
            add_effects.append(predicate)
        else:
            delete_effects.append(predicate)
    return add_effects, delete_effects


def _graph_edge_actions(graph: WebObservedGraph) -> list[str]:
    actions: list[str] = []
    for edge in graph.edges:
        add_effects, delete_effects = _edge_action_effects(edge)
        actions.append(
            _format_action(
                name=edge.semantic_action,
                preconditions=_edge_action_preconditions(edge),
                add_effects=add_effects,
                delete_effects=delete_effects,
            )
        )
    return actions
```

Then include actions in the domain:

```python
actions = _saucedemo_fill_actions() + _graph_edge_actions(graph)
```

Insert them before the final domain `)`.

- [ ] **Step 7: Run action tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py::test_compile_graph_to_pddl_emits_expected_actions tests\safesym_bridge\test_pddl_compiler.py::test_fill_actions_make_submit_preconditions_reachable -v
```

Expected: PASS.

- [ ] **Step 8: Run all compiler tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/pddl_compiler.py tests/safesym_bridge/test_pddl_compiler.py
git commit -m "feat: compile observed graph actions to pddl"
```

---

### Task 4: Write PDDL artifacts through the CLI

**Files:**
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Modify: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Consumes:
  - `write_pddl_artifacts(graph: WebObservedGraph, output_dir: Path) -> PddlArtifacts`
  - `build_observed_graph(app, start_node, transitions)`
  - `build_saucedemo_mvp_transitions()`
- Produces:
  - CLI command `pddl --output <dir>`
  - `domain.pddl`
  - `problem.pddl`

- [ ] **Step 1: Write the failing CLI test**

Append to `tests/safesym_bridge/test_cli.py`:

```python
def test_main_pddl_subcommand_writes_domain_and_problem(tmp_path):
    output_dir = tmp_path / "graph_pddl"

    exit_code = main(["pddl", "--output", str(output_dir)])

    assert exit_code == 0
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    problem = (output_dir / "problem.pddl").read_text(encoding="utf-8")
    assert "(define (domain saucedemo)" in domain
    assert "(:action order_place_confirm" in domain
    assert "(:domain saucedemo)" in problem
    assert "(at login)" in problem
    assert "(state_order_created)" in problem
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_cli.py::test_main_pddl_subcommand_writes_domain_and_problem -v
```

Expected: FAIL because `pddl` is not a known subcommand.

- [ ] **Step 3: Modify CLI imports**

Add imports:

```python
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
```

- [ ] **Step 4: Add helper function**

Add near `write_fixed_fsm()`:

```python
def write_saucedemo_pddl(output_dir: Path) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    write_pddl_artifacts(graph, output_dir)
    return output_dir
```

- [ ] **Step 5: Add parser branch**

Add subparser:

```python
pddl_parser = subparsers.add_parser(
    "pddl",
    help="Write SauceDemo graph-derived PDDL domain/problem files.",
)
pddl_parser.add_argument(
    "--output",
    type=Path,
    default=Path("outputs/safesym_e2e/graph_pddl"),
    help="Directory to write domain.pddl and problem.pddl.",
)
```

Add branch before the default fixed FSM branch:

```python
elif args.mode == "pddl":
    output_path = write_saucedemo_pddl(args.output)
```

- [ ] **Step 6: Run the CLI test**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_cli.py::test_main_pddl_subcommand_writes_domain_and_problem -v
```

Expected: PASS.

- [ ] **Step 7: Run all bridge tests**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge -v
```

Expected: all current tests pass, with the existing optional browser smoke test skipped unless explicitly enabled.

- [ ] **Step 8: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_cli.py
git commit -m "feat: add graph pddl cli output"
```

---

### Task 5: Verify SafeSym injection and Fast Downward solve

**Files:**
- Modify only if needed after observing failures:
  - `src/ai_web_explorer/safesym_bridge/pddl_compiler.py`
  - `tests/safesym_bridge/test_pddl_compiler.py`

**Interfaces:**
- Consumes:
  - `outputs/safesym_e2e/graph_pddl/domain.pddl`
  - `outputs/safesym_e2e/graph_pddl/problem.pddl`
  - SafeSym `configs/constraint_rules.json`
  - Fast Downward script at `C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py`
- Produces:
  - evidence that SafeSym injection succeeds;
  - evidence that Fast Downward finds a plan.

- [ ] **Step 1: Generate PDDL artifacts**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli pddl --output outputs\safesym_e2e\graph_pddl
```

Expected:

```text
Wrote output to outputs\safesym_e2e\graph_pddl
```

- [ ] **Step 2: Run SafeSym safety injection**

Use a short PowerShell command or Python one-liner that imports SafeSym from:

```text
C:\Users\moon\Desktop\Projects\SafeSym
```

The script should:

1. read `outputs\safesym_e2e\graph_pddl\domain.pddl`;
2. read `outputs\safesym_e2e\graph_pddl\problem.pddl`;
3. load `C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json`;
4. run `SafetyCompiler.from_file(...).compile(...)`;
5. write injected artifacts to `outputs\safesym_e2e\graph_pddl_safe`.

Expected:

```text
safe domain written
safe problem written
```

- [ ] **Step 3: Run Fast Downward**

Run:

```powershell
& "C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py" outputs\safesym_e2e\graph_pddl_safe\domain.pddl outputs\safesym_e2e\graph_pddl_safe\problem.pddl --search "astar(lmcut())"
```

Expected:

```text
Solution found.
```

or another Fast Downward success message with return code `0`.

- [ ] **Step 4: Inspect plan ordering**

Open the generated plan file, commonly `sas_plan`, and confirm these ordering constraints:

```text
login_fill_credentials
login_submit
checkout_info_fill
checkout_info_submit
```

Also confirm `order_place_confirm` appears only after injected safety/support/check actions required by SafeSym.

- [ ] **Step 5: If Fast Downward fails because of PDDL syntax**

Add or adjust compiler tests to reproduce the failing syntax shape first. Then fix `pddl_compiler.py` and rerun:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge\test_pddl_compiler.py -v
```

Commit with:

```powershell
git add src/ai_web_explorer/safesym_bridge/pddl_compiler.py tests/safesym_bridge/test_pddl_compiler.py
git commit -m "fix: produce planner-valid graph pddl"
```

- [ ] **Step 6: If SafeSym injection does not constrain `order_place_confirm`**

Do not rename `order_place_confirm`. Inspect whether the action syntax changed enough that the injector cannot parse or match it. Add a compiler test that asserts:

```python
assert "(:action order_place_confirm" in artifacts.domain
```

Then adjust formatting or action naming only.

- [ ] **Step 7: Final full verification**

Run:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m pytest tests\safesym_bridge -v
```

Expected: all current tests pass.

Then rerun:

```powershell
$env:PYTHONPATH="D:\GitHUb\ai-web-explorer-main\.worktrees\browser-observed-safesym-bridge\src"; & "D:\GitHUb\ai-web-explorer-main\.venv\Scripts\python.exe" -m ai_web_explorer.safesym_bridge.cli pddl --output outputs\safesym_e2e\graph_pddl
```

Expected: PDDL artifacts are regenerated successfully.

- [ ] **Step 8: Commit final verification docs if added**

If a short documentation note is created:

```powershell
git add docs/safesym_bridge/graph_to_pddl.md
git commit -m "docs: document graph pddl verification"
```

If no documentation file is added and no code changed during Task 5, do not create an empty commit.

---

## Completion Checklist

- [ ] `tests/safesym_bridge/test_pddl_compiler.py` covers PDDL domain/problem generation.
- [ ] `tests/safesym_bridge/test_cli.py` covers `pddl --output`.
- [ ] `src/ai_web_explorer/safesym_bridge/pddl_compiler.py` has one clear responsibility.
- [ ] `src/ai_web_explorer/safesym_bridge/cli.py` remains a thin command dispatcher.
- [ ] Existing bridge tests pass.
- [ ] Raw graph-derived PDDL is generated.
- [ ] SafeSym safety injection succeeds.
- [ ] Fast Downward finds a plan.
- [ ] The plan includes form-fill actions before submit actions.
- [ ] `order_place_confirm` remains safety-constrained.
