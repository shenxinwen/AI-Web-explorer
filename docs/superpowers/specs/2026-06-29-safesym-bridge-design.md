# AI Web Explorer → SafeSym Bridge Design

Date: 2026-06-29

## Goal

Build a first working bridge from `ai-web-explorer` to SafeSym.

The bridge should turn a real browser task on SauceDemo into a SafeSym-compatible FSM JSON file. The output must describe pages, state variables, semantic actions, preconditions, and effects so SafeSym can generate PDDL and inject safety rules.

The first milestone is intentionally narrow:

- Target site: SauceDemo.
- Target task: log in, add an item to cart, start checkout, submit checkout information, and place the order.
- Target output: one FSM JSON file that SafeSym can load.
- Target safety check: `order_place_confirm` is recognized as a financial/property-risk action by SafeSym safety rules.

## Background

`ai-web-explorer` already provides the browser-facing pieces:

- It opens websites.
- It observes pages.
- It proposes actions.
- It executes clicks, fills, and selections through Playwright.
- It records page transitions.

SafeSym needs a more structured model:

- `signature_schema`: page/state variables such as `$.cart_count`.
- Semantic action IDs such as `order_place_confirm`.
- Preconditions such as `$.cart_count > 0`.
- Effects such as `$.order_created = true`.

UI-KOBE is useful as a design reference because it separates screen type from dynamic screen state and records before/after state deltas. This bridge applies the same observation/delta idea to web pages, but the output is different: SafeSym needs a PDDL-oriented FSM, not only a navigation graph.

## Recommended approach

Use `ai-web-explorer` as the browser execution layer and add a separate SafeSym Bridge package.

Do not directly rewrite `loop.py` into a SafeSym exporter. Also do not port UI-KOBE wholesale, because UI-KOBE depends on Android, ADB, screenshots, and AITK-specific action formats.

The architecture is:

```text
SauceDemo web task
  ↓
ai-web-explorer browser/execution capabilities
  ↓
SafeSym Bridge
  ↓
SafeSym FSM JSON
  ↓
SafeSym loader / canonical PDDL / safety injection
```

`ai-web-explorer` remains the “eyes and hands.” The bridge is the “recorder and translator.”

## Package layout

Add a new package:

```text
src/ai_web_explorer/safesym_bridge/
  __init__.py
  models.py
  task_spec.py
  state_observer.py
  transition_recorder.py
  action_semantics.py
  effect_inferer.py
  fsm_exporter.py
  validator.py
  cli.py
```

### `models.py`

Defines small data containers used by the bridge:

- `StateSnapshot`
- `ObservedAction`
- `ObservedTransition`
- `SafeSymAction`
- `SafeSymPage`
- `SafeSymFsm`

These are the bridge’s internal record sheets. They make the data flow explicit before anything is exported as JSON.

### `task_spec.py`

Defines the SauceDemo task:

```json
{
  "app": "saucedemo",
  "start_url": "https://www.saucedemo.com/",
  "goal": "complete_checkout",
  "credentials": {
    "username": "standard_user",
    "password": "secret_sauce"
  }
}
```

The first version can be SauceDemo-specific. Later versions can load task specs from JSON or YAML.

### `state_observer.py`

Observes the current browser page and returns a `StateSnapshot`.

For the MVP, this should use deterministic SauceDemo rules based on URL, DOM, and visible fields. Examples:

- `/` → `page_id = "login"`
- `/inventory.html` → `page_id = "inventory"`
- cart badge text → `$.cart_count`
- checkout overview URL → `$.order_review_ready = true`
- checkout complete URL → `$.order_created = true`

This is inspired by UI-KOBE’s `describe_page_and_state`, but for SauceDemo the first version should prefer stable DOM/URL rules over LLM guesses.

### `transition_recorder.py`

Records one complete browser step:

```text
StateSnapshot before
ObservedAction
StateSnapshot after
```

It produces an `ObservedTransition`.

This is the equivalent of a small flight recorder. Each transition keeps enough evidence to explain why an effect was inferred.

### `effect_inferer.py`

Compares `before.signature` and `after.signature`.

Changed values become effects:

```json
{ "path": "$.cart_count", "op": "set", "value": 1 }
```

For the MVP, preconditions should be simple and rule-based:

- `login_submit` requires `$.username_filled = true` and `$.password_filled = true`.
- `product_add_to_cart` requires `$.is_logged_in = true`.
- `cart_checkout_start` requires `$.cart_count > 0`.
- `checkout_info_submit` requires `$.checkout_info_filled = true`.
- `order_place_confirm` requires `$.cart_count > 0` and `$.order_review_ready = true`.

### `action_semantics.py`

Maps raw browser actions to SafeSym semantic action IDs.

MVP mapping:

| Raw intent | SafeSym action ID |
|---|---|
| Click Login | `login_submit` |
| Click Add to cart | `product_add_to_cart` |
| Click Checkout | `cart_checkout_start` |
| Click Continue from checkout info | `checkout_info_submit` |
| Click Finish | `order_place_confirm` |

This layer is important because SafeSym safety rules match action names. A vague action like `finish_click` may not trigger the right rule; `order_place_confirm` is intentionally risk-readable.

### `fsm_exporter.py`

Converts observed transitions into SafeSym FSM JSON.

The exporter must produce:

```json
{
  "meta": {
    "app": "saucedemo",
    "initial_page_id": "login",
    "terminal_pages": ["checkout_complete"]
  },
  "pages": []
}
```

Each page contains:

- `id`
- `signature_schema`
- `actions`

Each action contains:

- `id`
- `name`
- `from`
- `to`
- `is_navigation`
- `preconditions`
- `effects`

### `validator.py`

Runs local bridge checks before handing the file to SafeSym:

- `meta.app` exists.
- `meta.initial_page_id` exists.
- `pages` is not empty.
- every page has `id` and `signature_schema`.
- every action has `id`, `name`, `from`, and `to`.
- every action’s `from` and `to` reference existing pages.
- every effect path appears in some relevant signature schema.
- `order_place_confirm` exists.

When SafeSym is available, the validator should also check:

- SafeSym loader can read the FSM JSON.
- SafeSym canonical builder can generate PDDL.
- Safety injection marks or constrains `order_place_confirm` as financial/property risk.

### `cli.py`

Provides a first runnable command, for example:

```bash
python -m ai_web_explorer.safesym_bridge.cli run-saucedemo
```

The CLI should produce the FSM JSON and print validation results.

## Target SauceDemo FSM

The MVP models this path:

```text
login
  ↓
inventory
  ↓
cart
  ↓
checkout_info
  ↓
checkout_overview
  ↓
checkout_complete
```

Target pages:

- `login`
- `inventory`
- `cart`
- `checkout_info`
- `checkout_overview`
- `checkout_complete`

Target signature variables:

```json
{
  "$.username_filled": "boolean",
  "$.password_filled": "boolean",
  "$.is_logged_in": "boolean",
  "$.cart_count": "number",
  "$.checkout_started": "boolean",
  "$.checkout_info_filled": "boolean",
  "$.order_review_ready": "boolean",
  "$.order_created": "boolean"
}
```

Target business actions:

| Action ID | From | To | Key effect |
|---|---|---|---|
| `login_submit` | `login` | `inventory` | `$.is_logged_in = true` |
| `product_add_to_cart` | `inventory` | `inventory` | `$.cart_count = 1` |
| `cart_checkout_start` | `cart` | `checkout_info` | `$.checkout_started = true` |
| `checkout_info_submit` | `checkout_info` | `checkout_overview` | `$.order_review_ready = true` |
| `order_place_confirm` | `checkout_overview` | `checkout_complete` | `$.order_created = true` |

`product_add_to_cart` is a self-loop because the page may remain `inventory` while `$.cart_count` changes.

## Example target output fragment

```json
{
  "id": "order_place_confirm",
  "name": "order_place_confirm",
  "from": "checkout_overview",
  "to": "checkout_complete",
  "is_navigation": true,
  "preconditions": [
    { "path": "$.cart_count", "cond": "gt", "value": 0 },
    { "path": "$.order_review_ready", "cond": "eq", "value": true }
  ],
  "effects": [
    { "path": "$.order_created", "op": "set", "value": true }
  ]
}
```

This action is the MVP safety target. It should be recognized by SafeSym as a financial/property-risk action.

## Validation plan

Validation has four layers.

### 1. Bridge structure validation

Check the generated FSM JSON is internally consistent.

Expected result: no missing pages, missing action fields, broken `from`/`to` references, or unknown effect paths.

### 2. SafeSym loader validation

Load the generated FSM JSON with SafeSym’s FSM loader.

Expected result: SafeSym can read the file and expose pages/actions.

### 3. PDDL generation validation

Run SafeSym’s canonical domain builder.

Expected result: generated PDDL includes:

- `login_submit`
- `product_add_to_cart`
- `cart_checkout_start`
- `checkout_info_submit`
- `order_place_confirm`

### 4. Safety rule validation

Run SafeSym safety injection.

Expected result: `order_place_confirm` is matched as financial/property risk and receives the appropriate safety handling.

Fast Downward planning is not a hard requirement for the MVP because planner installation can add unrelated environment noise. The MVP success boundary is:

```text
FSM JSON → SafeSym loader → PDDL generation → safety rule injection
```

## Non-goals for the MVP

The first version does not attempt to support:

- arbitrary real websites.
- full-site random exploration.
- Android apps.
- direct UI-KOBE code migration.
- multiple benchmark tasks.
- automatic repair of all SafeSym/PDDL errors.
- real risky purchases or non-resettable external side effects.

## Success criteria

The MVP is successful when:

1. A SauceDemo run produces a SafeSym FSM JSON file.
2. The file contains the target pages, signature variables, actions, preconditions, and effects.
3. `product_add_to_cart` is represented as a self-loop with a cart-count effect.
4. `order_place_confirm` has preconditions on `$.cart_count` and `$.order_review_ready`.
5. `order_place_confirm` has an effect setting `$.order_created = true`.
6. SafeSym can load the FSM.
7. SafeSym can generate PDDL containing the target actions.
8. SafeSym safety rules identify `order_place_confirm` as a financial/property-risk action.

## Implementation posture

Keep the bridge isolated from existing exploration code.

Prefer adding `src/ai_web_explorer/safesym_bridge/` and reusing existing browser/executor pieces instead of rewriting the main exploration loop. This keeps the original project useful while giving SafeSym a clean, testable integration point.
