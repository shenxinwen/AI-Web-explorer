# Graph-Guided SauceDemo Exploration Design

Date: 2026-07-07

## Goal

Implement a semi-generic browser exploration layer for the SafeSym bridge.

The next milestone should move from a fixed SauceDemo browser script to a graph-guided exploration loop:

```text
browser page
  -> observe state
  -> list candidate actions
  -> choose an unexplored action
  -> execute action
  -> record transition
  -> update WebObservedGraph
  -> generate graph-derived PDDL
```

The target is not generic web exploration yet. The target is a stable v1 that automatically explores the SauceDemo purchase path, produces a `WebObservedGraph`, and keeps the existing graph to PDDL to SafeSym planning chain usable.

## Scope

This stage should build:

1. a reusable exploration controller;
2. a SauceDemo-specific adapter;
3. CLI commands that run browser exploration and write graph/PDDL artifacts;
4. focused tests for exploration control, adapter behavior, graph output, and PDDL compatibility.

This stage should not build:

1. arbitrary website understanding;
2. LLM/VLM page description;
3. generic DOM action extraction;
4. complex search or backtracking;
5. integration with the main `ai-web-explorer` `ExploreLoop`;
6. screenshot, HTML, trace, or embedding sidecar storage.

## Architecture

Use a two-layer architecture:

```text
GraphExplorer
  generic layer: exploration loop, action selection, transition recording, graph writing

SauceDemoAdapter
  site-specific layer: state observation, available actions, action execution, goal detection
```

`GraphExplorer` must not know SauceDemo selectors, URLs, credentials, cart badge behavior, or checkout page names. It should depend only on an adapter interface.

`SauceDemoAdapter` should translate SauceDemo into the generic shape consumed by the explorer.

This keeps the implementation honest: v1 remains SauceDemo-specific in behavior, but the control loop can later be reused with another adapter.

## Core Interfaces

Add an exploration action model:

```python
@dataclass(frozen=True)
class ExplorationAction:
    raw_description: str
    semantic_id: str
    page_id: str
    execution_kind: str
    selector: str | None = None
    values: dict[str, str] = field(default_factory=dict)
```

The adapter interface should provide:

```python
class ExplorationAdapter(Protocol):
    start_url: str
    app_name: str
    start_node: str

    async def observe_state(self, page) -> StateSnapshot:
        ...

    async def list_actions(
        self,
        page,
        state: StateSnapshot,
    ) -> list[ExplorationAction]:
        ...

    async def execute_action(
        self,
        page,
        action: ExplorationAction,
    ) -> None:
        ...

    def is_goal_state(self, state: StateSnapshot) -> bool:
        ...
```

The exact module boundaries can be refined during implementation, but the responsibilities should remain separate.

## Exploration Loop

The v1 loop should be deterministic and easy to test:

```text
open adapter.start_url
current_state = adapter.observe_state(page)

while not adapter.is_goal_state(current_state) and steps < max_steps:
    actions = adapter.list_actions(page, current_state)
    action = choose_next_unexplored_action(current_state, actions, graph)

    if no action exists:
        stop with reason "no_unexplored_actions"

    before = current_state
    adapter.execute_action(page, action)
    after = adapter.observe_state(page)

    transition = ObservedTransition(before, action, after, preconditions, effects)
    append transition
    rebuild graph from transitions
    write graph JSON

    current_state = after
```

The first action selection policy should be simple:

```text
For the current page, choose the first candidate action whose semantic action has not already produced an observed edge from that source node.
```

An edge is considered explored when the graph already contains the same source node and semantic action. Target can be ignored for selection in v1 because SauceDemo actions are deterministic.

The explorer should stop when:

1. the adapter reports a goal state;
2. `max_steps` is reached;
3. there are no unexplored candidate actions for the current page.

Failed actions should not be written into the main `WebObservedGraph`. v1 may keep an in-memory list of failed action descriptions for diagnostics.

## SauceDemo Adapter

The SauceDemo adapter should reuse the existing deterministic observer:

```python
observe_saucedemo_state(page)
```

It should expose only the actions needed for the purchase-path MVP:

```text
login:
  login_submit
  fill #user-name and #password, then click #login-button

inventory:
  product_add_to_cart
  click [data-test="add-to-cart-sauce-labs-backpack"]

inventory:
  cart_open
  click .shopping_cart_link

cart:
  cart_checkout_start
  click #checkout

checkout_info:
  checkout_info_submit
  fill #first-name, #last-name, #postal-code, then click #continue

checkout_overview:
  order_place_confirm
  click #finish
```

The adapter should continue using the existing semantic action names:

```text
login_submit
product_add_to_cart
cart_open
cart_checkout_start
checkout_info_submit
order_place_confirm
```

The goal state is:

```text
state.page_id == "checkout_complete"
and state.signature["$.order_created"] == true
```

Browser-level fill and submit actions may be combined in the adapter. This does not remove the symbolic PDDL fill actions. They operate at different layers:

```text
browser exploration: fill fields and submit in one executable action
PDDL planning: use symbolic fill actions to establish filled-state predicates before submit actions
```

## Graph Updates

For v1, avoid a complex mutable graph API. The explorer should keep:

```python
transitions: list[ObservedTransition]
```

After every successful action, rebuild the graph with:

```python
build_observed_graph(
    app=adapter.app_name,
    start_node=adapter.start_node,
    transitions=transitions,
)
```

This reuses the existing graph builder and keeps behavior predictable.

The graph should also begin using node `interactable_elements`. Candidate actions exposed by the adapter should be represented as lightweight interactable elements on the corresponding node. For v1, these should come only from adapter-declared actions, not generic DOM scanning.

Example:

```json
{
  "description": "Add backpack to cart",
  "position": "product list",
  "explored": true,
  "execution_hints": {
    "selector": "[data-test=\"add-to-cart-sauce-labs-backpack\"]"
  }
}
```

If this adds too much complexity during implementation, the fallback is acceptable: complete the exploration loop and graph edges first, then add populated `interactable_elements` as a follow-up task in the same milestone.

## PDDL Integration

The explorer should not generate PDDL directly. The pipeline should remain:

```text
Adapter -> GraphExplorer -> WebObservedGraph -> PDDL compiler
```

Add CLI support for two workflows:

```powershell
python -m ai_web_explorer.safesym_bridge.cli explore-graph --output outputs\saucedemo_explored_graph.json
```

```powershell
python -m ai_web_explorer.safesym_bridge.cli explore-pddl --output outputs\safesym_e2e\explored_graph_pddl
```

`explore-graph` should run the real browser exploration and write graph JSON.

`explore-pddl` should run exploration, then pass the resulting graph to the existing graph-derived PDDL compiler.

The existing PDDL compiler may remain SauceDemo-specific in this stage. This milestone is about replacing fixed transitions with explored transitions, not about generic graph to PDDL compilation.

## Testing

Use three test layers.

### Unit Tests Without Browser

Use a fake adapter to test `GraphExplorer`:

1. it chooses an unexplored action;
2. it appends a successful transition;
3. it stops on goal;
4. it stops on `max_steps`;
5. it stops when no unexplored actions exist;
6. failed actions do not enter the graph.

### Adapter Tests Without Browser

Construct `StateSnapshot` values and verify SauceDemo action listing:

```text
login -> login_submit
inventory -> product_add_to_cart, cart_open
cart -> cart_checkout_start
checkout_info -> checkout_info_submit
checkout_overview -> order_place_confirm
checkout_complete -> no actions
```

Also verify goal detection for `checkout_complete` with `$.order_created == true`.

### Browser Smoke Test

Add or extend an optional Playwright smoke test. It should be skipped by default if browser/network prerequisites are unavailable.

When enabled, it should verify:

1. the explorer reaches `checkout_complete`;
2. the final state has `$.order_created == true`;
3. graph JSON contains the required nodes and edges.

## Acceptance Criteria

This stage is complete when:

1. `GraphExplorer` exists and drives exploration through an adapter interface;
2. `SauceDemoAdapter` supplies deterministic state, actions, execution, and goal detection;
3. `explore-graph` writes a graph produced by browser exploration;
4. `explore-pddl` writes graph-derived `domain.pddl` and `problem.pddl`;
5. the explored graph contains these nodes:

```text
login
inventory
cart
checkout_info
checkout_overview
checkout_complete
```

6. the explored graph contains these semantic actions:

```text
login_submit
product_add_to_cart
cart_open
cart_checkout_start
checkout_info_submit
order_place_confirm
```

7. PDDL generated from the explored graph still includes:

```text
login_fill_credentials
checkout_info_fill
order_place_confirm
state_order_created
```

8. `tests/safesym_bridge` passes;
9. optional browser smoke test reaches the SauceDemo completion page when enabled.

## Risks and Future Work

The v1 explorer is deterministic and goal-path oriented. It does not prove broad website coverage.

The graph remains trustworthy only within the observed action/state space. If the adapter does not expose an action, the explorer will not discover it.

Future stages can add:

1. richer action selection;
2. limited branch exploration;
3. generic DOM interactable extraction;
4. LLM page description and state proposal;
5. node merging beyond deterministic page IDs;
6. integration with the main `ExploreLoop`;
7. sidecar evidence for screenshots, HTML, and traces.
