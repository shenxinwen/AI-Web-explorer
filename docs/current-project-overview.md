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
- runtime-stable graph identity plus human-readable semantic labels;
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

## Graph Identity And Naming

Treat graph identity and human-readable naming as two different concerns.

Runtime identity is owned by deterministic code:

```text
node_id
edge_id
BrowserAction.semantic_id
BrowserAction.locator
```

These fields are allowed to drive graph merge, execution, trace correlation,
and PDDL projection. They should not be rewritten by LLM/VLM providers.

Readable names are evidence-bearing annotations:

```text
WebKobeNode.node_label
WebKobeNode.state_summary
BrowserAction.action_label
BrowserAction.canonical_action_name
naming_provenance
```

These fields make graphs easier to inspect and can later help the PDDL mapping
layer choose planner-facing action names. They are not graph identity. If
DeepSeek semantic naming is enabled, it only writes these readable fields.

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
- `WebKobeNode` and `BrowserAction` now separate runtime identity from readable
  naming. `node_id`, `edge_id`, `semantic_id`, and locators remain deterministic
  execution/projection anchors, while `node_label`, `state_summary`,
  `action_label`, `canonical_action_name`, and `naming_provenance` are optional
  diagnostic or projection-assist fields.
- DOM and Stagehand candidates provide lightweight baseline naming evidence.
  The Stagehand SauceDemo smoke can optionally enable DeepSeek semantic naming
  with `--deepseek-semantic-naming` and `--semantic-naming-model`; this uses the
  configured DeepSeek/OpenAI-compatible text endpoint and does not change
  runtime IDs, selectors, state facts, or PDDL effects.
- Business-milestone edges can now receive transition-level LLM naming from the
  VLM `visual_change_summary`. This is a generic naming pass, not an
  e-commerce action mapping table. It asks for a concise lower_snake_case
  business transition name and only affects readable action fields and PDDL
  action naming preference.
- DOM/HTML extraction remains part of the generic evidence layer. It should be
  used to support or challenge profile facts, not replaced by a site-specific
  observer.
- The old from-scratch action execution layer has been removed.
- Playwright remains available for controlled fixtures and fallback operation.
- Stagehand is integrated as a real-site action discovery/execution backend.
- The main Stagehand benchmark path now uses the generic grounded Playwright
  adapter and e-commerce-level task guidance. It should not auto-enable the
  SauceDemo-specific observer or static action catalog.
- Stagehand e-commerce task prompts are split into domain guidance, benchmark
  context, action policy, and safety boundary. SauceDemo credentials and
  checkout data are benchmark context, configurable through the smoke command,
  and should not be embedded in the reusable domain guidance.
- The e-commerce Stagehand smoke now defaults to a business-milestone execution
  boundary: each graph step asks Stagehand to advance one meaningful checkout
  milestone, while low-level clicks/fills stay inside the edge trace instead of
  becoming planner-facing graph edges.
- The preferred e-commerce Stagehand smoke entrypoint is now benchmark-driven:
  `web-kobe-ecommerce-stagehand-smoke --benchmark saucedemo`. The older
  `web-kobe-saucedemo-stagehand-smoke` command remains as a compatibility
  wrapper for existing scripts.
- WebKobeGraph can be projected into PDDL.
- PDDL projection currently treats candidate and verified planning-delta facts
  as trusted effects so the VLM/LLM-to-PDDL chain can be validated end to end.
- PDDL projection now separates unique planner action identity from readable
  business labels. Projected action names are generated by code with a stable
  `edge_###_<business_suffix>` shape, so repeated LLM-readable labels do not
  collapse into duplicate PDDL actions.
- PDDL projection defaults to planner-facing facts: graph location predicates
  plus profile/planning facts from `PlanningDelta`. DOM/control
  `observed_delta` facts remain graph evidence and are not default PDDL
  predicates.
- Planning delete effects are projected conservatively by requiring removed
  planning facts in the action precondition, which keeps the generated model in
  the STRIPS fragment expected by the current Fast Downward smoke.
- Generated PDDL can be checked for graph reachability and static consistency.
- PDDL smoke diagnostics now report projected action names, duplicate action
  names, observed/control fact projection, and delete effects without matching
  preconditions.
- SafeSym can parse and inject over the generated PDDL. The next experiment
  should re-run Fast Downward base/safe solve after this projection hardening.

Latest retained test status:

```text
all retained tests: 192 passed, 2 skipped
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

For the SauceDemo test site, the Stagehand smoke also has an explicit
`--allow-final-order` mode. That mode lets the runner click `Finish` and reach
`checkout_complete` so the full order-confirmation safety path can be tested.
The default remains safer and stops at checkout overview.

The current verified final-order run reached `checkout_complete` in 11
Stagehand-backed transitions. The generated PDDL projected the final low-level
click as `order_place_confirm`; SafeSym with `configs/constraint_rules.json`
inserted:

```text
check_human_confirmation_order_place_confirm
```

Use `constraint_rules.json` for injection smoke runs. `safety_rules.json` is
for risk labeling and does not contain the check-action injection config.

This validates the real-site chain up to graph construction, PDDL projection,
and external planner consumption. It does not yet validate robust generic state
understanding.

### Stagehand Business-Milestone Smoke

The current e-commerce Stagehand experiment uses the `business_milestone`
backend mode. Each graph step asks Stagehand to advance one meaningful checkout
milestone through bounded `agentExecute`, and Web-KOBE observes before/after
state once per milestone.

The latest SauceDemo final-order run produced a milestone-shaped graph:

```text
login/product listing
  -> add product to cart
  -> open cart
  -> start checkout
  -> submit checkout information / reach order review
  -> place order / reach checkout complete
```

The run reached `checkout_complete` with 6 projectable business transitions.
Before planner-facing projection hardening, SafeSym parse/inject could consume
the generated PDDL, but Fast Downward solve exposed projection-layer issues:
duplicate readable action names and delete effects for facts not established in
preconditions.

Important caveats from this run:

- Stagehand `agentExecute` completed useful browser work but reported
  `success=false` with `Thinking mode does not support this tool_choice`.
  Web-KOBE now preserves the backend-reported result in metadata while allowing
  observed state changes to define graph transition success.
- Planner-facing action identity is now code-owned and unique; LLM transition
  naming is only the readable suffix.
- PDDL projection now prefers profile/planning facts and keeps low-level
  DOM/control predicates as evidence instead of default planner-facing facts.
- The runner still needs a stronger terminal condition after `order_completed`
  to avoid one extra no-change attempt on the completion page.

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

Likewise, Stagehand's low-level action label is not necessarily the
planner-facing action name. The PDDL projection layer may map a transition such
as "click Finish and `order_created` becomes true" to the business action
`order_place_confirm`, because SafeSym rules operate on planning semantics, not
tool-specific click labels.

The current Stagehand e-commerce benchmark is moving from low-level
`observe()`/single-action execution toward a business-milestone boundary:

```text
observe before state
  -> ask Stagehand to advance exactly one meaningful business milestone
  -> Stagehand may perform multiple low-level click/fill interactions internally
  -> observe after state
  -> compute project-owned deltas
  -> append one WebKobeGraph business edge
```

Low-level Stagehand actions should not become final graph edges or PDDL
actions. They are trace/evidence attached to the business edge. The benchmark
runner now has a `business_milestone` Stagehand backend mode for this
experiment. That mode prefers Stagehand's bounded `execute`/agentExecute path
with a small step limit so Stagehand can complete a milestone internally, while
the older observed-action mode remains useful as a diagnostic baseline.

Do not replace this loop with a single opaque Stagehand `agent()` run as the
main implementation. `agent()` may be useful later as an external baseline, but
the project needs milestone-level transition evidence for SafeSym.

The Stagehand real-site benchmark may still start from SauceDemo as a URL, but
its task prompt should describe generic e-commerce behavior, not a
site-specific script. It must not encode SauceDemo usernames, passwords,
product names, exact button text, or a fixed step sequence. Test data should be
provided through benchmark configuration or task context instead of living in
the generic prompt.

In code, this boundary is represented by the Stagehand prompt builder:

```text
domain guidance = reusable e-commerce checkout prior
benchmark context = current test site credentials and checkout data
action policy = one business milestone per graph transition
safety boundary = whether final order confirmation is allowed
```

The command boundary should follow the same shape:

```text
web-kobe-ecommerce-stagehand-smoke
  --benchmark saucedemo
  --start-url optional override
  --test-username / --test-password / checkout data
```

This keeps SauceDemo as a benchmark configuration rather than the name of the
main architecture path.

For routine experiments, keep only the latest generated artifacts under
`outputs/latest/`. The standard SauceDemo test-site command shape is:

```text
web-kobe web-kobe-ecommerce-stagehand-smoke
  --benchmark saucedemo
  --output outputs/latest/ecommerce_stagehand_graph.json
  --stagehand-trace outputs/latest/ecommerce_stagehand_trace.json
  --screenshot-dir outputs/latest/screenshots
  --clean-output-dir
  --allow-final-order
```

Historical outputs should be copied elsewhere before running with
`--clean-output-dir`.

## State Observation and Planning Facts

State observation is the main current weakness.

The system can collect low-level signals such as URL, title, visible controls,
DOM text, HTML/DOM structure, form fields, and `[data-state]` values. Those are
useful evidence, but they are not sufficient by themselves for good PDDL.
Legacy SauceDemo-specific facts may remain in regression modules, but they
should not be the main observer for objective Stagehand exploration.

PDDL should consume planning-level facts, for example:

```text
logged_in
product_list_visible
cart_has_items
checkout_started
required_info_missing
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

Graph state ownership is intentionally split. `node.planning_state` is a
node-level aggregate of profile facts observed or propagated at that page/context.
It is useful for analysis, terminal-state checks, and future context-aware
frontier selection. `edge.planning_transition` records the transition-local
facts before and after a specific action. PDDL action prediction should prefer
`edge.planning_transition.pre_facts`, `added_facts`, and `removed_facts`, falling
back to the older `planning_delta`/source-node state path only for historical
graphs.

The project should introduce business-type profiles instead of trying to
collect every possible page state. A `BusinessFlowProfile` defines what a class
of websites needs the planner to understand, without binding that abstraction to
one site's selectors or exact URLs.

For example, an e-commerce checkout profile may describe facts such as
`cart_has_items`, `checkout_info_complete`, or
`order_place_pending_sensitive` with semantic meanings and evidence hints:

```text
fact: cart_has_items
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
- Current PDDL projection is intentionally small and STRIPS-oriented. It now
  uses clean planner-facing facts by default, but its semantic quality still
  depends on the quality of `PlanningDelta`.
- Some action names are still too low-level to match SafeSym safety-rule
  patterns reliably as safety triggers, even though PDDL action identity is now
  unique.
- The current visual-delta path asks the VLM provider to return candidate
  profile facts directly. It does not yet split the work into a pure visual
  change summary followed by a separate LLM/parser normalizer.
- The structured verifier is still signature-diff based. DOM, URL, controls,
  form values, and screenshots are evidence sources, but they are not yet
  combined by a general profile-driven verifier.
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

Important current-status distinction:

```text
implemented now:
  before/after screenshots
  + profile fact set
  -> VLM provider returns visible_change_summary
     + candidate_added_facts / candidate_removed_facts
  -> code rejects unknown facts outside the profile
  -> WebKobeGraph edge metadata records the visual_change_summary for review
  -> lightweight signature verifier adds structured verified facts

short-term experiment:
  keep the single VLM call
  require both a human-readable visual_change_summary and profile-bounded
  candidate facts
  run SauceDemo final-order and inspect whether each edge's candidate delta is
  good enough for PDDL/SafeSym experiments

later direction:
  before/after screenshots
  -> VLM visual change summary only
  -> LLM/parser maps that summary into the preset profile fact set
  -> structured verifier checks those candidates against DOM/URL/control/form
     evidence before they become planner-facing truth
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

1. Run the simple single-VLM visual delta experiment on SauceDemo final-order
   and inspect `visual_change_summary` plus candidate facts on each edge.
2. Try the same profile-bounded visual delta approach on one other e-commerce
   site and one forum-like site to understand where the abstraction breaks.
3. Split the current visual-delta path into VLM visual summary and LLM/parser
   fact normalization stages if the single-call path is hard to diagnose or
   too unstable.
4. Add an LLM/parser normalizer that maps summaries to the profile predicate set.
5. Extend the structured verifier to combine model candidates with DOM, URL,
   controls, form values, and known state signals.
6. Validate profile-verified planning deltas on `local_checkout` first, then
   SauceDemo and the additional benchmark sites.

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

src/ai_web_explorer/grounded_web/stagehand_prompt.py
  Stagehand task prompt builder. Keeps reusable domain guidance separate from
  benchmark context and safety mode.

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
  Legacy SauceDemo-specific observation and regression support. These modules
  are not the generic Stagehand exploration observer.

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
