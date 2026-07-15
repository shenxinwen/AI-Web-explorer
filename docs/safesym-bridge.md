# SafeSym Bridge

The SafeSym bridge turns observed SauceDemo browser behavior into planning
artifacts that can be checked by SafeSym.

The SafeSym regression path is:

```text
real browser exploration
  -> WebObservedGraph
  -> graph-derived PDDL
  -> SafeSym safety injection
  -> planner
```

In CLI terms:

```text
explore-graph -> explore-pddl -> SafeSym
```

Older FSM work is kept only as historical design notes and example artifacts.
The current CLI does not expose the old `fixed` or `observed` FSM commands.

## Current Recommended Path

For generic unknown-site exploration, the active mainline is now the
DOM-grounded Web-KOBE path exposed through `ai_web_explorer.grounded_web` and
the `web-kobe-explore` CLI. The SauceDemo commands in this document remain the
SafeSym end-to-end regression route.

### Explore and write graph JSON

Run from the repository root:

```bash
python -m ai_web_explorer.safesym_bridge.cli explore-graph --output outputs/saucedemo_explored_graph.json
```

This launches a real Playwright browser, lets `GraphExplorer` drive the
SauceDemo adapter, and writes a `WebObservedGraph`.

The graph records:

- abstract page nodes such as `login`, `inventory`, and `checkout_complete`;
- semantic action edges such as `login_submit` and `order_place_confirm`;
- observed state values such as `$.cart_count` and `$.order_created`;
- DOM-backed, adapter-mapped interactable elements for continued exploration.

The DOM observation layer discovers candidate controls first; the SauceDemo
adapter maps checkout-relevant candidates into semantic exploration actions.

### Explore and write PDDL

```bash
python -m ai_web_explorer.safesym_bridge.cli explore-pddl --output outputs/safesym_e2e/explored_graph_pddl
```

This runs the same browser exploration, then compiles the explored graph into:

```text
outputs/safesym_e2e/explored_graph_pddl/domain.pddl
outputs/safesym_e2e/explored_graph_pddl/problem.pddl
```

Those PDDL files are the intended input for the SafeSym safety-injection step.

## Safety-Critical Action

The SauceDemo MVP is centered on the checkout path:

```text
login -> inventory -> cart -> checkout_info -> checkout_overview -> checkout_complete
```

The most important safety action is:

```text
order_place_confirm
```

That action means the user confirmed the order. Its relevant preconditions
include:

- `$.cart_count > 0`
- `$.order_review_ready = true`

Its effect is:

- `$.order_created = true`

SafeSym can inject checks before safety-relevant actions such as
`order_place_confirm`.

## Generic Web-KOBE Direction

The project is adding a Web-KOBE-style exploration graph for unknown web
environments. This does not replace the current SauceDemo graph/PDDL path yet.

The intended long-term chain is:

```text
unknown website
  -> Web-KOBE exploration graph
  -> PDDL projection
  -> SafeSym
```

Debug commands:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-graph --output outputs/web_kobe_graph.json
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl --output outputs/web_kobe_pddl --goal-node start
```

The preferred generic exploration route is the DOM-grounded Web-KOBE explorer:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

This path extracts real DOM interactables, turns them into grounded browser
actions, executes them through a replaceable automation backend, and records
before/after deltas in a Web-KOBE graph. New generic exploration work should
start here.

The original `explore` command can still write a Web-KOBE sidecar graph:

```bash
explore example.com -i 10 --web-kobe-output outputs/example_web_kobe.json
```

That route is compatibility support for the original ai-web-explorer driver. It
is useful for comparison, but it is not the preferred place to add new generic
exploration logic.

SauceDemo is the primary real-site smoke target:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url https://www.saucedemo.com/ \
  --output outputs/saucedemo_web_kobe_graph.json \
  --app-name saucedemo \
  --steps 4
```

For this profile, Web-KOBE reuses the existing SauceDemo state observer and
action profile. This keeps the real browser test deterministic while still
recording browser-grounded Web-KOBE graph edges. Generic pages continue to use
DOM extraction. The optional real SauceDemo verification test is gated by
`RUN_WEB_KOBE_SAUCEDEMO_TEST=1`.

The `web-kobe-explore` command is the current generic operation-and-recording
mainline. Its policy is intentionally simple today; action selection,
deduplication, state recovery, and LLM/VLM semantic assistance should be added
there behind clear interfaces.

## Debug Commands

These commands are still supported, but they are debug shortcuts for the current
graph/PDDL path rather than the recommended browser-exploration path.

### Graph from fixed transitions

```bash
python -m ai_web_explorer.safesym_bridge.cli graph --output outputs/saucedemo_observed_graph.json
```

This writes a graph from fixed MVP transitions. It is useful for debugging graph
serialization without launching a browser.

### PDDL from fixed graph

```bash
python -m ai_web_explorer.safesym_bridge.cli pddl --output outputs/safesym_e2e/graph_pddl
```

This compiles the fixed-transition graph into PDDL. It is useful for fast PDDL
regression tests without browser exploration.

## Run Tests

Default bridge tests:

```bash
pytest tests/safesym_bridge -v
```

Optional real-browser smoke tests:

```bash
RUN_SAUCEDEMO_BROWSER_TEST=1 pytest tests/safesym_bridge/test_browser_runner.py -v
```

The browser tests are skipped by default because they depend on network access,
SauceDemo availability, and local Playwright browser installation.

## Current Boundaries

This bridge is still a SauceDemo MVP.

The current graph-to-PDDL compiler is SauceDemo-specific. It proves that explored
browser behavior can feed the SafeSym planning chain, but it is not yet a
generic compiler for arbitrary websites.

The safety guarantee is model-bounded: SafeSym reasons over the graph/PDDL model
that was observed and compiled. If an action or state is not exposed by the
adapter or graph, the planner does not know it exists.
