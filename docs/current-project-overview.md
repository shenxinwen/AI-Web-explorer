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
  -> WebObservedGraph
  -> graph-derived PDDL
  -> SafeSym safety injection
  -> planner
  -> safe action plan
```

The current milestone uses SauceDemo as the target website. SauceDemo is not the
final goal; it is a controlled web app used to prove the end-to-end chain.

The important research question is:

```text
How can we observe a web app, abstract its state and actions into a graph,
and compile that graph into a planning model where safety checks can be added?
```

## Current Main Pipeline

The recommended path is no longer the older FSM-first path. The current main
path is graph-first:

```text
Playwright browser
  -> SauceDemoAdapter
  -> WebObservation / StateSnapshot
  -> DOM interactable candidates
  -> semantic action resolution
  -> GraphExplorer
  -> WebObservedGraph
  -> PDDL compiler
  -> SafeSym
```

In CLI form:

```bash
python -m ai_web_explorer.safesym_bridge.cli explore-graph --output outputs/saucedemo_explored_graph.json
python -m ai_web_explorer.safesym_bridge.cli explore-pddl --output outputs/safesym_e2e/explored_graph_pddl
```

An experimental capability-graph sidecar is also available:

```bash
python -m ai_web_explorer.safesym_bridge.cli capability-graph --output outputs/saucedemo_capability_graph.json
python -m ai_web_explorer.safesym_bridge.cli explore-capability-graph --output outputs/saucedemo_explored_capability_graph.json
```

This sidecar does not replace `WebObservedGraph -> PDDL -> SafeSym`. It projects
the same observed transitions into a capability-first artifact that focuses on
semantic page states, abstract capabilities, and observed state deltas.

An early Web-KOBE-style exploration graph is being introduced as the next
generic exploration direction:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
```

This graph is intended to become the main exploration-time representation for
unknown websites. It records semantic page states, browser-grounded actions,
observed deltas, and evidence so the project can later project unknown web
environments into SafeSym-compatible PDDL.

The current near-term generic Web-KOBE path is DOM-first grounded exploration.
The explorer extracts real interactable elements from the page, converts them
into grounded browser actions, executes those actions with Playwright locators,
and records before/after state deltas in a Web-KOBE graph. LLM/VLM assistance
can be added later for action selection and semantic labeling, but selectors
should come from DOM-grounded candidates rather than being invented by the
model.

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
pieces from the original `ai-web-explorer` agent, or other web-agent tools, as
additional backends without replacing the Web-KOBE/SafeSym exploration layer.

The concrete backend boundary lives in:

```text
src/ai_web_explorer/safesym_bridge/automation_backend.py
```

Current implementations should satisfy `AutomationBackend`. The first concrete
implementation is `WebKobePlaywrightAdapter`, which wraps Playwright browser
operation while leaving exploration policy and graph recording in
`WebKobeExplorer`.

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_shop_web_kobe.json \
  --app-name local_shop \
  --page-id local_shop \
  --steps 3
```

This route is the main place to improve generic unknown-site operation because
it directly tests whether the agent can correctly operate real page controls and
record the resulting state changes. The older original-explorer sidecar path is
still useful as a comparison point, but it is less stable because it asks the
LLM to generate both action descriptions and selectors.

The preferred first smoke target is a local no-login fixture page:

```bash
python -m http.server 8000 --directory tests/fixtures/local_shop
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_shop_web_kobe.json \
  --app-name local_shop \
  --page-id local_shop \
  --steps 3
```

This fixture avoids login, cookie banners, and third-party website changes. It
contains repeated product-card entities and simple cart state changes, so it is
the fastest way to check whether DOM candidate extraction, Playwright execution,
state observation, and Web-KOBE graph recording are connected correctly.
SauceDemo should be used after this local smoke path works, because SauceDemo
requires a login state before `/inventory.html` is accessible.

The fixture currently verifies click-based grounded operation. The expected
recorded deltas include cart count changes and cart panel visibility changes.
Complex state recovery, deduplication, and full PDDL projection are intentionally
deferred until this operation-and-recording loop is reliable.

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

This command is useful as an experimental validation path, but new generic
exploration work should prefer collector hooks in the original explorer rather
than expanding a second independent exploration loop.

The debug-only commands are still available:

```bash
python -m ai_web_explorer.safesym_bridge.cli graph --output outputs/saucedemo_observed_graph.json
python -m ai_web_explorer.safesym_bridge.cli pddl --output outputs/safesym_e2e/graph_pddl
```

The `graph` and `pddl` commands use fixed MVP transitions. They are useful for
fast regression tests, but they are not the long-term main path.

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
src/ai_web_explorer/safesym_bridge/models.py
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
src/ai_web_explorer/safesym_bridge/dom_observer.py
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

`WebObservedGraph` is the central graph structure.

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

The graph is intended to become the main source for later PDDL generation.

### Effects

Effects are inferred by comparing the before and after state signatures.

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

This matters because the system should not rely only on hand-written action
effects. The long-term goal is to learn effects from observed transitions.

### PDDL Artifacts

The PDDL compiler turns the observed graph into planning files.

Relevant file:

```text
src/ai_web_explorer/safesym_bridge/pddl_compiler.py
```

It outputs:

```text
domain.pddl
problem.pddl
```

The current compiler is SauceDemo-specific. It maps graph facts into PDDL
predicates such as:

```text
(at inventory)
(state_is_logged_in)
(state_cart_count_positive)
(state_order_created)
```

The current goal is:

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

Current main path:

```text
WebObservedGraph -> PDDL -> SafeSym
```

Older historical path:

```text
observed transitions -> FSM JSON -> SafeSym loader compatibility
```

The active CLI no longer exposes the old `fixed` or `observed` FSM commands.
The graph is now the important project data structure.

## Current Technical Boundaries

The current system has several important limits:

- Fact modeling is still hand-designed for SauceDemo.
- DOM candidate extraction is generic, but semantic resolution is mostly rules.
- Action preconditions are currently defined by local code.
- The PDDL compiler silently ignores unsupported predicates in some cases.
- The compiler is not yet generic across websites.
- Browser exploration is still narrow and follows the checkout-style path.
- Safety guarantees only apply to the model that was observed and compiled.

These are not failures. They define the next research and engineering steps.

## Next Direction

The next stage should focus on a more general web abstraction layer:

```text
raw browser data
  -> observed facts with evidence
  -> state signature
  -> graph nodes and edges
  -> inferred preconditions/effects
  -> PDDL facts and actions
```

The most important design questions are:

- Which page facts should be stored?
- How should different kinds of facts be classified?
- How should state signatures avoid both missing important state and storing too
  much DOM noise?
- Which decisions should use local rules?
- Which decisions should use LLM or VLM assistance?
- How should graph changes be converted into reliable PDDL?

A conservative approach is recommended:

```text
local DOM/rule observation first
LLM/VLM as resolver or verifier later
```

This keeps the pipeline debuggable while leaving a clear path toward more
semantic understanding.

## Important Files

```text
src/ai_web_explorer/safesym_bridge/web_observation.py
  Observation data model: facts, evidence, page identity.

src/ai_web_explorer/safesym_bridge/state_observer.py
  SauceDemo-specific state fact extraction.

src/ai_web_explorer/safesym_bridge/dom_observer.py
  DOM interactable candidate extraction.

src/ai_web_explorer/safesym_bridge/semantic_resolver.py
  Resolver interface for mapping candidates to semantic actions.

src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
  SauceDemo adapter connecting observation, resolution, and execution.

src/ai_web_explorer/safesym_bridge/graph_explorer.py
  Generic graph-guided exploration loop.

src/ai_web_explorer/safesym_bridge/observed_graph.py
  WebObservedGraph data structure and builder.

src/ai_web_explorer/safesym_bridge/effect_inferer.py
  Effect inference from before/after state signatures.

src/ai_web_explorer/safesym_bridge/pddl_compiler.py
  Graph-to-PDDL compiler for the current SauceDemo MVP.

docs/safesym-bridge.md
  Practical SafeSym bridge usage and command reference.
```
