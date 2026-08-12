# Frontier Replay and Surface PDDL V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace path-ordered planning with an observed surface-transition PDDL model and continue open exploration from deeper under-explored surfaces through reset-and-verified-replay.

**Architecture:** Keep `execution_events` and Trace PDDL unchanged for audit. Add a small replay contract to the automation boundary, select a reachable frontier from the already aggregated `WebKobeGraph`, reset to the configured entry URL, replay the shortest observed path one atomic action at a time, and abort on the first state mismatch. Compile the aggregated graph—not the ordered trace—into Surface PDDL, using one synthetic `executed` marker per transition so same-surface actions remain legal independent siblings without inventing business facts.

**Tech Stack:** Python 3.11+, dataclasses, asyncio, Playwright, Stagehand adapter, pytest, existing SafeSym bridge.

## Global Constraints

- Preserve open-ended exploration; no purchase-specific, shopping-specific, filter-specific, or sort-specific branching in production code.
- Keep Trace PDDL as a separate audit artifact and do not change its semantics.
- Replay is best effort and fail-closed: a mismatch aborts the replay attempt and must not create a successful graph edge.
- Execute and validate one atomic action at a time; do not use a multi-step Stagehand agent call for replay.
- V1 state validation reuses existing node identification/state matching; do not add new embedding models, screenshot matching algorithms, schema-delta reasoning, or business facts.
- Only successful observed graph edges may enter Surface PDDL.
- Do not require arbitrary browser backtracking; V1 recovery is entry reset plus replay.
- Keep existing CLI behavior unless the new frontier replay option is explicitly enabled.

---

## File Structure

- Modify `src/ai_web_explorer/grounded_web/automation_backend.py`: add the reset operation required by replay.
- Modify `src/ai_web_explorer/grounded_web/playwright_backend.py`: implement entry reset with `page.goto`.
- Modify `src/ai_web_explorer/grounded_web/stagehand_backend.py`: delegate reset to the underlying browser backend while retaining Stagehand for atomic replay actions.
- Create `src/ai_web_explorer/grounded_web/frontier_replay.py`: pure graph path/frontier selection plus replay result types and orchestration.
- Modify `src/ai_web_explorer/grounded_web/explorer.py`: expose current-node validation and a single replay action operation without recording replay as a newly explored transition.
- Modify `src/ai_web_explorer/grounded_web/controller.py`: when the current node is exhausted, attempt one eligible frontier replay before stopping.
- Modify `src/ai_web_explorer/safesym_bridge/browser_runner.py`: pass `start_url` and the opt-in replay setting to the controller and persist replay metrics.
- Create `src/ai_web_explorer/safesym_bridge/surface_pddl.py`: compile aggregated observed edges into minimal Surface PDDL.
- Modify `src/ai_web_explorer/safesym_bridge/cli.py`: expose opt-in frontier replay and Surface PDDL output.
- Add focused unit and integration tests under `tests/safesym_bridge/`.

---

### Task 1: Add a fail-closed browser reset contract

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/automation_backend.py`
- Modify: `src/ai_web_explorer/grounded_web/playwright_backend.py`
- Modify: `src/ai_web_explorer/grounded_web/stagehand_backend.py`
- Test: `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`
- Test: `tests/safesym_bridge/test_stagehand_backend.py`

**Interfaces:**
- Produces: `AutomationBackend.reset_to(url: str) -> Awaitable[bool]`.
- Contract: success means navigation was attempted and the page settled; it does not mean the expected logical node was reached.

- [ ] **Step 1: Write failing adapter reset tests**

Add a fake page that records `goto` calls and assert:

```python
@pytest.mark.anyio
async def test_reset_to_navigates_to_entry_and_settles():
    page = FakePage()
    adapter = WebKobePlaywrightAdapter(page, app_name="fake")

    assert await adapter.reset_to("https://example.test/start") is True
    assert page.goto_calls == [
        ("https://example.test/start", "domcontentloaded", 5000)
    ]
```

Add failure coverage asserting `False` and a `reset_error:<ExceptionType>` error string when `goto` raises.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -k reset_to -v
```

Expected: FAIL because `reset_to` is absent.

- [ ] **Step 3: Implement the minimal reset operation**

Add to the protocol:

```python
async def reset_to(self, url: str) -> bool: ...
```

Implement in `WebKobePlaywrightAdapter` with:

```python
async def reset_to(self, url: str) -> bool:
    self.last_execution_error = None
    try:
        await self.page.goto(url, wait_until="domcontentloaded", timeout=5000)
        await self.page.wait_for_timeout(100)
        return True
    except Exception as exc:
        return self._fail_execution(f"reset_error:{type(exc).__name__}")
```

In `StagehandAutomationBackend`, delegate to `base_backend.reset_to(url)`, copy `last_execution_error`, and set metadata with `stagehand_execution_mode="entry_reset"`.

- [ ] **Step 4: Run reset tests**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -k reset_to -v
pytest tests/safesym_bridge/test_stagehand_backend.py -k reset -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/automation_backend.py src/ai_web_explorer/grounded_web/playwright_backend.py src/ai_web_explorer/grounded_web/stagehand_backend.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_stagehand_backend.py
git commit -m "feat: add entry reset contract for replay"
```

---

### Task 2: Select reachable frontiers and shortest observed replay paths

**Files:**
- Create: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`

**Interfaces:**
- Produces: `ReplayStep(edge_id: str, source_node_id: str, target_node_id: str, action: BrowserAction)`.
- Produces: `FrontierTarget(node_id: str, path: tuple[ReplayStep, ...], untried_action_ids: tuple[str, ...])`.
- Produces: `select_frontier(graph: WebKobeGraph, *, blocked_node_ids: Collection[str] = ()) -> FrontierTarget | None`.
- Only edges with successful execution traces and controller-success statuses are traversable.

- [ ] **Step 1: Write failing pure graph tests**

Cover these exact cases:

```python
def test_select_frontier_returns_shortest_reachable_under_explored_node():
    graph = graph_with_paths(
        ("start", "a", "open_a"),
        ("start", "b", "open_b"),
        ("a", "deep", "open_deep"),
        frontier_actions={"b": ["inspect_b"], "deep": ["continue_deep"]},
    )
    target = select_frontier(graph)
    assert target is not None
    assert target.node_id == "b"
    assert [step.target_node_id for step in target.path] == ["b"]


def test_select_frontier_ignores_failed_edges_and_blocked_nodes():
    ...


def test_select_frontier_returns_none_when_every_reachable_node_is_exhausted():
    ...
```

The fixture must compute untried actions from `node.business_affordances` minus outgoing edge action identities, matching existing `_frontier_metrics_for_graph` semantics.

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
pytest tests/safesym_bridge/test_frontier_replay.py -v
```

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement BFS path selection**

Use a queue from `graph.start_node_id`. Build adjacency only from successful aggregated `graph.edges`. Sort edges by `edge_id` for deterministic tests. A node qualifies when it has at least one business affordance whose canonical action identity has no outgoing attempt from that source. Return the first qualifying non-start node not in `blocked_node_ids`.

Do not rank by business semantics in V1. The BFS choice is deliberately small and deterministic.

- [ ] **Step 4: Run the pure tests**

Run:

```powershell
pytest tests/safesym_bridge/test_frontier_replay.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/frontier_replay.py tests/safesym_bridge/test_frontier_replay.py
git commit -m "feat: select replayable exploration frontiers"
```

---

### Task 3: Execute reset-and-replay with per-step state validation

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/frontier_replay.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Test: `tests/safesym_bridge/test_frontier_replay.py`
- Test: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Produces: `ReplayResult(success: bool, reached_node_id: str | None, failed_edge_id: str | None, reason: str, completed_steps: int)`.
- Produces: `FrontierReplayRunner.replay(target: FrontierTarget, *, start_url: str) -> Awaitable[ReplayResult]`.
- Consumes from explorer: `validate_current_node(expected_node_id: str) -> Awaitable[bool]` and `execute_replay_action(action: BrowserAction) -> Awaitable[bool]`.
- Replay must not call `WebKobeGraphManager.add_edge`; replay is navigation evidence, not a new exploration event.

- [ ] **Step 1: Write failing replay behavior tests**

Use a fake replay port with recorded calls and cover:

```python
@pytest.mark.anyio
async def test_replay_resets_executes_and_validates_every_step():
    port = FakeReplayPort(validations=[True, True, True])
    result = await FrontierReplayRunner(port).replay(
        target_with_two_steps(),
        start_url="https://example.test/start",
    )
    assert result.success is True
    assert port.calls == [
        ("reset", "https://example.test/start"),
        ("validate", "start"),
        ("execute", "open_listing"),
        ("validate", "listing"),
        ("execute", "open_product"),
        ("validate", "product"),
    ]


@pytest.mark.anyio
async def test_replay_aborts_before_next_action_on_target_mismatch():
    port = FakeReplayPort(validations=[True, False])
    result = await FrontierReplayRunner(port).replay(...)
    assert result.success is False
    assert result.reason == "target_state_mismatch"
    assert "open_product" not in port.executed_action_ids
```

Also cover reset failure, start-state mismatch, and action execution failure.

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
pytest tests/safesym_bridge/test_frontier_replay.py -k replay -v
```

Expected: FAIL because the runner is absent.

- [ ] **Step 3: Add the minimal explorer replay port**

`execute_replay_action` delegates to `adapter.execute(action)` and does nothing else.

`validate_current_node` must:

```python
async def validate_current_node(self, expected_node_id: str) -> bool:
    snapshot = await self.adapter.observe_state()
    interactables = await self.adapter.list_interactables(snapshot)
    draft = self.semantic_assistor.describe_state(
        snapshot=snapshot,
        interactables=interactables,
    )
    if draft.node_id == expected_node_id:
        self._current_node_id = expected_node_id
        return True
    match = self._match_current_state(
        before=snapshot,
        before_interactables=interactables,
    )
    if match is not None and match.status == "same" and match.node_id == expected_node_id:
        self._current_node_id = expected_node_id
        return True
    return False
```

V1 deliberately does not ask a new VLM question during validation.

- [ ] **Step 4: Implement fail-closed replay orchestration**

The runner order must be reset, validate start, then for each edge execute and validate target. Return immediately on the first failure. Do not retry in V1; retries obscure whether the path is stable.

- [ ] **Step 5: Run replay and explorer tests**

Run:

```powershell
pytest tests/safesym_bridge/test_frontier_replay.py -v
pytest tests/safesym_bridge/test_web_kobe_explorer.py -k "validate_current_node or replay" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/frontier_replay.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: verify every step of frontier replay"
```

---

### Task 4: Continue exploration after current-state exhaustion

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/controller.py`
- Modify: `src/ai_web_explorer/safesym_bridge/browser_runner.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_web_kobe_controller.py`
- Test: `tests/safesym_bridge/test_browser_runner.py`
- Test: `tests/safesym_bridge/test_cli.py`

**Interfaces:**
- Extend controller constructor with `frontier_replay_runner: FrontierReplayRunner | None = None` and `start_url: str | None = None`.
- Add CLI flag `--frontier-replay` defaulting to false.
- Persist meta keys: `replay_attempt_count`, `replay_success_count`, `replay_failure_count`, `last_replay_reason`, and `blocked_replay_node_ids`.

- [ ] **Step 1: Write failing controller tests**

Cover:

```python
@pytest.mark.anyio
async def test_controller_replays_frontier_instead_of_stopping_on_exhaustion():
    explorer = ExhaustedThenProductiveExplorer()
    replay = SuccessfulReplayRunner(target_node_id="listing")
    result = await WebKobeExplorationController(
        explorer,
        frontier_replay_runner=replay,
        start_url="https://example.test/start",
    ).run(max_steps=3)
    assert replay.call_count == 1
    assert result.graph.meta["replay_success_count"] == 1
    assert result.summary.stop_reason == "max_steps"
```

Also assert a failed target is blocked for the remainder of the run and the controller stops with `frontier_replay_exhausted` when no eligible target remains.

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_controller.py -k frontier_replay -v
```

Expected: FAIL because controller integration is absent.

- [ ] **Step 3: Integrate replay at the exhaustion boundary**

When `graph.total_steps_completed == previous_completed` and `last_step_kind == "current_state_exhausted"`:

1. If replay is disabled, retain the existing stop behavior.
2. Call `select_frontier` excluding the in-run blocked set.
3. If no target exists, stop with `frontier_replay_exhausted`.
4. Attempt replay once.
5. On failure, block that target, update metrics, and look for another target on the next controller iteration without adding an edge.
6. On success, update metrics and continue normal `explore_one_step()` from the reached frontier.

- [ ] **Step 4: Wire the opt-in CLI and browser runner**

Add `frontier_replay: bool = False` to the generic Stagehand runner. When true, construct `FrontierReplayRunner(explorer)` and pass the configured `start_url` to the controller. The Stagehand adapter remains the action executor; no alternate Playwright replay path is introduced.

- [ ] **Step 5: Run focused integration tests**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_controller.py -v
pytest tests/safesym_bridge/test_browser_runner.py -k frontier_replay -v
pytest tests/safesym_bridge/test_cli.py -k frontier_replay -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/grounded_web/controller.py src/ai_web_explorer/safesym_bridge/browser_runner.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_browser_runner.py tests/safesym_bridge/test_cli.py
git commit -m "feat: continue exploration through verified frontier replay"
```

---

### Task 5: Compile minimal non-linear Surface PDDL

**Files:**
- Create: `src/ai_web_explorer/safesym_bridge/surface_pddl.py`
- Modify: `src/ai_web_explorer/safesym_bridge/cli.py`
- Test: `tests/safesym_bridge/test_surface_pddl.py`
- Test: `tests/safesym_bridge/test_web_kobe_safesym_smoke.py`

**Interfaces:**
- Produces: `compile_surface_domain(graph: WebKobeGraph, *, domain_name: str = "web_kobe_surface") -> SurfaceDomainProjection`.
- Produces: `compile_surface_problem(graph: WebKobeGraph, *, goal_node_id: str, problem_name: str = "web_kobe_surface_problem") -> SurfaceProblemProjection`.
- Domain predicates: `(at ?surface - surface)` and `(executed ?transition - transition)` only.
- One transition constant and one grounded action per successful aggregated `graph.edges` entry.

- [ ] **Step 1: Write failing non-linearity tests**

Construct a graph whose ordered events are `filter`, `clear`, `sort`, `open_product`, while aggregated edges have all first three sourced from `shopping`. Assert:

```python
def test_surface_domain_uses_observed_sources_not_trace_order():
    projection = compile_surface_domain(surface_graph_fixture())
    assert "(:precondition (and (at shopping))" in action_block(
        projection.domain, "filter"
    )
    assert "(:precondition (and (at shopping))" in action_block(
        projection.domain, "sort"
    )
    assert "checkpoint" not in projection.domain
```

For a same-surface edge, assert the effect adds its `executed` marker and does not delete `(at shopping)`. For a cross-surface edge, assert it deletes the source and adds the target. Assert failed edges are excluded.

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
pytest tests/safesym_bridge/test_surface_pddl.py -v
```

Expected: FAIL because the compiler is absent.

- [ ] **Step 3: Implement the compiler by adapting stable naming from Location PDDL**

Render same-surface actions as:

```lisp
(:action filter_on_shopping
  :parameters ()
  :precondition (and (at shopping))
  :effect (and
    (executed transition_filter_on_shopping)))
```

Render cross-surface actions as:

```lisp
(:action open_product_from_shopping
  :parameters ()
  :precondition (and (at shopping))
  :effect (and
    (not (at shopping))
    (at product_detail)
    (executed transition_open_product_from_shopping)))
```

The synthetic marker is bookkeeping only; do not use it as another action's precondition.

- [ ] **Step 4: Add CLI artifact generation and SafeSym smoke coverage**

Add a `surface` PDDL mode/output sibling to existing trace/location modes. Smoke-test parse, inject, base solve, and safe solve using a graph with sibling self-loop actions and a two-edge deep path.

- [ ] **Step 5: Run PDDL tests**

Run:

```powershell
pytest tests/safesym_bridge/test_surface_pddl.py -v
pytest tests/safesym_bridge/test_web_kobe_safesym_smoke.py -k surface -v
```

Expected: PASS, with the SafeSym plan reaching the requested deep surface without trace checkpoints.

- [ ] **Step 6: Commit**

```powershell
git add src/ai_web_explorer/safesym_bridge/surface_pddl.py src/ai_web_explorer/safesym_bridge/cli.py tests/safesym_bridge/test_surface_pddl.py tests/safesym_bridge/test_web_kobe_safesym_smoke.py
git commit -m "feat: compile observed surface graph to PDDL"
```

---

### Task 6: Verify the complete shallow-to-deep workflow

**Files:**
- Modify: `docs/web-capability-graph-design.md`
- Create: `docs/experiments/frontier-replay-surface-pddl-v1.md`
- Test: `tests/safesym_bridge/test_web_kobe_playwright_integration.py`

**Interfaces:**
- Demonstrates: sibling same-surface actions, replay to an old frontier, discovery of a deeper node, Surface PDDL generation, SafeSym planning, and stepwise execution validation.

- [ ] **Step 1: Add a deterministic local integration fixture**

Use the existing local shop fixture and arrange generic actions/states so one first-pass path exhausts while another previously observed surface retains an untried action leading to a deeper page. Do not add production conditionals for fixture labels.

- [ ] **Step 2: Write the failing end-to-end test**

Assert all of:

```python
assert result.graph.meta["replay_success_count"] >= 1
assert any(edge.target_node_id == "checkout" for edge in result.graph.edges)
assert sibling_action_sources(result.graph, "filter", "sort") == {
    "shopping"
}
assert safesym_result.safe_solve is True
assert "checkpoint" not in surface_domain
```

- [ ] **Step 3: Run and verify the test before final fixes**

Run:

```powershell
pytest tests/safesym_bridge/test_web_kobe_playwright_integration.py -k frontier_replay_surface_pddl -v
```

Expected: FAIL until all integration wiring is correct.

- [ ] **Step 4: Make only integration-level corrections**

Fix interface mismatches, artifact wiring, or deterministic fixture timing. Do not add richer state inference, retries, domain profiles, or special-case action ordering.

- [ ] **Step 5: Run the full verification suite**

Run:

```powershell
pytest tests/safesym_bridge/test_frontier_replay.py tests/safesym_bridge/test_surface_pddl.py tests/safesym_bridge/test_web_kobe_controller.py tests/safesym_bridge/test_web_kobe_playwright_integration.py -v
pytest -q
```

Expected: focused tests PASS and the full suite retains the prior pass/skip baseline or improves it.

- [ ] **Step 6: Document the experiment honestly**

Record:

- number of reset attempts and successful replays;
- first replay failure reason, if any;
- discovered node/edge counts;
- sibling action source nodes;
- deepest verified surface;
- generated Surface PDDL paths;
- SafeSym parse/base/safe results;
- explicit V1 limitations: coarse state identity, no retry, no hidden-state guarantees, and no coverage claim.

- [ ] **Step 7: Commit**

```powershell
git add tests/safesym_bridge/test_web_kobe_playwright_integration.py docs/web-capability-graph-design.md docs/experiments/frontier-replay-surface-pddl-v1.md
git commit -m "docs: verify frontier replay surface planning workflow"
```

---

## Self-Review Results

- **Spec coverage:** Linear dependency is addressed by compiling aggregated source/target edges rather than ordered checkpoints. Depth is addressed by selecting reachable under-explored nodes and reset/replay. Replay uncertainty is addressed by validation after reset and after every atomic action, with fail-closed behavior.
- **Scope discipline:** No new semantic fact inference, state-splitting algorithm, coverage optimizer, domain-specific profile, or arbitrary backtracking is included.
- **Type consistency:** `FrontierTarget` carries immutable `ReplayStep` values; `FrontierReplayRunner` consumes the explorer replay port; controller integration consumes the runner; Surface PDDL consumes the existing aggregated graph.
- **Safety:** A replay attempt never creates a successful edge. Only the subsequent normal exploration step may record a new observed transition.
