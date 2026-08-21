# SafeSym Bridge

The SafeSym bridge consumes Web-KOBE graph artifacts and turns them into
planner-facing files. Its current job is to prove that browser-grounded web
exploration can produce a compact model that SafeSym can later reason over.

```text
webpage
  -> grounded_web exploration
  -> WebKobeGraph
  -> Web-KOBE PDDL projection
  -> domain.pddl / problem.pddl
  -> SafeSym / planner
```

This project is not trying to become a complete web agent. Browser operation,
state recording, and graph construction live in `grounded_web`; SafeSym/PDDL
projection lives here.

## Current Recommended Path

Run a deterministic local fixture first:

```bash
python -m http.server 8000 --directory tests/fixtures/local_checkout
```

Explore the page and write a WebKobeGraph:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6
```

Then check whether the graph can produce planner-facing artifacts:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-domain-from-graph \
  --graph outputs/local_checkout_web_kobe.json \
  --output outputs/local_checkout_domain
```

`web-kobe-domain-from-graph` is the exploration-stage projection path. It writes
only `domain.pddl`, so it does not require choosing a concrete start/goal
planning query.

## Explored Trace PDDL V1

Trace V1 is the recommended Phase A projection. It consumes the ordered
successful events in the frozen Raw Graph and emits an untyped, zero-argument
STRIPS checkpoint machine. A successful action remains eligible when URL and
Raw/Planning nodes are unchanged; successful same-URL/self-loop actions with a
completed `after_observation_id` therefore become trace transitions. Failed
actions and structurally incomplete events remain in `projection_report.json`
with exclusion reasons but do not become checkpoints or actions. DOM and Visual
Delta differences are diagnostic only.

Generate the domain-only trace artifacts:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection trace `
  --graph outputs/experiments/site/graph.json `
  --output outputs/experiments/site/trace_pddl_v1
```

Read the first and last `checkpoint_id` values from
`outputs/experiments/site/trace_pddl_v1/projection_report.json`, then rerun with
both explicit checkpoint flags to create `problem.pddl`:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection trace `
  --graph outputs/experiments/site/graph.json `
  --output outputs/experiments/site/trace_pddl_v1 `
  --start-checkpoint <start_checkpoint_id> `
  --goal-checkpoint <goal_checkpoint_id>
```

The checkpoint query is retrospective and never flows back into exploration,
candidate generation, ranking, or Stagehand prompts. Then run the unchanged
SafeSym smoke over the generated `domain.pddl` and `problem.pddl`:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke `
  --task-dir outputs/experiments/site/trace_pddl_v1 `
  --safesym-root C:\Users\moon\Desktop\Projects\SafeSym `
  --rules C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json `
  --fast-downward C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py
```

Trace V1 describes only the recorded exploration path. It does not claim full
site coverage, branch completeness, semantic state equality, or an optimal
business workflow.

## Location PDDL V1 Compatibility

Use `--projection location` to retain the page-level Planning Graph model. It
uses the frozen Planning Graph as its only planner-facing input and
deterministically emits the generalized schema
`location + (at ?location - location)` and excludes unverified, missing-target,
self-loop, and invalid-action transitions. Visual Delta, profile/supporting
facts, `PlanningState`, embeddings, and the evidence sidecar are not PDDL
inputs. The resulting `projection_report.json` records location/action maps,
Raw edge provenance, and excluded-edge reasons.

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection location `
  --graph outputs/experiments/site/graph.json `
  --output outputs/experiments/site/location_pddl_v1
```

By default `web-kobe-phase-a` writes `raw_graph.json`,
`planning_graph.json`, `planning_abstraction_report.json`,
`projection_report.json`, and `domain.pddl`. It does not write a problem.
After the Planning Graph is frozen, an explicit query may add both parameters:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-phase-a `
  --projection location `
  --graph outputs/experiments/site/graph.json `
  --output outputs/experiments/site/location_pddl_v1 `
  --start-node <planning_node_id> `
  --goal-node <planning_node_id>
```

This writes `problem.pddl` only when the goal is reachable through the same
projectable transitions used for the domain. Start/goal are retrospective
planning-query inputs; they are never passed back to Explorer, candidate
selection, or Stagehand prompts. The legacy fact-rich
`web-kobe-pddl-from-graph` path remains available for diagnostics.

When a diagnostic planning query is needed, generate both `domain.pddl` and
`problem.pddl` with an explicit goal node:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/local_checkout_web_kobe.json \
  --output outputs/local_checkout_pddl_smoke \
  --goal-node <goal_node_id>
```

Then, when a local SafeSym checkout and optional Fast Downward executable are
available, run the real SafeSym consumption smoke:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-safesym-smoke \
  --task-dir outputs/local_checkout_pddl_smoke \
  --safesym-root C:\Users\moon\Desktop\Projects\SafeSym \
  --rules C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json \
  --fast-downward C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py
```

The smoke command writes:

```text
domain.pddl
problem.pddl
smoke_report.json
```

### Graph artifacts and evidence sidecar

The exploration writer emits a compact `graph.json` plus a sibling
`graph_evidence.json`. The compact graph keeps topology, URLs and compact state
signatures, frozen business affordances, action/status/visit data, execution
outcomes, and non-empty planning transitions. Repeated page/node evidence,
verbose instruction and action details, observed/schema deltas, and full
Stagehand/Visual Delta traces remain in the sidecar. A compact node or edge
resolves its `evidence_ref` through `node-evidence:<node_id>` or
`edge-evidence:<edge_id>` in the sidecar.

Historical full graph JSON remains load-compatible, and a compact graph can be
loaded without the sidecar. Phase A reads only `graph.json`; it does not
hydrate or require `graph_evidence.json`, and its `raw_graph.json` preserves the
input JSON shape instead of expanding compact input. Sidecar visual evidence is
diagnostic only and does not enter graph planning state or PDDL. This artifact
layout does not change state naming or exploration semantics; candidate
generation failure/empty distinction remains a separate follow-up.

It validates planning readiness only. The report checks graph reachability,
projected action/predicate counts, and basic static PDDL consistency. In
particular, `pddl_static_consistency_ready` must be true and
`undeclared_predicates` should be empty; otherwise `planning_ready` becomes
false because the generated domain uses predicates that were not declared.

Missing SafeSym safety injection is not a failure unless the graph contains a
safety-relevant action and rule model that should trigger it.

Use `configs/constraint_rules.json` when the goal is to inject check actions
into PDDL. `configs/safety_rules.json` is useful for risk labeling, but it does
not contain the injection configuration used by the SafeSym smoke.

The SafeSym smoke writes `safesym_smoke_report.json`. For the current
`local_checkout` fixture, SafeSym parsing, safety injection, and base/safe
planning can succeed while `safety_actions_inserted` remains false. That is
expected until projected action names become semantic enough to match SafeSym
rules.

`local_checkout` is the current golden-path fixture. It is a deterministic
mini-shopping flow with product, cart, checkout form, and order-complete states.
It avoids login, third-party scripts, random content, and network noise while
still exercising click, fill, state-delta recording, state-specific graph nodes,
and PDDL smoke generation.

## CLI Commands

Current mainline commands:

```text
web-kobe-explore
web-kobe-domain-from-graph
web-kobe-pddl-from-graph
web-kobe-pddl-smoke
web-kobe-safesym-smoke
```

Debug helpers:

```text
web-kobe-graph
web-kobe-pddl
```

Older fixed `WebObservedGraph` and capability-graph commands are no longer part
of the default CLI surface. The old `WebObservedGraph` exploration stack has
been removed from the active source tree; historical notes remain only in
archival design documents.

### Stagehand-Backed E-Commerce Graph Smoke

```powershell
$env:STAGEHAND_SERVER = "local"
$env:STAGEHAND_MODEL = "deepseek/<your-model-name>"
$env:MODEL_API_KEY = "<your-deepseek-key>"
python -m ai_web_explorer.safesym_bridge.cli web-kobe-ecommerce-stagehand-smoke `
  --benchmark saucedemo `
  --output outputs/latest/ecommerce_stagehand_graph.json `
  --stagehand-trace outputs/latest/ecommerce_stagehand_trace.json `
  --steps 10
```

This command is opt-in because real Stagehand runs require external credentials
and browser/model access. Default tests use fake providers.

For BYO model-key runs, set the generic `MODEL_API_KEY`, which is the
recommended Python SDK input. This runner loads `.env`, reads `STAGEHAND_MODEL`,
and also accepts provider-specific aliases such as `DEEPSEEK_API_KEY` for
`deepseek/...` models. The recommended runner mode is `STAGEHAND_SERVER=local`,
which lets Stagehand operate on the same Playwright page that Web-KOBE observes.
`STAGEHAND_API_URL` may be set for a custom Stagehand service endpoint; it is
not the DeepSeek/OpenAI-compatible model provider base URL.

The current verified DeepSeek-backed local run reached `checkout_overview` in
10 low-level Stagehand steps and did not click `Finish`. A follow-up
`web-kobe-pddl-smoke` over `outputs/saucedemo_stagehand_graph.json` reported
`planning_ready=True` and no undeclared predicates.

For the SauceDemo test site only, the runner can explicitly continue through
the final confirmation action:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-ecommerce-stagehand-smoke `
  --benchmark saucedemo `
  --output outputs/latest/ecommerce_stagehand_graph.json `
  --stagehand-trace outputs/latest/ecommerce_stagehand_trace.json `
  --screenshot-dir outputs/latest/screenshots `
  --openai-visual-delta `
  --visual-delta-model gpt-4o `
  --steps 12 `
  --allow-final-order
```

Without `--allow-final-order`, the Stagehand smoke intentionally stops at
checkout overview, so no final order safety action is expected. With the flag,
the projected PDDL should contain a SafeSym-facing order confirmation action,
`order_place_confirm`, even if the low-level Stagehand action description is
something like `click Finish`.

The current verified final-order run reached `checkout_complete` in 11
Stagehand-backed transitions. PDDL smoke reported `planning_ready=True`,
projected `order_place_confirm`, and SafeSym with `constraint_rules.json`
inserted:

```text
check_human_confirmation_order_place_confirm
```

### Generic Stagehand Exploration

The generic Stagehand runner is the bounded-exploration integration surface. It
can now reuse the existing profile, visual-delta, embedding, and Stagehand
candidate-action capabilities:

Stagehand and screenshot observation retain separate model settings, but all
three paths now default to GPT-4o. Set `STAGEHAND_MODEL` (or `--model`) only for
Stagehand action execution. Candidate observation defaults to `gpt-4o` and uses
`OPENAI_VISUAL_DELTA_MODEL` (or `--visual-delta-model`); action-outcome observation defaults to `gpt-4o` and
uses `OPENAI_ACTION_OUTCOME_MODEL` (or `--action-outcome-model`). These OpenAI
providers are independent, and explicit provider injection remains supported.
Never copy the Stagehand model name into either observation option unless that
separate OpenAI-compatible endpoint explicitly exposes the same model ID.
Embeddings use `EMBEDDING_MODEL` independently.

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-stagehand-explore `
  --url https://www.saucedemo.com/ `
  --app-name saucedemo `
  --output outputs/experiments/saucedemo/latest/stagehand_explore_graph.json `
  --stagehand-trace outputs/experiments/saucedemo/latest/stagehand_explore_trace.json `
  --screenshot-dir outputs/experiments/saucedemo/latest/screenshots `
  --business-profile ecommerce_checkout `
  --openai-visual-delta `
  --visual-delta-model gpt-4o `
  --action-outcome-model gpt-4o `
  --state-embeddings `
  --embedding-model text-embedding-v4 `
  --embedding-dimension 1024 `
  --model openai/gpt-4o `
  --steps 8
```

`observed_action` is the default mode for generic exploration. In the preferred
bounded-exploration path, VLM proposes business affordances from screenshots,
Web-KOBE selects and deduplicates with graph/embedding memory, and Stagehand
executes the selected business action. `business_milestone` remains available
as a legacy fallback mode and for checkout benchmark smoke paths, but it should
not be treated as the main generic exploration path. Visual delta requires
`--screenshot-dir` because it compares before/after screenshots.

## SauceDemo Role

SauceDemo remains useful as an app-specific regression target, especially for
future safety-trigger scenarios such as checkout confirmation:

```text
login -> inventory -> cart -> checkout_info -> checkout_overview -> checkout_complete
```

The safety-relevant action in that flow is:

```text
order_place_confirm
```

SafeSym can only inject checks for actions and predicates represented in the
exported model. If a WebKobeGraph does not contain a safety-relevant action, the
planner not triggering a safety rule is expected.

The PDDL projection layer may translate low-level browser action names into
planning-level action names when the transition evidence supports it. For
example, an edge that creates `order_created` is projected as
`order_place_confirm` so SafeSym rules can match the business action rather
than a tool-specific click label.

## Run Tests

Default bridge tests:

```bash
pytest tests/safesym_bridge -q
```

Some tests launch Playwright Chromium. In restricted sandboxes they may need to
be run with local browser execution permission.

## Current Boundaries

The location-scoped active path now has a minimal dependency-driven contract:
one strict initial screenshot response supplies `actions` with same-location
`requires`; each execution is followed by only `outcome`, `location_change`,
and visible `evidence`. Local memory schedules satisfied dependencies and
creates location-scoped completion predicates for successful actions. Missing,
invalid, cyclic, or over-limit dependency responses fail closed, and
failed/uncertain outcomes do not create planner-facing state or locations.
Offline bridge regression covers this path; a fresh Practice Shopping VLM run
followed by SafeSym and planner acceptance is still pending.

- `grounded_web` owns browser observation, operation, state deltas, and graph
  construction.
- `safesym_bridge` consumes graph artifacts and writes PDDL/smoke outputs.
- SauceDemo-specific helpers are regression scaffolding, not the generic
  exploration architecture.
- Legacy original-explorer and WebObservedGraph designs are archival reference
  material only. Active code should use `WebKobeGraph`.
