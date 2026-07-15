# Legacy Action Executor / AiWebExplorerBackend v1 Design

## Goal

This design defines how to reuse operation capability from the original
`ai-web-explorer` codebase without letting its ReAct-style exploration loop take
over the Web-KOBE/SafeSym architecture.

The intended boundary remains:

```text
Web-KOBE / SafeSym Explorer
  -> owns exploration strategy
  -> owns state observation and delta recording
  -> owns graph construction
  -> later owns SafeSym/PDDL projection

Reusable automation backend
  -> operates the browser
  -> executes grounded actions
  -> returns execution success/failure evidence
```

The next reusable unit should be a small action execution layer extracted from
the original `Executor`, not the whole original `ExploreLoop`.

## Current Finding

The original project already contains useful browser operation code in:

```text
src/ai_web_explorer/executor.py
```

The most reusable part is the tool-call execution logic:

```text
click_element(selector)
fill_text_input(selector, text)
select_option(selector, value)
```

These operations map closely to the current Web-KOBE `BrowserAction` kinds:

```text
click
fill
select
fill_then_click
```

However, the current `Executor.execute(action)` method is not a clean backend.
It combines several responsibilities:

- prompting an LLM to generate tool calls;
- executing the tool calls;
- comparing screenshots;
- asking a model to verify success;
- retrying execution;
- storing all tool calls;
- depending on the original `webstate.Action` structure.

That is too coupled for the Web-KOBE/SafeSym path.

## Recommended Approach

Extract or introduce a small `LegacyActionExecutor` that only performs grounded
browser operations.

Conceptual interface:

```python
class LegacyActionExecutor:
    def __init__(self, page: playwright.sync_api.Page) -> None:
        ...

    def execute_browser_action(self, action: BrowserAction) -> bool:
        ...
```

This executor should not:

- call an LLM;
- choose actions;
- describe pages;
- verify success with a model;
- build graphs;
- know about SafeSym/PDDL.

It should only translate an already-grounded `BrowserAction` into real
Playwright operations.

## Why Not Wrap the Whole Original Executor?

Wrapping `Executor.execute()` directly looks tempting because it already knows
how to use LLM-generated tool calls. But it would reintroduce the coupling this
project is trying to avoid.

Directly wrapping it would mean the backend might:

- generate its own selectors;
- decide how to execute an abstract description;
- depend on OpenAI prompts;
- retry with new model-generated actions;
- verify success using screenshots;
- hide the exact operation path from the Web-KOBE explorer.

That is useful for a general web agent, but risky for a SafeSym-facing
environment modeling system.

For this project, the selector and action candidate should already be grounded
before execution reaches the backend.

## Proposed Data Flow

```text
WebKobeExplorer
  -> selects BrowserAction from grounded candidates
  -> calls AutomationBackend.execute(action)

AiWebExplorerBackend
  -> receives BrowserAction
  -> delegates physical operation to LegacyActionExecutor

LegacyActionExecutor
  -> scrolls locator into view
  -> click / fill / select
  -> waits briefly
  -> returns bool success

WebKobeExplorer
  -> observes after-state
  -> computes delta
  -> records edge
```

## Relationship to Existing Playwright Backend

`WebKobePlaywrightAdapter` remains the default async Playwright backend.

`LegacyActionExecutor` is not meant to replace it immediately. Its value is to
start separating reusable operation primitives from the old `ai-web-explorer`
agent.

The project may later introduce:

```text
AiWebExplorerBackend
  -> uses original sync Playwright page and LegacyActionExecutor
```

or keep using the async Playwright backend if it proves simpler.

## Action Mapping

| BrowserAction kind | Legacy operation |
| --- | --- |
| `click` | scroll target into view, then click target locator |
| `fill` | fill target locator with the first available input value, or a safe default |
| `select` | select the first available input value |
| `fill_then_click` | fill each selector/value pair, then click target locator |

Unsupported actions should return `False` rather than guessing.

## First Implementation Scope

The first implementation should be intentionally small:

1. Add `LegacyActionExecutor`.
2. Cover `click`, `fill`, `select`, and `fill_then_click`.
3. Unit-test with fake page/locator objects.
4. Keep the current `WebKobePlaywrightAdapter` behavior unchanged.
5. Optionally add an experimental `AiWebExplorerBackend` only after the executor
   is isolated and tested.

This avoids mixing two changes:

- extracting reusable operation capability;
- introducing a second full backend.

## Non-goals

This step does not attempt to:

- connect a third-party web agent;
- make the old `ExploreLoop` the main explorer;
- use LLMs for action selection;
- use LLMs for selector generation;
- solve state recovery;
- solve graph deduplication;
- change the Web-KOBE graph schema.

## Recommendation

Proceed in two phases:

```text
Phase 1:
  Extract LegacyActionExecutor and test it.

Phase 2:
  If Phase 1 is clean, wrap it in an experimental AiWebExplorerBackend.
```

This keeps the project aligned with the core principle:

```text
Reuse operation capability.
Own exploration and SafeSym-facing knowledge construction.
```

