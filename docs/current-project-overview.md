# Current Project Overview

This document explains what this project is currently trying to build, how the
main pipeline works, and which parts are still MVP-specific.

## What This Project Does

The original `ai-web-explorer` project explores websites with a browser and
LLM assistance, then outputs a graph of web states and actions.

The current project extends that idea toward safety-aware web planning:

```text
real website
  -> browser observation
  -> DOM-grounded Web-KOBE exploration
  -> WebKobeGraph
  -> WebKobeGraph-to-PDDL projection
  -> SafeSym/planner-facing artifacts
  -> later SafeSym safety injection
  -> planner
  -> safe action plan
```

The current milestone uses local fixtures and SauceDemo as controlled targets.
They are not the final goal; they are stable web apps used to prove the
end-to-end chain.

The important research question is:

```text
How can we observe a web app, abstract its state and actions into a graph,
and compile that graph into a planning model where safety checks can be added?
```

## Current Main Pipeline

The recommended path is no longer the older FSM-first path. The project now has
one active generic mainline and one app-specific regression route:

```text
active generic mainline:
  DOM-grounded Web-KOBE exploration
  -> page structure observation
  -> state facts and typed deltas
  -> selected BrowserAction execution through an AutomationBackend
  -> before/after observation and observed deltas
  -> WebKobeExplorer
  -> WebKobeGraph
  -> WebKobeGraph-to-PDDL projection
  -> SafeSym/PDDL-facing artifacts

SafeSym regression route:
  SauceDemoAdapter
  -> GraphExplorer
  -> WebObservedGraph
  -> graph-derived PDDL
  -> SafeSym
```

New generic exploration code should import the active mainline through:

```text
src/ai_web_explorer/grounded_web/
```

That package is the stable boundary for DOM-grounded web operation, state
recording, action execution, and graph construction.
`safesym_bridge` consumes these graph/data structures and should stay focused on
SafeSym/PDDL projection plus app-specific regression adapters. Generic
exploration code and tests should depend on `grounded_web` directly.

The current mainline is now WebKobeGraph-to-PDDL projection: take the graph
produced by grounded Web-KOBE exploration, project successful observed
transitions into a simple STRIPS `domain.pddl`, and create a concrete
`problem.pddl` from explicit start/goal node selection. This keeps
`grounded_web` as the exploration/observation layer and `safesym_bridge` as the
planner-facing projection layer.

The SauceDemo graph/PDDL route remains as an app-specific SafeSym regression
path, especially for future safety-trigger scenarios:

```text
Playwright browser
  -> SauceDemoAdapter
  -> WebObservation / StateSnapshot
  -> DOM interactable candidates
  -> semantic action resolution
  -> GraphExplorer
  -> WebObservedGraph
  -> graph-derived PDDL/regression support
  -> SafeSym scenarios
```

The active CLI smoke path is now Web-KOBE/PDDL-first:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-from-graph \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl \
  --goal-node <goal_node_id>
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/web_kobe_explored_graph.json \
  --output outputs/web_kobe_pddl_smoke \
  --goal-node <goal_node_id>
```

`web-kobe-pddl-smoke` checks whether an explored WebKobeGraph yields non-empty,
graph-reachable, internally consistent PDDL artifacts. The smoke report now
includes static PDDL consistency fields such as
`pddl_static_consistency_ready` and `undeclared_predicates`, so action effects
cannot silently reference predicates that were not declared in the domain. This
is planning-readiness validation, not SafeSym safety-trigger validation.

The retained regression suite is intentionally focused on this mainline plus
the SauceDemo app-specific adapter/resolver/catalog path. Older
WebObservedGraph compiler unit tests, capability-graph sidecar tests, legacy
executor tests, and simple-agent facade tests were removed from the default
suite so test failures better reflect current project direction. The old
prompt-evaluation tests and fixture corpus under `tests/ai/` and `tests/data/`
have also been removed because they depended on live OpenAI/MLflow evaluation
workflows and did not validate the SafeSym-oriented mainline.

Latest retained bridge-suite verification:

```text
tests/safesym_bridge: 156 passed, 2 skipped
all retained tests: 160 passed, 2 skipped
```

`WebKobeGraph` is the main exploration-time representation for unknown websites.
It records semantic page states, browser-grounded actions, observed deltas, and
evidence so the project can project observed web environments into
planner-facing PDDL artifacts for SafeSym.

The current near-term generic Web-KOBE path is DOM-first grounded exploration.
The explorer extracts real interactable elements from the page, converts them
into grounded browser actions, executes those actions with Playwright locators,
and records before/after state deltas in a Web-KOBE graph. LLM/VLM assistance
can be added later for action selection and semantic labeling, but selectors
should come from DOM-grounded candidates rather than being invented by the
model.

The current experimental LLM path follows that boundary: an LLM selector may
choose one action id from already-grounded `BrowserAction` candidates, but it
must not generate selectors or execute the browser directly. Each selection can
be written as a trace sidecar containing the goal, state, candidates, prompt,
raw response, parsed response, status, and error category. This makes failures
attributable to parse errors, invalid action ids, poor choice, execution
failure, or observation/delta problems.

An offline OpenAI-backed selector smoke is now exposed as:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-openai-selector-smoke \
  --output outputs/openai_selector_smoke.json
```

It tests the current concrete SauceDemo selection problem without opening a
browser: given `inventory`, `cart_count=0`, and candidates
`product_add_to_cart` / `cart_open`, the expected choice is
`product_add_to_cart`.

A browser-backed SauceDemo LLM smoke is also available:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-llm-step-smoke \
  --output outputs/saucedemo_llm_5step_graph.json \
  --selector-trace outputs/saucedemo_llm_5step_trace.json \
  --steps 5
```

This smoke treats login as a deterministic test bootstrap, then starts the agent
on the inventory page. With `--steps 5`, the live run produced:

```text
product_add_to_cart
  -> cart_open
  -> cart_checkout_start
  -> checkout_info_submit
  -> order_place_confirm
```

The resulting graph reached `saucedemo:checkout_complete`. It recorded
`cart_count: 0 -> 1`, treated the cart navigation edge as
`succeeded_with_navigation`, recorded `checkout_started: false -> true`,
recorded `order_review_ready: false -> true`, and finally recorded
`order_created: false -> true` plus `cart_count: 1 -> 0`.

That complete graph can now be projected into PDDL and solved by Fast Downward.
The generated base plan is the same five-step checkout path. Running
`web-kobe-safesym-smoke` over the generated PDDL with SafeSym's
`configs/constraint_rules.json` succeeds end to end and inserts:

```text
check_information_verification_checkout_info_submit
check_human_confirmation_order_place_confirm
```

The corresponding safe plan places these checks before
`checkout_info_submit` and `order_place_confirm`.

The old intent-resolution action loop has been removed from the active
mainline. `WebKobeExplorer` now executes the already-selected `BrowserAction`
through an `AutomationBackend`, observes the page before and after execution,
records typed/schema deltas, and writes the graph edge. This keeps the modeling
boundary without expanding a project-owned web-agent execution layer.

When an action executes successfully but produces no immediate delta, the
explorer waits for a bounded observation window and polls state before recording
`no_observed_change`. This is an observation policy, not an execution retry:
the browser action is not repeated by default.

The deterministic semantic assistor now includes a stable state-signature digest
in generated node IDs. This lets single-page applications produce distinct graph
nodes for distinct observed states while still merging repeated observations of
the same state.

The intended architecture boundary is now:

```text
Reusable automation backend
  -> operates the browser
  -> click / fill / scroll / wait / navigate
  -> locator resolution and browser/session handling

Web-KOBE / SafeSym explorer
  -> owns exploration strategy
  -> records before/after observations
  -> infers state deltas
  -> builds Web-KOBE / capability graphs
  -> later exports SafeSym/PDDL-facing artifacts
```

This project should not become a from-scratch general-purpose web agent. It
should reuse existing browser automation capability where possible while keeping
the exploration goal, data model, state recording, graph construction, and
SafeSym bridge under project control. The current Playwright-backed adapter is
the first concrete automation backend. Later work can wrap useful operation
pieces from other web-agent tools as additional backends without replacing the
Web-KOBE/SafeSym exploration layer. The old upstream `explore` runtime has been
removed from the active package because it asked the LLM to generate both action
descriptions and selectors, which conflicts with the current DOM-grounded
candidate boundary.

The concrete backend boundary lives in:

```text
src/ai_web_explorer/grounded_web/automation_backend.py
```

Current implementations should satisfy `AutomationBackend`. The retained
concrete implementations are the Playwright-backed adapter for controlled
fixtures/fallback operation and the Stagehand-backed wrapper for real-site
single-step action discovery/execution. Both leave exploration policy and graph
recording in `WebKobeExplorer`.

Earlier legacy operation-executor experiments have been removed from the active
bridge package. Browser operation should now go through the `AutomationBackend`
boundary and the Playwright-backed Web-KOBE adapter.

The earlier explicit no-LLM `SimpleGroundedWebAgent`, `ActionIntent`,
`ActionExecutionResult`, and ranking/action-loop helpers have been removed.
They encouraged the project to grow its own generic web-agent layer. The active
surface is now smaller: action candidates are selected externally or by the
minimal explorer fallback, executed through an `AutomationBackend`, and modeled
by Web-KOBE.

There are still compatibility structures from the Web-KOBE collector and the
SauceDemo MVP route. They should not be expanded as generic mainline code.
Refactoring should happen gradually when a feature touches a boundary, with new
generic code going through `grounded_web`.

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6
```

This route is the main place to improve generic unknown-site operation because
it directly tests whether the agent can correctly operate real page controls and
record the resulting state changes.

The preferred first golden-path target is a local no-login checkout fixture:

```bash
python -m http.server 8000 --directory tests/fixtures/local_checkout
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6
```

This fixture avoids login, cookie banners, and third-party website changes. It
contains a small product/cart/checkout/order-complete flow, so it is the fastest
way to check whether DOM candidate extraction, Playwright execution, form
filling, state observation, state-specific graph nodes, and Web-KOBE PDDL smoke
are connected correctly.
SauceDemo should be used after this local smoke path works, because SauceDemo
requires a login state before `/inventory.html` is accessible.

The fixture verifies click and fill grounded operation. The expected recorded
deltas include cart count, checkout step, form-completion, and order-created
changes. It is not a site-specific adapter; it is a low-noise shopping benchmark
that exercises the generic DOM-grounded pipeline.

The fixture uses `[data-state]` attributes for lightweight generic state
observation. The Web-KOBE observer currently records each `[data-state]`
element's text value and visibility, which lets the collector infer deltas such
as `cart_panel_visible: false -> true` without a site-specific adapter.

A separate Playwright-backed Web-KOBE exploration command is also available for
controlled local or fixture pages:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

SauceDemo is the primary real-site smoke target for this path:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url https://www.saucedemo.com/ \
  --output outputs/saucedemo_web_kobe_graph.json \
  --app-name saucedemo \
  --steps 4
```

For `--app-name saucedemo`, the adapter reuses the existing SauceDemo state
observer and action profile so the Web-KOBE graph can record meaningful browser
steps such as login, add-to-cart, cart open, and checkout start. Generic pages
still use local DOM extraction. Real SauceDemo browser verification is gated by
`RUN_WEB_KOBE_SAUCEDEMO_TEST=1`.

## Core Concepts

### WebObservation

`WebObservation` is the current observation model for one browser state.

Relevant file:

```text
src/ai_web_explorer/safesym_bridge/web_observation.py
```

It contains:

- `PageIdentity`: the abstract page identity, URL, and title.
- `ObservedFact`: one structured fact about the page.
- `ObservationEvidence`: where that fact came from.
- `interactables`: DOM-backed candidate controls on the page.

Example facts:

```text
username_filled = false
password_filled = false
is_logged_in = false
cart_count = 0
checkout_started = false
order_review_ready = false
order_created = false
```

The key idea is that the browser gives us raw information, but the planner needs
stable facts. `WebObservation` is the bridge between those two levels.

### StateSnapshot

`StateSnapshot` is a compact planning-facing snapshot derived from observation.

Relevant file:

```text
src/ai_web_explorer/grounded_web/models.py
```

It stores:

- `page_id`
- `url`
- `title`
- `signature`

The `signature` is the current set of state facts and values. It is not PDDL by
itself. It is the project's internal representation of the current web state.

### DOM Interactable Candidate

The DOM observer finds visible and enabled interactive elements.

Relevant file:

```text
src/ai_web_explorer/grounded_web/dom_observer.py
```

It scans elements such as:

```text
button
a[href]
input
textarea
select
[role="button"]
[role="link"]
[onclick]
[data-test]
```

Each candidate records information such as:

- element kind
- locator
- locator strategy
- visible name
- metadata

At this stage, a candidate is only a possible control. It is not yet a semantic
planning action.

### Semantic Action

The resolver maps DOM candidates to domain-level action names.

Relevant files:

```text
src/ai_web_explorer/safesym_bridge/semantic_resolver.py
src/ai_web_explorer/safesym_bridge/saucedemo_resolver.py
src/ai_web_explorer/safesym_bridge/action_catalog.py
src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py
```

For example:

```text
DOM candidate: button with text "Checkout"
semantic action: cart_checkout_start
```

The current resolver is rule-based and SauceDemo-specific. In the future, this
is the natural place to add LLM or VLM assistance.

### WebObservedGraph

`WebObservedGraph` is now a SauceDemo regression structure, not the active
generic graph. New unknown-site work should use `WebKobeGraph`.

Relevant file:

```text
src/ai_web_explorer/safesym_bridge/observed_graph.py
```

It contains:

- nodes: abstract web states such as `login`, `inventory`, `cart`
- edges: semantic actions such as `login_submit`, `cart_checkout_start`
- observed values for state facts
- action preconditions
- inferred effects
- interactable elements

An edge represents:

```text
before state
  -- semantic action -->
after state
```

This graph remains useful for SauceDemo-specific safety/regression history, but
it is no longer the default source for new PDDL generation.

### Effects

The older SauceDemo regression route infers effects by comparing before and
after state signatures.

Relevant file:

```text
src/ai_web_explorer/safesym_bridge/effect_inferer.py
```

Example:

```text
before: cart_count = 0
after:  cart_count = 1
effect: set cart_count to 1
```

This remains useful as historical regression support. The active generic path
records observed deltas directly on `WebKobeGraph` edges and projects those
deltas through `web_kobe_pddl_projector.py`.

### PDDL Artifacts

The active PDDL projector turns a `WebKobeGraph` into planning files.

Relevant file:

```text
src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
```

It outputs:

```text
domain.pddl
problem.pddl
```

The current projector is intentionally simple. It maps observed Web-KOBE graph
nodes and successful state-changing edges into STRIPS predicates and actions
such as:

```text
(at_<node_id>)
(cart_count_positive)
(order_created_positive)
```

The current golden-path validation goal is:

```text
(at checkout_complete)
(state_order_created)
```

The generated PDDL can be passed into SafeSym so SafeSym can inject safety
checks before sensitive actions.

## How SafeSym Fits In

SafeSym is not responsible for exploring the website. It receives a planning
model and adds safety constraints or safety-check actions.

In the current SauceDemo MVP, the important sensitive action is:

```text
order_place_confirm
```

This represents placing the order. SafeSym can require a human confirmation
check before that action.

The tested full chain is:

```text
Graph PDDL
  -> SafeSym compile_safe_pddl
  -> Fast Downward
  -> safe plan found
```

The safe plan includes inserted checks such as:

```text
check_information_verification_checkout_info_submit
check_human_confirmation_order_place_confirm
```

## What Is Still SauceDemo-Specific

The current project has a real end-to-end MVP, but it is not yet a generic web
planner.

The following parts are still domain-specific:

- page IDs such as `login`, `inventory`, and `checkout_overview`
- observed state facts such as `cart_count` and `order_created`
- semantic actions such as `product_add_to_cart`
- action preconditions
- the PDDL object list and final goal
- the rule-based resolver

This is intentional for the current stage. The purpose is to make the chain
work first, then generalize carefully.

## What Older Parts Are Now Historical

Earlier work produced SafeSym-compatible FSM outputs. Those pieces are still
visible in older design documents and example artifacts, but they are no longer
the current implementation path.

Current generic main path:

```text
WebKobeGraph -> PDDL artifacts -> SafeSym/planner-facing consumption
```

Retained app-specific regression path:

```text
WebObservedGraph -> SauceDemo PDDL/regression support -> SafeSym scenarios
```

Older historical path:

```text
observed transitions -> FSM JSON -> SafeSym loader compatibility
```

The active CLI no longer exposes the old `fixed` or `observed` FSM commands.
The graph is now the important project data structure.

## Current Technical Boundaries

The current system has several important limits:

- Generic state facts are still intentionally simple; local fixtures use
  `[data-state]` to make early validation low-noise.
- DOM candidate extraction is generic, but action selection and semantic naming
  are still mostly rule-based. An experimental LLM action selector now exists
  behind an explicit optional hook; it is not the default policy.
- The WebKobeGraph-to-PDDL projector emits a deliberately small STRIPS subset.
- `web-kobe-pddl-smoke` now checks graph reachability and basic static PDDL
  consistency, but it is not a full PDDL parser or external planner run.
- `web-kobe-safesym-smoke` can now run the generated Web-KOBE PDDL through the
  external SafeSym parser, safety injection, and optional Fast Downward base/safe
  solves.
- The current `local_checkout` smoke reaches SafeSym and Fast Downward, but it
  does not insert safety check actions yet because projected action names such as
  `dom_006_button_place_order` do not match SafeSym's safety-rule patterns.
- Browser exploration is still narrow and follows checkout-style paths. The
  current SauceDemo LLM smoke proves the bounded selector can complete a
  checkout path when the app-specific candidate actions are available, but it
  does not yet prove arbitrary-site or arbitrary-goal generality.
- Real LLM selector smoke has been run after explicit user approval to use this
  workspace's non-OpenAI `OPENAI_BASE_URL`. The offline selector smoke chose
  `product_add_to_cart` for the concrete SauceDemo `inventory/cart_count=0`
  case. The browser-backed smoke now completes the five-step SauceDemo checkout
  path, reaches `checkout_complete`, and produces a graph/PDDL model that
  Fast Downward and SafeSym can consume. SafeSym inserts checks for
  `checkout_info_submit` and `order_place_confirm`. Default automated coverage
  still uses fake providers to validate selector boundaries and traceability
  without consuming API quota.
- Safety guarantees only apply to the model that was observed and compiled.

These are not failures. They define the next research and engineering steps.

## Next Direction

The next stage should focus on real-web state-transition extraction without
turning the project into a competing general-purpose web agent. The current
recommended design is:

```text
Stagehand-backed WebKobeGraph Exploration MVP
```

The goal is to use Stagehand as a capable browser operation backend while this
project owns the SafeSym-facing modeling layer:

```text
SauceDemo real page
  -> Stagehand single-step observe/act
  -> project-owned before/after observation
  -> schema_delta / typed_delta
  -> WebKobeGraph edge with Stagehand evidence
  -> WebKobeGraph-to-PDDL projection
  -> PDDL smoke report
  -> SafeSym parser / safety injection / planner smoke
```

This changes the short-term focus from building a better web agent to reusing a
web-agent-like operation backend for graph construction. Stagehand may discover
and execute one next browser action, but the project still decides what state
transition was observed and what enters WebKobeGraph, PDDL, and SafeSym.

The first target task should start from the SauceDemo login page and reach
`checkout_overview` after adding one item to the cart:

```text
login
  -> inventory
  -> inventory/cart_nonempty
  -> cart
  -> checkout_info
  -> checkout_overview
```

The MVP should not click `Finish` / place the order. It should also avoid using
Stagehand's full autonomous `agent()` as one opaque task run. The graph loop
should remain one transition at a time:

```text
observe before state
  -> Stagehand observe/act one scoped action
  -> observe after state
  -> compute observed deltas
  -> append graph edge
```

The main design document for this stage is:

```text
docs/superpowers/specs/2026-07-17-stagehand-backed-webkobegraph-exploration-design.md
```

The planned Stagehand-backed smoke command is:

```powershell
$env:STAGEHAND_SERVER = "local"
$env:STAGEHAND_MODEL = "deepseek/<your-model-name>"
$env:MODEL_API_KEY = "<your-deepseek-key>"
python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke `
  --output outputs/saucedemo_stagehand_graph.json `
  --stagehand-trace outputs/saucedemo_stagehand_trace.json `
  --steps 10
```

For BYO model-key runs, `MODEL_API_KEY` is the recommended Python SDK key input.
The project loads `.env` for this runner, reads `STAGEHAND_MODEL`, and also maps
provider-specific keys such as `DEEPSEEK_API_KEY` for `deepseek/...` models.
`STAGEHAND_SERVER=local` is the recommended default because Stagehand then acts
on the same Playwright page that Web-KOBE observes before and after each step.
`STAGEHAND_API_URL` may be set for a custom Stagehand service endpoint; it is
not the DeepSeek/OpenAI-compatible model provider base URL.

It starts at the SauceDemo login page and should stop at `checkout_overview`.
It must not click `Finish`.

With `STAGEHAND_SERVER=local`, `STAGEHAND_MODEL=deepseek/deepseek-v4-pro`, and
`MODEL_API_KEY` configured in `.env`, a live run reached
`checkout_overview__0e208d5cb9` in 10 low-level Stagehand-backed steps:

```text
fill username
  -> fill password
  -> click Login
  -> add Sauce Labs Backpack to cart
  -> open cart
  -> click Checkout
  -> fill first name
  -> fill last name
  -> fill postal code
  -> click Continue
```

The resulting WebKobeGraph had 11 nodes and 10 edges, and
`web-kobe-pddl-smoke` over the graph reported `planning_ready=True` with no
undeclared predicates. A follow-up Fast Downward run solved the projected PDDL
with a 10-step plan matching the observed Stagehand action sequence. This means
the Stagehand-backed route is now validated through real browser operation,
graph construction, PDDL projection, and external planner consumption up to
`checkout_overview`.

Stagehand/AI SDK logged warnings that the DeepSeek model does not support its
current `responseFormat` setting, but the observe/act calls still succeeded.

The important architecture interpretation is:

```text
Stagehand = action discovery/execution evidence
Web-KOBE observer = state facts and before/after deltas
WebKobeGraph/PDDL/SafeSym = project-owned planning model
```

Stagehand descriptions are useful evidence for what was attempted, but they are
not the source of truth for state identity, state deltas, safety triggers, or
PDDL semantics. The project must keep those responsibilities in
`grounded_web`/`safesym_bridge`; otherwise the work collapses back into an
opaque web-agent run instead of a SafeSym-facing web-state model.

The next exploration strategy should be business-flow-guided rather than
coverage-first. Different website types have different representative business
flows, and the graph should be built around those flows first. For the current
e-commerce/check-out target, the representative flow is:

```text
login or session setup
  -> product selection
  -> cart
  -> checkout information
  -> order review
  -> pending sensitive order placement
```

During this v1 strategy, the explorer should still record candidates that were
available but not executed at each node. These records become future frontier
actions for later coverage improvement. The current stage should not yet try to
replay old paths, restore browser snapshots, or backtrack to old nodes to finish
those frontier actions. That recovery/backtracking runtime is important, but it
is deferred until the project has a cleaner state-observation model.

The intended v1 output is therefore:

```text
task-guided main path
  + per-node unexecuted/frontier action records
  + sensitive/pending action candidates
  + before/after state deltas on executed edges
```

This should be treated as a task-guided partial graph, not a complete website
model. A future `frontier_coverage_report` should make that explicit by
reporting fields such as total nodes, executed edges, unexecuted action count,
sensitive pending count, and nodes with remaining frontier actions.

The weakest remaining part of the Stagehand path is state observation. The
current SauceDemo observer still reads known URLs and selectors such as
checkout fields and cart badges. That is acceptable as a real-site regression
benchmark, but it is not generic web-state understanding. The next engineering
step should generalize observation signals while keeping app-specific observers
isolated in `safesym_bridge`.

Deferred work includes node deduplication, repeated product-card abstraction,
parameterized actions, replay/backtracking to old frontier nodes, final
order-placement safety triggers, and using Stagehand `agent()` only as an
external baseline.

Near-term Stagehand-backed priorities are:

- introduce generic state-signal extraction beyond `[data-state]` and
  SauceDemo selectors;
- add a semantic action-labeling layer that maps low-level Stagehand operations
  to stable domain-level actions when enough evidence exists;
- represent sensitive or pending actions such as `Finish` / order placement
  without blindly executing them during graph exploration;
- record unexecuted candidates as per-node frontier actions, while deferring
  replay/backtracking execution of those frontiers;
- improve Stagehand trace diagnostics around invalid choices, parse/model
  warnings, failed execution, navigation, and no observed delta;
- keep CDP/session wiring reusable without moving SauceDemo task prompts into
  the generic exploration layer.

## Important Files

```text
src/ai_web_explorer/safesym_bridge/web_observation.py
  Observation data model: facts, evidence, page identity.

src/ai_web_explorer/safesym_bridge/state_observer.py
  SauceDemo-specific state fact extraction.

src/ai_web_explorer/grounded_web/dom_observer.py
  DOM interactable candidate extraction.

src/ai_web_explorer/grounded_web/llm_action_selector.py
  Experimental selector boundary for choosing one grounded action id and
  recording traceable LLM decision diagnostics.

src/ai_web_explorer/grounded_web/openai_action_selector.py
  OpenAI Chat Completions-backed provider for the selector boundary.

src/ai_web_explorer/grounded_web/stagehand_actions.py
  Stagehand action/trace contracts and conversion into BrowserAction records.

src/ai_web_explorer/grounded_web/stagehand_backend.py
  AutomationBackend wrapper that exposes Stagehand-observed actions to the
  Web-KOBE explorer while preserving project-owned graph recording.

src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py
  Optional Stagehand SDK provider, model-key loading, local/remote server setup,
  and local CDP browser attachment.

src/ai_web_explorer/safesym_bridge/openai_selector_smoke.py
  Offline SauceDemo action-selection smoke for the current `cart_count=0`
  problem.

src/ai_web_explorer/safesym_bridge/semantic_resolver.py
  Resolver interface for mapping candidates to semantic actions.

src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
  SauceDemo adapter connecting observation, resolution, and execution.

src/ai_web_explorer/safesym_bridge/graph_explorer.py
  SauceDemo/regression graph-guided exploration loop.

src/ai_web_explorer/safesym_bridge/observed_graph.py
  WebObservedGraph data structure and builder.

src/ai_web_explorer/safesym_bridge/effect_inferer.py
  Effect inference from before/after state signatures.

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
  Active WebKobeGraph-to-PDDL projector.

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
  Planning-readiness and static-consistency smoke report for WebKobeGraph PDDL
  artifacts.

docs/safesym-bridge.md
  Practical SafeSym bridge usage and command reference.
```
