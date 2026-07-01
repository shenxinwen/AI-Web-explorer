# Browser-Observed SafeSym Bridge Design

Date: 2026-07-01

## Goal

Upgrade the current SauceDemo SafeSym Bridge from a fixed, pre-authored transition sequence to a browser-observed transition sequence.

The current bridge can already generate a SafeSym-compatible FSM JSON from deterministic SauceDemo snapshots. This next stage should open SauceDemo in a real browser, execute the checkout task, observe page state before and after each action, infer effects, export FSM JSON, and keep the same SafeSym validation path.

## Current baseline

Already implemented:

- `models.py`: bridge data models.
- `action_semantics.py`: raw action text to SafeSym action IDs.
- `effect_inferer.py`: before/after signature delta to effects, plus rule-based preconditions.
- `fsm_exporter.py`: observed transitions to SafeSym FSM.
- `task_spec.py`: fixed SauceDemo MVP transitions.
- `validator.py`: bridge validation and optional SafeSym loader validation.
- `cli.py`: fixed FSM JSON generation.
- `examples/safesym/saucedemo_fsm.json`: committed example FSM.

Verified behavior:

- Bridge tests pass.
- SafeSym can load the generated FSM.
- SafeSym canonical builder supports all generated preconditions/effects.
- `order_place_confirm` matches financial/property risk.
- `constraint_rules.json` injects `check_human_confirmation_order_place_confirm`.

## New target behavior

Add a new browser-observed flow:

```text
Open SauceDemo
  ↓
observe login snapshot
  ↓
fill credentials and click Login
  ↓
observe inventory snapshot
  ↓
click Add to cart
  ↓
observe inventory snapshot with cart_count = 1
  ↓
open cart
  ↓
observe cart snapshot
  ↓
click Checkout
  ↓
observe checkout_info snapshot
  ↓
fill checkout information and click Continue
  ↓
observe checkout_overview snapshot
  ↓
click Finish
  ↓
observe checkout_complete snapshot
  ↓
export SafeSym FSM
```

The output should be written to:

```text
outputs/saucedemo_observed_fsm.json
```

`outputs/` remains ignored by git.

## Recommended approach

Use deterministic Playwright and DOM/URL rules for this stage.

Do not use LLMs for the first browser-observed flow. SauceDemo is simple and stable; URL and CSS selectors are more reliable, cheaper, and easier to test.

Do not rewrite the existing ai-web-explorer exploration loop. The first browser-observed bridge should be isolated inside `src/ai_web_explorer/safesym_bridge/`.

## New modules

Add:

```text
src/ai_web_explorer/safesym_bridge/state_observer.py
src/ai_web_explorer/safesym_bridge/transition_recorder.py
src/ai_web_explorer/safesym_bridge/browser_runner.py
```

### `state_observer.py`

Responsibility: turn a real browser page into a `StateSnapshot`.

The observer should use:

- current URL,
- page title,
- DOM selectors,
- input values,
- cart badge text,
- page-specific markers.

It should expose:

```python
async def observe_saucedemo_state(page) -> StateSnapshot:
    ...
```

Suggested page ID rules:

| Browser URL / marker | `page_id` |
|---|---|
| root URL or login form visible | `login` |
| `/inventory.html` | `inventory` |
| `/cart.html` | `cart` |
| `/checkout-step-one.html` | `checkout_info` |
| `/checkout-step-two.html` | `checkout_overview` |
| `/checkout-complete.html` | `checkout_complete` |

Suggested signature rules:

| Signature path | How to observe |
|---|---|
| `$.username_filled` | username input value is non-empty |
| `$.password_filled` | password input value is non-empty |
| `$.is_logged_in` | inventory/cart/checkout pages, or menu/logout marker |
| `$.cart_count` | shopping cart badge text; default `0` |
| `$.checkout_started` | checkout page URL or later |
| `$.checkout_info_filled` | checkout first/last/postal inputs are non-empty |
| `$.order_review_ready` | checkout overview URL |
| `$.order_created` | checkout complete URL or complete header visible |

The observer should include only stable, task-relevant values.

### `transition_recorder.py`

Responsibility: record one high-level observed transition.

It should expose:

```python
async def record_transition(page, raw_description: str, action_coro) -> ObservedTransition:
    ...
```

The function should:

1. observe state before the action;
2. map `raw_description` to `semantic_id`;
3. await the provided action coroutine;
4. observe state after the action;
5. infer preconditions and effects;
6. return an `ObservedTransition`.

This mirrors UI-KOBE’s useful pattern:

```text
detail_before → execute action → detail_after → schema_delta
```

For this project, the output is:

```text
StateSnapshot before → action → StateSnapshot after → SafeSym effects
```

### `browser_runner.py`

Responsibility: run the SauceDemo checkout task in a real browser and export an observed FSM.

It should expose:

```python
async def run_saucedemo_observed_flow(output_path: Path, *, headless: bool = True) -> Path:
    ...
```

The runner should:

1. launch Playwright Chromium;
2. open `https://www.saucedemo.com/`;
3. execute the known SauceDemo task;
4. record high-level transitions;
5. build FSM via `build_fsm`;
6. validate with `validate_fsm`;
7. write JSON to `output_path`;
8. close the browser even if an error occurs.

Known user inputs:

```text
username: standard_user
password: secret_sauce
first name: Safe
last name: Sym
postal code: 12345
```

Known high-level raw action descriptions:

```text
Click the Login button
Click Add to cart
Click the shopping cart link
Click Checkout
Click Continue on checkout information
Click Finish
```

These are intentionally the same phrases already covered by `action_semantics.py`.

## CLI change

Extend the existing bridge CLI to support two modes:

```bash
python -m ai_web_explorer.safesym_bridge.cli fixed --output outputs/saucedemo_fsm.json
python -m ai_web_explorer.safesym_bridge.cli observed --output outputs/saucedemo_observed_fsm.json
```

For backward compatibility, the old no-subcommand behavior may keep generating the fixed FSM.

## Testing strategy

Use tests in layers.

### Unit tests

Test pure helper logic without launching a browser:

- URL to page ID mapping.
- cart badge parsing.
- signature construction from mocked values if helper functions are extracted.
- transition recorder behavior with fake observer/action functions where practical.

### CLI tests

Keep existing fixed-mode CLI tests.

Add tests that verify:

- `fixed` subcommand writes JSON.
- `observed` subcommand delegates to the observed runner.

The CLI test should not launch a real browser; monkeypatch the runner function.

### Browser smoke test

Add a browser smoke test only if Playwright browsers are available in the environment. Otherwise skip with a clear reason.

This avoids making the normal unit test suite depend on browser installation.

## Validation plan

After implementation:

1. Run bridge unit tests.
2. Run the observed CLI against SauceDemo.
3. Verify the generated FSM contains:
   - `login_submit`
   - `product_add_to_cart`
   - `cart_open`
   - `cart_checkout_start`
   - `checkout_info_submit`
   - `order_place_confirm`
4. Verify `order_place_confirm` has:
   - precondition `$.cart_count > 0`
   - precondition `$.order_review_ready = true`
   - effect `$.order_created = true`
5. Run SafeSym loader/canonical/safety validation using the observed FSM.

## Non-goals

This stage does not attempt to support:

- arbitrary websites;
- random exploration;
- LLM-based state observation;
- automatic recovery from every UI failure;
- real purchases or non-resettable side effects;
- replacing the existing ai-web-explorer loop.

## Success criteria

This stage is successful when:

1. `python -m ai_web_explorer.safesym_bridge.cli observed --output outputs/saucedemo_observed_fsm.json` runs successfully in an environment with Playwright browsers installed.
2. The observed FSM contains the same core action IDs as the fixed MVP FSM.
3. The observed FSM passes bridge validation.
4. SafeSym can load the observed FSM and build canonical PDDL with no unsupported preconditions or effects.
5. `order_place_confirm` matches financial/property risk and receives human-confirmation constraint injection.
