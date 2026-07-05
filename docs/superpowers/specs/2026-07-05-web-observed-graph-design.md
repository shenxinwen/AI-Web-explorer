# Web Observed Graph Design

Date: 2026-07-05

## Goal

Introduce a UI-KOBE-inspired Web Observed Graph as the central exploration artifact for the SafeSym bridge.

The graph should support two downstream uses:

1. guide continued LLM/browser exploration of a website;
2. export the safety-relevant subset into SafeSym-compatible FSM JSON.

The graph is not a complete evidence archive. It should stay compact, readable, and centered on page-state modeling.

## Design principle

Use the graph while exploring, not only after exploration.

The intended loop is:

```text
observe current page
  -> identify or create graph node
  -> merge page state and interactable elements
  -> choose an unexplored or underexplored element/action
  -> execute browser action
  -> observe target page
  -> identify or merge target node
  -> record edge and state delta
  -> save graph
```

This mirrors UI-KOBE's useful pattern:

```text
identify screen node
  -> collect dynamic state and interactable elements
  -> plan next action from current graph context
  -> execute action
  -> identify next node
  -> add edge
  -> mark interacted element explored
```

## What to borrow from UI-KOBE

### Abstract page nodes

Nodes represent reusable page types, not one concrete URL or one screenshot.

Examples:

```text
product_detail
product_listing
cart
checkout_information
checkout_review
```

For a shopping site, these URLs may all map to the same abstract node:

```text
/products/iphone-15
/products/macbook-pro
/products/airpods
```

The node should be `product_detail`; product-specific values belong in state.

### Dynamic state belongs in the node schema

Like UI-KOBE's `state_schema`, a web node should accumulate dynamic state values observed across visits.

Static UI labels, fixed navigation links, decorative elements, and page chrome should not become state variables.

Good state examples:

```text
$.product_id
$.price
$.in_stock
$.cart_count
$.active_filter
$.search_query
```

Bad state examples:

```text
$.has_logo
$.has_footer
$.checkout_button_visible
$.site_title
```

### Interactable elements live on nodes

Each node should store a lightweight list of interactable elements to support continued exploration.

This should follow the UI-KOBE style:

```json
{
  "description": "Add to cart buttons",
  "position": "product list",
  "explored": false
}
```

The graph should group content-like repeated elements.

Good:

```text
product result items
Add to cart buttons
category links
```

Avoid:

```text
iPhone 15 Add to cart button
MacBook Pro Add to cart button
AirPods Add to cart button
```

Specific product names belong in state, not in the abstract element list.

### Edges record explored actions

Edges should record the action that moved the browser from one abstract node to another, plus the state change observed around that action.

For SafeSym export, one edge should correspond to one semantic action. This differs slightly from UI-KOBE, which may aggregate multiple low-level actions under the same source-target edge.

The bridge should prefer:

```text
source + target + semantic_action
```

as the edge identity.

## What not to put in the main graph

To keep the graph readable, do not store the following in the main graph JSON:

- merge reasoning;
- LLM explanations;
- confidence scores;
- full screenshots;
- screenshot crops;
- embedding vectors;
- full HTML;
- long DOM excerpts;
- complete Playwright traces.

If needed later, store these in sidecar artifacts:

```text
outputs/evidence/<run_id>/screenshots/
outputs/evidence/<run_id>/html/
outputs/evidence/<run_id>/embeddings.json
outputs/evidence/<run_id>/trace.jsonl
```

The main graph may keep short references to sidecar artifacts in the future, but v1 should not require them.

## Graph schema v1

### Top-level document

```json
{
  "meta": {
    "schema_version": "web-observed-graph-v1",
    "app": "saucedemo",
    "start_node": "login",
    "total_steps_completed": 6
  },
  "nodes": [],
  "edges": []
}
```

### Node

```json
{
  "id": "inventory",
  "page_description": "product listing page",
  "url_patterns": ["/inventory.html"],
  "state_schema": {
    "$.is_logged_in": "boolean",
    "$.cart_count": "number"
  },
  "observed_values": {
    "$.is_logged_in": [true],
    "$.cart_count": [0, 1]
  },
  "last_state_snapshot": {
    "$.is_logged_in": true,
    "$.cart_count": 1
  },
  "interactable_elements": [
    {
      "description": "Add to cart buttons",
      "position": "product list",
      "explored": true,
      "execution_hints": {
        "role": "button",
        "label": "Add to cart",
        "selector": "[data-test^='add-to-cart']"
      }
    },
    {
      "description": "shopping cart link",
      "position": "top right",
      "explored": true,
      "execution_hints": {
        "label": "shopping cart",
        "selector": ".shopping_cart_link"
      }
    }
  ],
  "visit_count": 2
}
```

Field notes:

- `id`: stable abstract node ID used by edges and SafeSym export.
- `page_description`: short semantic page type. It should not contain user-specific or item-specific values.
- `url_patterns`: compact URL patterns observed for this abstract page type.
- `state_schema`: state variable type information.
- `observed_values`: concrete values seen across visits.
- `last_state_snapshot`: latest observed value for each known state key.
- `interactable_elements`: lightweight exploration affordances.
- `execution_hints`: optional hints for browser execution. They are not required and must not be used by SafeSym export.
- `visit_count`: number of times this abstract node has been observed.

`execution_hints` should be treated as hints, not proof. Runtime should try them first and fall back to role/text/LLM execution if they fail.

### Edge

```json
{
  "source": "inventory",
  "target": "inventory",
  "semantic_action": "product_add_to_cart",
  "instructions": ["Click Add to cart"],
  "target_observations": ["product listing page with cart_count=1"],
  "schema_deltas": [
    {
      "$.cart_count": {
        "before": 0,
        "after": 1
      }
    }
  ],
  "preconditions": [
    {
      "path": "$.is_logged_in",
      "cond": "eq",
      "value": true
    }
  ],
  "effects": [
    {
      "path": "$.cart_count",
      "op": "set",
      "value": 1
    }
  ],
  "visit_count": 1
}
```

Field notes:

- `source` and `target`: abstract node IDs.
- `semantic_action`: SafeSym-facing action name.
- `instructions`: raw natural-language instructions that produced this edge.
- `target_observations`: compact summaries of the post-action state.
- `schema_deltas`: raw before/after differences useful for graph exploration and audit.
- `preconditions`: SafeSym-facing action preconditions.
- `effects`: SafeSym-facing action effects.
- `visit_count`: number of successful observations of this semantic edge.

## Exploration behavior

### Page observation

The observer should return:

```text
page_description
state
interactable_elements
url
title
```

For the first version, SauceDemo can use deterministic DOM/URL rules. Later, a web VLM/LLM describer can produce the same shape.

The LLM prompt should follow UI-KOBE's key rule:

```text
page_description is the page type;
dynamic user/product/task data belongs in state.
```

### Node identification

v1 can identify SauceDemo nodes with deterministic page IDs.

The schema should leave room for future LLM/embedding-based merging, but the graph JSON should not store merge evidence.

Future node matching may use:

- URL pattern similarity;
- page description similarity;
- state key similarity;
- interactable element similarity;
- optional screenshot verification.

Only the resulting merged node should be written to the main graph.

### Element exploration

The planner should prefer unexplored elements from the current node.

After a successful edge is recorded, the matching interactable element should be marked:

```json
{"explored": true}
```

Matching can start simple: compare the selected instruction against element descriptions.

### Edge recording

When an action succeeds:

1. record source node;
2. record target node;
3. map raw instruction to `semantic_action`;
4. compute schema delta from before/after state;
5. infer or attach SafeSym preconditions;
6. infer or attach SafeSym effects;
7. increment edge visit count if the same semantic edge already exists.

When an action fails, v1 may log it outside the graph. Failed actions should not be exported to SafeSym.

## SafeSym export

The SafeSym exporter should read only the safety/planning subset:

From nodes:

- `id`;
- `state_schema`.

From edges:

- `source`;
- `target`;
- `semantic_action`;
- `preconditions`;
- `effects`.

The exporter should ignore:

- `interactable_elements`;
- `execution_hints`;
- `instructions`;
- `target_observations`;
- `schema_deltas`;
- `visit_count`;
- sidecar evidence.

This keeps SafeSym's FSM clean while preserving enough graph information for continued exploration.

## Relationship to current bridge

Current bridge data models:

```text
StateSnapshot
ObservedTransition
SafeSymFsm
```

Proposed addition:

```text
WebObservedGraph
WebObservedNode
WebObservedEdge
InteractableElement
```

The current SauceDemo observed flow can become:

```text
StateSnapshot before/after
  -> ObservedTransition
  -> WebObservedGraph.add_transition(...)
  -> graph_to_safesym_fsm(...)
```

This is an incremental change. It should not require rewriting `loop.py` yet.

## First implementation scope

v1 should support:

1. building a WebObservedGraph from the existing SauceDemo observed flow;
2. saving the graph to `outputs/saucedemo_observed_graph.json`;
3. exporting the graph to the existing SafeSym FSM shape;
4. preserving current fixed and observed CLI behavior;
5. keeping all existing SafeSym bridge tests green.

Do not implement generic LLM/embedding node merging in v1.

Do not integrate the main `ai-web-explorer` `ExploreLoop` in v1.

Those should be follow-up stages after the graph model is stable.

## Open follow-up stages

After v1:

1. graph audit CLI;
2. graph-guided SauceDemo exploration;
3. LLM page describer that outputs `page_description`, `state`, and `interactable_elements`;
4. abstract node merging using page descriptions and element/state similarity;
5. integration with `ExploreLoop`;
6. sidecar evidence storage for screenshots, HTML, embeddings, and traces.
