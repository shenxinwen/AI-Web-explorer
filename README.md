# AI Web Explorer

This repository is being shaped into a SafeSym-oriented web environment
explorer. Its current mainline is not a general-purpose web agent; it is a
pipeline for observing webpages, recording state-changing browser actions, and
projecting the resulting graph into planner-facing artifacts.

```text
real webpage
  -> DOM-grounded observation and browser action execution
  -> WebKobeGraph
  -> Web-KOBE PDDL projection
  -> SafeSym/planner-facing artifacts
```

The old upstream `explore` runtime has been removed from the active package.
New work should use the Web-KOBE/SafeSym path.

## Current Mainline

The active generic exploration package is:

```text
src/ai_web_explorer/grounded_web/
```

It owns:

- DOM-grounded page observation;
- action candidate extraction;
- browser action execution through a replaceable automation backend;
- state facts and typed deltas;
- WebKobeGraph construction.

The SafeSym bridge package is:

```text
src/ai_web_explorer/safesym_bridge/
```

It consumes `grounded_web` graph artifacts and writes SafeSym/PDDL-facing
outputs. It should not own generic exploration policy.

## CLI

After installing the package, the current mainline CLI is available as:

```bash
web-kobe --help
```

You can also run it directly from the repository root:

```bash
python -m ai_web_explorer.safesym_bridge.cli --help
```

Recommended flow:

```bash
python -m http.server 8000 --directory tests/fixtures/local_checkout

web-kobe web-kobe-explore \
  --url http://127.0.0.1:8000/index.html \
  --output outputs/local_checkout_web_kobe.json \
  --app-name local_checkout \
  --page-id local_checkout \
  --steps 6

web-kobe web-kobe-pddl-smoke \
  --graph outputs/local_checkout_web_kobe.json \
  --output outputs/local_checkout_pddl_smoke \
  --goal-node <goal_node_id>
```

If SafeSym is checked out locally, validate that SafeSym can parse, inject, and
optionally solve the generated PDDL:

```bash
web-kobe web-kobe-safesym-smoke \
  --task-dir outputs/local_checkout_pddl_smoke \
  --safesym-root C:\Users\moon\Desktop\Projects\SafeSym \
  --rules C:\Users\moon\Desktop\Projects\SafeSym\configs\constraint_rules.json \
  --fast-downward C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py
```

The smoke command writes:

```text
domain.pddl
problem.pddl
smoke_report.json
```

This validates planning readiness only. If the explored graph does not contain a
safety-relevant action such as `order_place_confirm`, SafeSym safety injection
not triggering is expected.

## Useful Commands

```bash
web-kobe web-kobe-explore --url <url> --output outputs/web_kobe_graph.json
web-kobe web-kobe-pddl-from-graph --graph outputs/web_kobe_graph.json --goal-node <node>
web-kobe web-kobe-pddl-smoke --graph outputs/web_kobe_graph.json --goal-node <node>
web-kobe web-kobe-safesym-smoke --task-dir outputs/web_kobe_pddl_smoke --safesym-root <path> --rules <rules.json>
```

Debug-only helpers are still available:

```bash
web-kobe web-kobe-graph --output outputs/debug_web_kobe_graph.json
web-kobe web-kobe-pddl --output outputs/debug_web_kobe_pddl --goal-node start
```

## Tests

Run the retained mainline bridge suite:

```bash
pytest tests/safesym_bridge -q
```

Some browser tests launch Playwright Chromium and may require local execution
permissions outside restricted sandboxes.
