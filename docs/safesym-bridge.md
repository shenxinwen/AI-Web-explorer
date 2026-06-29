# SafeSym Bridge

This bridge generates a SafeSym-compatible FSM JSON for the SauceDemo checkout task.

The MVP target path is:

```text
login → inventory → cart → checkout_info → checkout_overview → checkout_complete
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

## Generate the FSM

Run from the repository root:

```bash
python -m ai_web_explorer.safesym_bridge.cli --output outputs/saucedemo_fsm.json
```

Expected result:

```text
Wrote SafeSym FSM to outputs/saucedemo_fsm.json
```

## Run bridge tests

```bash
pytest tests/safesym_bridge -v
```

Expected result:

```text
all tests pass
```

## SafeSym validation boundary

The MVP is successful when:

1. the generated JSON passes bridge validation;
2. SafeSym can load the FSM;
3. SafeSym can generate PDDL from the FSM;
4. SafeSym safety rules identify `order_place_confirm` as a financial/property-risk action.
