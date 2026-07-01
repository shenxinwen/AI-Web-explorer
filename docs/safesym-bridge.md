# SafeSym Bridge

This bridge generates a SafeSym-compatible FSM JSON for the SauceDemo checkout
task.

The MVP target path is:

```text
login -> inventory -> cart -> checkout_info -> checkout_overview -> checkout_complete
```

The most important safety action is:

```text
order_place_confirm
```

That action means the user confirmed the order. Its preconditions include:

- `$.cart_count > 0`
- `$.order_review_ready = true`

Its effect is:

- `$.order_created = true`

## Generate the fixed FSM

Run from the repository root:

```bash
python -m ai_web_explorer.safesym_bridge.cli --output outputs/saucedemo_fsm.json
```

The explicit subcommand form is also supported:

```bash
python -m ai_web_explorer.safesym_bridge.cli fixed --output outputs/saucedemo_fsm.json
```

Expected result:

```text
Wrote SafeSym FSM to outputs/saucedemo_fsm.json
```

`outputs/` is treated as a local generated-output directory. A committed example
FSM is stored at:

```text
examples/safesym/saucedemo_fsm.json
```

## Generate the browser-observed FSM

The observed mode runs a real Playwright browser flow against SauceDemo, records
the page state before and after each important action, then writes the resulting
SafeSym FSM JSON:

```bash
python -m ai_web_explorer.safesym_bridge.cli observed --output outputs/saucedemo_observed_fsm.json
```

To watch the browser while it runs:

```bash
python -m ai_web_explorer.safesym_bridge.cli observed --headed --output outputs/saucedemo_observed_fsm.json
```

The observed flow currently covers the same safety-critical checkout path as the
fixed MVP:

1. log in as `standard_user`;
2. add one product to the cart;
3. open the cart;
4. enter checkout information;
5. continue to order overview;
6. finish the order.

In beginner terms: fixed mode is a hand-written example of the FSM, while
observed mode lets the browser produce the transition evidence and then converts
that evidence into the same SafeSym-facing shape.

## Run bridge tests

```bash
pytest tests/safesym_bridge -v
```

Expected result:

```text
all tests pass
```

There is also an optional real-browser smoke test. It is skipped by default
because it depends on network access, SauceDemo availability, and local
Playwright browser installation:

```bash
RUN_SAUCEDEMO_BROWSER_TEST=1 pytest tests/safesym_bridge/test_browser_runner.py -v
```

## SafeSym validation boundary

The MVP is successful when:

1. the generated JSON passes bridge validation;
2. SafeSym can load the FSM;
3. SafeSym can generate PDDL from the FSM;
4. SafeSym safety rules identify `order_place_confirm` as a financial/property-risk action.
