# Current Project Overview

This is the project handoff document for code context and AI-assisted work.
The Chinese version, `docs/current-project-overview.zh-CN.md`, is for human
review. Keep both files synchronized whenever the project direction changes.

## Project Purpose

This project is not trying to become a general-purpose web agent.

The goal is to serve SafeSym by turning real web interaction into a
planner-facing model:

```text
real website
  -> browser observation and action execution
  -> WebKobeGraph
  -> Web-KOBE PDDL projection
  -> SafeSym parser / safety injection / planner artifacts
```

The core research question is:

```text
How can we explore a web app, observe what actions change, abstract those
changes into planning facts, and compile them into a model where SafeSym can
inject safety checks?
```

The valuable part of this project is the state graph and planning model, not
the low-level ability to operate arbitrary websites. Existing browser automation
or web-agent tools should be reused when they help, while this project keeps
ownership of state abstraction, graph construction, PDDL projection, and
SafeSym-facing semantics.

## Main Pipeline

The current mainline is:

```text
real webpage
  -> grounded observation
  -> candidate action discovery/selection
  -> browser action execution through AutomationBackend
  -> before/after observation
  -> schema_delta / typed_delta / planning_delta
  -> WebKobeGraph
  -> PDDL artifacts
  -> SafeSym / planner consumption
```

The current graph should be treated as a task-guided partial website model. It
does not need to cover every interaction in the website at this stage. The
near-term exploration strategy is business-flow-guided:

```text
login or session setup
  -> product selection
  -> cart
  -> checkout information
  -> order review
  -> pending sensitive order placement
```

While following the main task, the explorer should record available but
unexecuted actions as future frontier actions. Executing those frontiers through
replay, snapshots, or backtracking is deferred until state observation is more
reliable.

## Architecture Boundaries

### grounded_web

`src/ai_web_explorer/grounded_web/` is the generic web exploration layer.

It owns:

- DOM and browser-grounded observation;
- candidate action representation;
- automation backend interfaces;
- before/after state recording;
- typed and schema deltas;
- WebKobeGraph construction;
- trace boundaries for LLM/Stagehand-assisted selection or execution.

It should not contain SafeSym-specific planning logic or SauceDemo-only
business rules.

### safesym_bridge

`src/ai_web_explorer/safesym_bridge/` consumes graph and observation artifacts.

It owns:

- WebKobeGraph-to-PDDL projection;
- SafeSym smoke integration;
- planner-facing artifacts;
- local checkout and SauceDemo regressions;
- app-specific adapters, observers, and action catalogs when needed.

It should not grow into the generic exploration runtime.

### AutomationBackend

Browser operation goes through:

```text
src/ai_web_explorer/grounded_web/automation_backend.py
```

Current concrete backends:

```text
src/ai_web_explorer/grounded_web/playwright_backend.py
src/ai_web_explorer/grounded_web/stagehand_backend.py
```

The backend operates the browser. The Web-KOBE layer owns the graph and the
meaning of the observed transition.

## Current Implementation Status

The project has an end-to-end MVP. It is not yet a mature generic web-state
modeling system.

Completed and validated:

- `WebKobeGraph` is the active graph representation for new work.
- `BusinessFlowProfile` and `PlanningDelta` schemas exist for profile-guided
  planning-state abstraction.
- `WebKobeEdge` can carry candidate and verified planning deltas.
- A minimal structured `PlanningFactVerifier` can derive verified planning
  deltas from existing state signatures.
- `WebKobeExplorer` can attach profile-verified `PlanningDelta` records to
  executed edges when a business profile is provided.
- `WebKobeExplorer` can optionally capture before/after screenshots when the
  automation backend supports screenshot capture.
- A model-independent visual delta summarizer can turn screenshot evidence into
  candidate planning facts without verifying them.
- An OpenAI visual delta provider exists behind separate OpenAI vision config;
  it belongs to the observation layer and is independent from Stagehand.
- The Stagehand SauceDemo smoke can optionally enable OpenAI visual delta with
  `--openai-visual-delta`, `--visual-delta-model`, and `--screenshot-dir`.
- The old from-scratch action execution layer has been removed.
- Playwright remains available for controlled fixtures and fallback operation.
- Stagehand is integrated as a real-site action discovery/execution backend.
- WebKobeGraph can be projected into PDDL.
- PDDL projection currently treats candidate and verified planning-delta facts
  as trusted effects so the VLM/LLM-to-PDDL chain can be validated end to end.
- Generated PDDL can be checked for graph reachability and static consistency.
- Fast Downward can solve the generated base plan.
- SafeSym can parse, inject safety actions, and solve the safe plan in smoke
  scenarios.

Latest retained test status:

```text
all retained tests: 182 passed, 2 skipped
```

Playwright browser tests may still fail inside a restricted sandbox with browser
spawn permission errors. They require external execution permission when run in
that environment.

## What Has Been Validated

### SauceDemo LLM Checkout Smoke

The app-specific SauceDemo LLM smoke completed a five-step checkout path:

```text
product_add_to_cart
  -> cart_open
  -> cart_checkout_start
  -> checkout_info_submit
  -> order_place_confirm
```

The graph reached `checkout_complete`, projected PDDL could be solved, and
SafeSym inserted safety checks before:

```text
checkout_info_submit
order_place_confirm
```

The inserted check actions were:

```text
check_information_verification_checkout_info_submit
check_human_confirmation_order_place_confirm
```

### Stagehand SauceDemo Graph Smoke

Stagehand has been validated as a local browser operation backend using a CDP
connection to the same Playwright browser observed by Web-KOBE.

With `.env` configured for local Stagehand and the user's model key, a real
SauceDemo run reached `checkout_overview` in 10 low-level Stagehand-backed
steps:

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

The resulting WebKobeGraph had 11 nodes and 10 edges. PDDL smoke reported
`planning_ready=True` with no undeclared predicates, and Fast Downward produced
a plan matching the observed action sequence.

This validates the real-site chain up to graph construction, PDDL projection,
and external planner consumption. It does not yet validate robust generic state
understanding.

## Stagehand Integration

Stagehand should be interpreted as:

```text
Stagehand = action discovery / action execution evidence
Web-KOBE observer = state facts and before/after deltas
WebKobeGraph/PDDL/SafeSym = project-owned planning model
```

Stagehand descriptions are useful evidence about what was attempted. They are
not the source of truth for:

- state identity;
- state deltas;
- safety triggers;
- PDDL predicates or effects;
- node merging;
- task success.

The project currently uses Stagehand in a one-transition-at-a-time loop:

```text
observe before state
  -> Stagehand observe/act one scoped action
  -> observe after state
  -> compute project-owned deltas
  -> append WebKobeGraph edge
```

Do not replace this loop with a single opaque Stagehand `agent()` run as the
main implementation. `agent()` may be useful later as an external baseline, but
the project needs transition-level evidence for SafeSym.

## State Observation and Planning Facts

State observation is the main current weakness.

The system can collect low-level signals such as URL, title, visible controls,
DOM text, form fields, `[data-state]` values, and app-specific SauceDemo facts.
Those are useful evidence, but they are not sufficient by themselves for good
PDDL.

PDDL should consume planning-level facts, for example:

```text
logged_in
product_list_visible
cart_empty
cart_nonempty
checkout_started
checkout_info_complete
order_review_ready
order_place_pending_sensitive
order_completed
error_visible
```

The intended abstraction stack is:

```text
raw browser evidence
  -> structured observation facts
  -> candidate planning facts
  -> verified planning facts
  -> PDDL predicates/effects
```

The graph should preserve evidence and uncertainty. A model or heuristic may
propose that an action succeeded, but only verified planning facts should affect
the planner-facing model.

The project should introduce business-type profiles instead of trying to
collect every possible page state. A `BusinessFlowProfile` defines what a class
of websites needs the planner to understand, without binding that abstraction to
one site's selectors or exact URLs.

For example, an e-commerce checkout profile may describe facts such as
`cart_nonempty`, `checkout_info_complete`, or
`order_place_pending_sensitive` with semantic meanings and evidence hints:

```text
fact: cart_nonempty
meaning: the user has at least one item selected for purchase
evidence hints:
  - cart badge or item count indicates one or more items
  - cart page lists at least one product
  - product card indicates the item is selected or removable
```

The boundary should be:

```text
BusinessFlowProfile = what the planner needs to understand
observers/verifiers = how evidence is found on the current page
site adapters = optional benchmark-specific stabilization
```

This keeps the abstraction more general than SauceDemo while still much more
efficient than blind state collection.

## Current Limitations

Known limits:

- Generic state abstraction is still shallow.
- Current PDDL projection is intentionally small and STRIPS-oriented.
- Some action names are still too low-level to match SafeSym safety-rule
  patterns reliably.
- SauceDemo remains a real-site benchmark, not proof of arbitrary-site
  generality.
- The graph is currently task-guided and partial, not a complete website model.
- Frontier actions are recorded conceptually, but replay/backtracking is
  deferred.
- Node deduplication and repeated-structure abstraction are not mature.
- Safety guarantees only apply to the observed and compiled model.

These are expected research-stage limits. The next phase should address the
state abstraction gap first.

## Next Stage: AI-assisted State Delta Extraction

The next stage is:

```text
VLM/LLM-assisted planning-state delta extraction
```

The goal is to use large models where they are strongest, while keeping project
control over verification and graph truth.

Proposed flow:

```text
before screenshot
  + after screenshot
  + executed action
  + task goal
  + before/after structured observation
  -> VLM visual delta summary
  -> LLM/parser normalized candidate planning delta
  -> structured verification
  -> verified planning facts/effects
  -> WebKobeGraph edge
  -> PDDL projection
```

Screenshot capture is local evidence collection only. It does not imply that
the configured Stagehand text model can process images. If visual analysis is
enabled later, it should use a separate VLM provider/config and feed its output
back as candidate planning facts for structured verification.

Current implementation keeps this separation explicit:

```text
Stagehand = operation backend
visual_delta / OpenAIVisualDeltaProvider = observation-side VLM support
PlanningFactVerifier = structured verification before graph/PDDL truth
```

Responsibilities:

```text
VLM = visual evidence and task-relevant change hypothesis
LLM/parser = schema normalization and predicate selection
structured verifier = DOM/URL/control/form evidence check
WebKobeGraph/PDDL/SafeSym = verified planning model
```

The VLM should not directly write PDDL facts. The LLM should not freely invent
predicates. The verifier should preserve uncertainty, for example:

```text
candidate_success = true
verified_success = false or uncertain
reason = cart badge/button/URL evidence did not support the claim
```

This allows the system to benefit from large-model semantic compression without
turning the planning model into an opaque model transcript.

The current `PlanningDelta` shape intentionally keeps both candidate and
verified facts, but the near-term chain assumes profile-level planning facts are
trusted enough to project. This lets the project validate the full
VLM/LLM-to-PDDL path first. The structured verifier remains a later stability
and trust upgrade that can decide which candidate facts should become verified
facts.

## Near-term Roadmap

Recommended next steps:

1. Add an LLM/parser normalizer that maps summaries to the profile predicate set.
2. Extend the structured verifier to combine model candidates with DOM, URL,
   controls, form values, and known state signals.
3. Run the Stagehand SauceDemo smoke with OpenAI visual delta when
   `OPENAI_API_KEY` and a vision-capable model are configured.
4. Validate profile-verified planning deltas on `local_checkout` first, then
   SauceDemo.

Deferred work:

- complete frontier replay/backtracking;
- robust node merging and template-level page abstraction;
- repeated product-card abstraction;
- parameterized actions;
- broad website-type profiles beyond checkout;
- Stagehand `agent()` baseline comparison.

## Important Files

```text
src/ai_web_explorer/grounded_web/
  Generic exploration and graph construction package.

src/ai_web_explorer/grounded_web/automation_backend.py
  Browser automation backend interface.

src/ai_web_explorer/grounded_web/stagehand_backend.py
  Stagehand-backed AutomationBackend wrapper.

src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py
  Stagehand SDK setup, model-key loading, local server/CDP wiring.

src/ai_web_explorer/grounded_web/explorer.py
  Web-KOBE exploration loop.

src/ai_web_explorer/grounded_web/graph.py
src/ai_web_explorer/grounded_web/graph_manager.py
  WebKobeGraph data structures and management.

src/ai_web_explorer/grounded_web/state_facts.py
src/ai_web_explorer/grounded_web/typed_delta.py
  Generic state fact and delta extraction.

src/ai_web_explorer/grounded_web/business_profile.py
  BusinessFlowProfile and planning-delta schema for profile-guided state
  abstraction.

src/ai_web_explorer/grounded_web/planning_fact_verifier.py
  Structured verifier that maps observed state changes into profile-guided
  PlanningDelta records.

src/ai_web_explorer/grounded_web/visual_delta.py
  Model-independent visual delta summarizer for screenshot-backed candidate
  planning facts.

src/ai_web_explorer/grounded_web/openai_visual_delta.py
  OpenAI vision provider for visual delta summarization. This belongs to the
  observation layer, not the Stagehand operation layer.

src/ai_web_explorer/safesym_bridge/
  SafeSym/PDDL projection and app-specific regression package.

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_projector.py
  Active WebKobeGraph-to-PDDL projector.

src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
  PDDL planning-readiness smoke.

src/ai_web_explorer/safesym_bridge/state_observer.py
src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
  SauceDemo-specific observation and regression support.

docs/safesym-bridge.md
  Practical SafeSym bridge command reference.
```

## Handoff Notes

For a new session, read this English document first. The Chinese document is
for human review, but both must stay synchronized.

Restate these points before starting new architecture or implementation work:

- the project serves SafeSym, not a generic web-agent product;
- `grounded_web` explores and builds WebKobeGraph;
- `safesym_bridge` projects and validates planner-facing artifacts;
- Stagehand is an action backend/evidence source, not the graph truth;
- the next priority is verified planning-state delta extraction.

Default working preference:

```text
single agent
save tokens
do not use subagents unless the user explicitly allows them
```
