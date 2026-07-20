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

### Stagehand-Backed SauceDemo Graph Smoke

```powershell
$env:STAGEHAND_SERVER = "local"
$env:STAGEHAND_MODEL = "deepseek/<your-model-name>"
$env:MODEL_API_KEY = "<your-deepseek-key>"
python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke `
  --output outputs/saucedemo_stagehand_graph.json `
  --stagehand-trace outputs/saucedemo_stagehand_trace.json `
  --steps 10
```

To use SauceDemo as a full checkout safety-trigger regression, explicitly allow
the final `Finish` click and give the runner enough steps:

```powershell
python -m ai_web_explorer.safesym_bridge.cli web-kobe-saucedemo-stagehand-smoke `
  --output outputs/saucedemo_stagehand_final_order_graph.json `
  --stagehand-trace outputs/saucedemo_stagehand_final_order_trace.json `
  --steps 12 `
  --allow-final-order
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
If the local Stagehand SEA server starts listening but does not become ready
within the SDK default window, set `STAGEHAND_LOCAL_READY_TIMEOUT_S` to a larger
value such as `45`.
The project Stagehand provider also ensures `127.0.0.1` and `localhost` are
added to `NO_PROXY` / `no_proxy` for local runs, because some Windows VPN or
system proxy setups otherwise route the SDK localhost readiness check through a
proxy and cause a timeout before SauceDemo is reached.

The current verified DeepSeek-backed local run reached `checkout_overview` in
10 low-level Stagehand steps and did not click `Finish`. A follow-up
`web-kobe-pddl-smoke` over `outputs/saucedemo_stagehand_graph.json` reported
`planning_ready=True` and no undeclared predicates.

A later full-chain run used DeepSeek for Stagehand and `gpt-4o` for
observation-side visual delta with `--openai-visual-delta`,
`--visual-delta-model gpt-4o`, and `--screenshot-dir`. It produced a graph,
screenshots, PDDL artifacts, and SafeSym base/safe plans. When
`--allow-final-order` is omitted, no safety actions are expected because the
graph stops at `checkout_overview` and does not include the final order
placement action.

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
