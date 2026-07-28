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
of the default CLI surface. Their source modules may remain temporarily as
legacy/reference code, but new work should not extend them as the mainline.

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
  --stagehand-execution-mode observed_action `
  --state-embeddings `
  --embedding-model text-embedding-v4 `
  --embedding-dimension 1024 `
  --model deepseek/deepseek-v4-flash `
  --steps 8
```

`business_milestone` mode asks Stagehand to advance one useful milestone.
`observed_action` mode asks Stagehand to observe candidate actions and lets
Web-KOBE select one from the returned candidates. Visual delta requires
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

- `grounded_web` owns browser observation, operation, state deltas, and graph
  construction.
- `safesym_bridge` consumes graph artifacts and writes PDDL/smoke outputs.
- SauceDemo-specific helpers are regression scaffolding, not the generic
  exploration architecture.
- Legacy original-explorer and WebObservedGraph code should be treated as
  reference material unless a future task explicitly revives it.
