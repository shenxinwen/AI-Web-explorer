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
python -m http.server 8000 --directory tests/fixtures/local_shop
```

Explore the page and write a WebKobeGraph:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_shop_web_kobe.json \
  --app-name local_shop \
  --page-id local_shop \
  --steps 3
```

Then check whether the graph can produce planner-facing artifacts:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/local_shop_web_kobe.json \
  --output outputs/local_shop_pddl_smoke \
  --goal-node <goal_node_id>
```

The smoke command writes:

```text
domain.pddl
problem.pddl
smoke_report.json
```

It validates planning readiness only. Missing SafeSym safety injection is not a
failure unless the graph contains a safety-relevant action and rule model that
should trigger it.

## CLI Commands

Current mainline commands:

```text
web-kobe-explore
web-kobe-pddl-from-graph
web-kobe-pddl-smoke
```

Debug helpers:

```text
web-kobe-graph
web-kobe-pddl
```

Older fixed `WebObservedGraph` and capability-graph commands are no longer part
of the default CLI surface. Their source modules may remain temporarily as
legacy/reference code, but new work should not extend them as the mainline.

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
