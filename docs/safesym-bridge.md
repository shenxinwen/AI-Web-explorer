# SafeSym Bridge

The SafeSym bridge turns observed SauceDemo browser behavior into planning
artifacts that can be checked by SafeSym.

The current recommended path is:

```text
real browser exploration
  -> WebObservedGraph
  -> graph-derived PDDL
  -> SafeSym safety injection
  -> planner
```

In CLI terms, the active commands are:

```text
explore-graph
explore-pddl
```

Earlier FSM export commands were removed after `WebObservedGraph -> PDDL`
became the primary bridge path. The historical design notes remain under
`docs/superpowers/` for context, but the runtime code now follows the graph/PDDL
path only.

## Current Recommended Path

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
- adapter-declared interactable elements for continued exploration.

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
