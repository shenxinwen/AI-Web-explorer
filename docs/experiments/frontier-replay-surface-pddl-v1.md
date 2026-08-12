# Entry Frontier Replay and Surface PDDL V1.1 Verification

This note records the local verification boundary for Entry Frontier V1.1.
It does not represent a real-site experiment and does not call a real VLM or
model API.

## Verification fixture

The environment-gated browser test uses a deterministic local HTML fixture.
The entry surface provides three generic candidates. The first pass observes
the entry surface, reaches a deeper surface, and exhausts it. Entry frontier
replay resets and validates the entry state with an empty replay path; the
following normal exploration step executes one remaining entry candidate.
The resulting Surface PDDL is compiled from the aggregated graph, so it has no
checkpoint dependency.

The test is:

```text
tests/safesym_bridge/test_web_kobe_playwright_integration.py
  -k frontier_replay_surface_pddl
```

The intended bounded experiment configuration is:

```text
--steps 10
--max-candidates 5
--frontier-replay
--openai-visual-delta
--screenshot-dir <experiment screenshots>
--stagehand-execution-mode observed_action
```

Five is an upper bound, not a quota. Candidate refresh on revisit is not part
of this experiment.

## Results

The deterministic unit and CLI/smoke coverage passed during implementation.
An attempt to run the local browser fixture with
`RUN_WEB_KOBE_BROWSER_TEST=1` was blocked by the environment before the test
started: Playwright Chromium launch returned `spawn EPERM`. Therefore this
note records no browser replay count, discovered graph count, or SafeSym
result as a claimed runtime experiment.

When the fixture is runnable, the acceptance report must record candidate
counts per visited surface, replay attempts/successes/failures, blocked
frontier IDs, node and edge counts, deepest verified surface, Surface PDDL
domain/problem paths, and SafeSym parse/base/safe results.

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
- Candidate recall remains bounded by the first VLM observation of each
  surface; five candidates reduces premature omission but does not guarantee
  full coverage.
- The implementation makes no claim that the whole site or all capabilities
  have been covered.
