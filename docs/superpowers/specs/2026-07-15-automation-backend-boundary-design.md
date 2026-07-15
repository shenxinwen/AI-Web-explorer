# Automation Backend Boundary Design

## Goal

This design fixes an important project boundary:

```text
Reuse existing web automation capability.
Own the exploration logic, state recording, graph construction, and SafeSym bridge.
```

The project should not become a from-scratch general-purpose web agent. Its value is the SafeSym-facing exploration layer that turns unknown web environments into structured action/state knowledge.

## Architecture Principle

The system is split into two layers.

```text
Web-KOBE / SafeSym Explorer
  -> controls exploration strategy
  -> records before/after observations
  -> infers state deltas
  -> builds Web-KOBE / capability graphs
  -> later exports SafeSym/PDDL-facing artifacts

Automation Backend
  -> operates the browser
  -> clicks, fills, scrolls, waits, navigates
  -> resolves locators
  -> handles browser/session state
```

The explorer decides what should be explored and how the result should be recorded. The backend only provides grounded browser operation.

## Why This Boundary Matters

Existing web agents are usually optimized for completing a task, such as buying an item, filling a form, or searching for information. This project is different. We need to discover and record what the environment can do.

If a general web agent controls the whole process, it may complete tasks successfully while hiding the exact information SafeSym needs:

- which concrete interactable was used;
- what locator grounded the action;
- what the before-state was;
- what changed after the action;
- whether the transition should become a graph edge;
- how the transition should later become a planning action.

Therefore, we can reuse a web agent's browser operation layer, but the exploration loop and data model must remain ours.

## Proposed Interface

Introduce a stable backend boundary. The exact name can evolve, but the conceptual interface is:

```python
class AutomationBackend:
    async def observe(self) -> PageObservation:
        ...

    async def list_interactables(self) -> list[Interactable]:
        ...

    async def execute(self, action: BrowserAction) -> ActionResult:
        ...
```

Optional future methods:

```python
async def navigate(url: str) -> None:
    ...

async def reset_to(state_ref: StateRef) -> bool:
    ...

async def recover(edge_path: list[BrowserAction]) -> bool:
    ...
```

The first version should stay small. `observe`, `list_interactables`, and `execute` are enough to preserve the current DOM-first exploration loop.

## Backend Candidates

### 1. PlaywrightBackend

This is the current default path.

It is reliable, testable, and already works on the local fixture. It should remain the first backend because it gives us direct control over locators, browser state, and before/after observation.

### 2. AiWebExplorerBackend

This backend would wrap useful automation pieces from the original `ai-web-explorer` project.

It should reuse browser operation capabilities without importing the original ReAct-style exploration logic as the main controller.

### 3. ThirdPartyWebAgentBackend

This can wrap tools such as browser-use-style agents later.

This is useful if their action execution is stronger than our local Playwright wrapper, but they must still be constrained by our candidate actions and must return enough evidence for graph recording.

## Data Flow

```text
ExplorerCore
  -> backend.observe()
  -> backend.list_interactables()
  -> build grounded BrowserAction candidates
  -> select next action
  -> backend.execute(action)
  -> backend.observe()
  -> compute delta
  -> record Web-KOBE edge
```

The selector may be deterministic, BFS/DFS-based, LLM-based, or VLM-based. In all cases, it should choose from grounded candidates rather than inventing actions.

## Current Implementation Direction

The current `web_kobe_playwright_adapter.py` should be treated as the first concrete backend, not as the final exploration architecture.

Near-term work should:

1. Keep the existing Playwright-backed path working.
2. Clarify backend/explorer boundaries in names and interfaces.
3. Ensure the explorer owns graph recording and state delta inference.
4. Later evaluate whether the original `ai-web-explorer` operation pieces can become another backend.

## Non-goals

This design does not attempt to:

- build a new general-purpose web agent;
- replace Playwright;
- make LLM/VLM directly control arbitrary browser actions;
- finish state deduplication or PDDL projection;
- solve full state recovery in this step.

Those are later concerns after the operation-and-recording loop is stable.

## Acceptance Criteria

The design is satisfied when:

- documentation clearly states that browser operation is delegated to reusable automation backends;
- Web-KOBE/SafeSym code remains responsible for exploration strategy and graph recording;
- the current Playwright adapter can be understood as one backend implementation;
- future backends can be added without rewriting the graph and SafeSym-facing logic.

