# Project Structure

This repository is now centered on the SafeSym-oriented Web-KOBE mainline. The
old upstream `explore` runtime has been removed from the active package.

```text
src/ai_web_explorer/
  Package root for the Web-KOBE/SafeSym implementation.

src/ai_web_explorer/grounded_web/
  Active generic exploration mainline: DOM observation, grounded browser action
  execution, state facts, typed deltas, WebKobeGraph construction, and
  exploration control.

src/ai_web_explorer/safesym_bridge/
  Planner-facing bridge: WebKobeGraph-to-PDDL projection, planning-readiness
  smoke reports, Web-KOBE CLI, and app-specific SauceDemo regression helpers.

tests/safesym_bridge/
  Retained tests for the active Web-KOBE/PDDL mainline plus SauceDemo
  app-specific regression helpers.

tests/fixtures/
  Stable local browser fixtures used for deterministic Web-KOBE exploration
  smoke tests.

docs/
  Human-facing architecture and usage documentation.

docs/superpowers/
  Development specs and implementation plans created during guided work.

examples/
  Historical sample artifacts.

outputs/
  Local generated outputs. This directory is ignored by git.

data/
  Local exploration data and tracked sample fixtures, when present.
```

Important entry points:

- `web-kobe` -> `ai_web_explorer.safesym_bridge.cli:main`

Current recommended command surface:

```text
web-kobe-explore
web-kobe-pddl-from-graph
web-kobe-pddl-smoke
web-kobe-safesym-smoke
web-kobe-saucedemo-stagehand-smoke
```

Debug helpers:

```text
web-kobe-graph
web-kobe-pddl
```
