# Frontier Replay and Surface PDDL V1 Verification

This note records the local verification boundary for the V1 implementation.
It does not represent a real-site experiment and does not call a VLM or model
API.

## Verification fixture

The environment-gated browser test uses a deterministic local HTML fixture.
The first pass observes a shopping surface, reaches a product surface, and
exhausts it. Reset-and-replay returns to the previously observed shopping
surface, where the remaining `sort` and `filter` candidates can be executed.
The resulting Surface PDDL is compiled from the aggregated graph, so it has no
checkpoint dependency.

The test is:

```text
tests/safesym_bridge/test_web_kobe_playwright_integration.py
  -k frontier_replay_surface_pddl
```

## Results

The deterministic unit and CLI/smoke coverage passed during implementation.
An attempt to run the local browser fixture with
`RUN_WEB_KOBE_BROWSER_TEST=1` was blocked by the environment before the test
started: Playwright Chromium launch returned `spawn EPERM`. Therefore this
note records no browser replay count, discovered graph count, or SafeSym
result as a claimed runtime experiment.

The offline compiler and SafeSym smoke path are covered by:

```text
tests/safesym_bridge/test_surface_pddl.py
tests/safesym_bridge/test_web_kobe_safesym_smoke.py
```

## V1 limitations

- Surface validation uses the existing structured observation boundary and is
  intentionally coarse.
- Replay has no retry for a failed target and makes no hidden-state guarantee.
- Surface PDDL includes only successful aggregated observed edges.
- The implementation makes no claim that the whole site or all capabilities
  have been covered.
