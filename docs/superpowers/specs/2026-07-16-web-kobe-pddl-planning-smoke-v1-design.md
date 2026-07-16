# Web-KOBE PDDL Planning Smoke v1 Design

## Goal

Build a short-term smoke validation path that checks whether an explored
`WebKobeGraph` can produce a planning-usable PDDL model.

The goal is not to validate SafeSym safety injection yet. It is to answer the
smaller and more immediate question:

```text
Can the graph we explored become a non-empty, connected, planner-facing model?
```

This keeps the project focused on the main SafeSym-serving pipeline without
over-investing in general web-agent capability.

## Current Context

The current mainline is:

```text
grounded_web exploration
-> WebKobeGraph JSON
-> web-kobe-pddl-from-graph
-> domain.pddl / problem.pddl
-> later SafeSym / planner use
```

The newly completed projector can:

- load `WebKobeGraph.to_dict()` JSON;
- validate explicit start and goal node IDs;
- project successful observed edges into PDDL actions;
- project boolean facts and positive numeric/count facts into STRIPS predicates;
- write PDDL through the `web-kobe-pddl-from-graph` CLI.

The next useful check is whether the generated model is plausibly usable for
planning before we involve SafeSym safety rules.

## Important SafeSym Boundary

SafeSym has its own planner and safety-injection behavior.

Safety injection is expected to happen only when the planning model contains
actions or predicates that match configured safety rules. If the current
`local_shop` graph does not contain a safety-relevant action such as
`order_place_confirm`, then SafeSym not injecting a safety check is expected
behavior, not a bug.

Therefore this smoke test must separate two concerns:

```text
planning-readiness
  Does the generated PDDL look usable as a planning model?

safety-trigger behavior
  Does the model contain safety-relevant actions that SafeSym rules can match?
```

This v1 smoke test covers only planning-readiness.

## Recommended Scope

Use `local_shop` as the first smoke target because it is local, deterministic,
and already exercises DOM-grounded browser operation and state deltas.

The smoke flow is:

```text
local_shop fixture
-> web-kobe-explore
-> WebKobeGraph JSON
-> web-kobe-pddl-from-graph
-> domain.pddl / problem.pddl
-> smoke_report.json
```

The smoke report should make the model quality visible without pretending to be
a full planner.

## Non-goals

This milestone will not:

- require SafeSym safety injection to trigger;
- require `order_place_confirm`;
- implement or bundle a new planner;
- run Fast Downward;
- run SafeSym automatically;
- infer sensitive actions;
- infer user goals with LLMs;
- add LLM/VLM reasoning;
- expand browser operation capability;
- introduce numeric PDDL fluents;
- solve arbitrary planning problems.

## Proposed CLI

Add a small smoke command:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-pddl-smoke \
  --graph outputs/web_kobe_explored_graph.json \
  --goal-node <goal_node_id> \
  --output outputs/web_kobe_pddl_smoke \
  [--start-node <start_node_id>]
```

The command should:

1. load a `WebKobeGraph` JSON file;
2. validate start and goal nodes;
3. check whether the goal is reachable from the start in the graph using
   projectable edges;
4. compile PDDL using the existing `compile_web_kobe_graph_to_pddl()`;
5. write `domain.pddl` and `problem.pddl`;
6. write `smoke_report.json`.

This command is a validation/reporting wrapper around the existing projector,
not a separate compiler.

## Smoke Report

The report should be stable JSON, for example:

```json
{
  "graph_loaded": true,
  "app": "local_shop",
  "start_node": "shop_empty",
  "goal_node": "shop_cart_open",
  "goal_reachable_in_graph": true,
  "projectable_edge_count": 2,
  "projected_action_count": 2,
  "projected_predicate_count": 5,
  "domain_path": "outputs/web_kobe_pddl_smoke/domain.pddl",
  "problem_path": "outputs/web_kobe_pddl_smoke/problem.pddl",
  "safety_trigger_expected": false,
  "safety_trigger_reason": "No safety-relevant action is required for local_shop planning-readiness smoke."
}
```

Exact node IDs will depend on the explored graph. Tests should use deterministic
fixture graphs rather than relying on a live browser run.

## Reachability Check

The reachability check is a graph sanity check only.

It should:

- start from the selected start node;
- traverse only projectable edges, using the same success/status policy as the
  PDDL projector;
- report whether the selected goal node is reachable.

It should not:

- replace a planner;
- precompute a PDDL plan;
- export only the reachable path;
- judge SafeSym safety behavior.

If the goal is unreachable, the command should still be able to write a report,
but it should not present the smoke as successful.

## Success Criteria

The planning smoke succeeds when:

- graph JSON loads successfully;
- selected start and goal nodes exist;
- goal is reachable from start through projectable edges;
- `domain.pddl` is written;
- `problem.pddl` is written;
- domain contains at least one projected action;
- domain contains predicates;
- problem contains an init section;
- problem contains a goal section;
- report clearly states that safety injection is not expected for this smoke
  unless the graph contains a safety-relevant action.

## Failure Criteria

The planning smoke should fail or report failure when:

- graph JSON cannot be loaded;
- start node is missing;
- goal node is missing;
- no projectable edges exist;
- no PDDL actions are projected;
- goal is not reachable from start;
- PDDL files are not written.

These failures indicate a planning-readiness issue, not necessarily a SafeSym
safety-rule issue.

## Suggested Implementation Shape

Add a focused module:

```text
src/ai_web_explorer/safesym_bridge/web_kobe_pddl_smoke.py
```

Responsibilities:

- compute projectable graph reachability;
- call the existing Web-KOBE PDDL projector;
- count projected actions and predicates conservatively;
- produce a structured smoke report;
- write PDDL and report artifacts.

Keep this module small. It should not know browser automation details and should
not implement SafeSym safety rules.

Extend:

```text
src/ai_web_explorer/safesym_bridge/cli.py
```

with `web-kobe-pddl-smoke`.

## Testing Strategy

Unit tests should use small in-memory `WebKobeGraph` fixtures.

Test cases:

1. reachable goal produces report success and writes PDDL/report files;
2. unreachable goal is reported as not planning-ready;
3. failed/no-change/unexpected edges do not count toward reachability;
4. missing goal raises a clear `ValueError` or returns CLI exit code `1`;
5. report states `safety_trigger_expected: false` for generic local smoke;
6. CLI command writes `domain.pddl`, `problem.pddl`, and `smoke_report.json`.

Do not require a real browser in unit tests.
Do not require SafeSym or Fast Downward in unit tests.

## Later Follow-up

After this smoke passes, the next separate milestone can be:

```text
saucedemo-safety-trigger-regression-v1
```

That later milestone should use SauceDemo or a checkout-like local fixture that
contains a safety-relevant action such as `order_place_confirm`. Its success
criteria may include SafeSym safety-rule matching.

This current milestone intentionally stops before that.
