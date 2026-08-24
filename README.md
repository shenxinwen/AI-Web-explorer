# AI Web Explorer

AI Web Explorer observes real webpages, discovers semantic business actions, executes them through Stagehand, records the results in a `WebKobeGraph`, and projects the graph to Minimal Semantic PDDL for SafeSym.

```text
VLM screenshot observation
  -> semantic-location candidate pool + requires
  -> dependency-aware local selection
  -> Stagehand execution
  -> VLM outcome observation
  -> WebKobeGraph update
  -> frontier replay when context recovery is needed
  -> Minimal Semantic PDDL
  -> SafeSym
```

Replay only restores a previously explored context by resetting the start URL and replaying a saved semantic-action path. It never discovers candidates or mutates exploration state; normal exploration resumes after replay succeeds.

## CLI

```bash
python -m ai_web_explorer.safesym_bridge.cli --help
```

The three public commands are:

```text
web-kobe-stagehand-explore
web-kobe-semantic-pddl
web-kobe-safesym-smoke
```

Example:

```bash
web-kobe web-kobe-stagehand-explore \
  --url https://www.saucedemo.com/ \
  --app-name saucedemo \
  --goal "explore the shopping and checkout flow" \
  --output outputs/saucedemo/web_kobe_graph.json

web-kobe web-kobe-semantic-pddl \
  --graph outputs/saucedemo/web_kobe_graph.json \
  --output outputs/saucedemo/pddl \
  --goal-location checkout_complete

web-kobe web-kobe-safesym-smoke \
  --task-dir outputs/saucedemo/pddl \
  --safesym-root <path-to-SafeSym>
```

## Documentation

- [Current overview](docs/current-project-overview.zh-CN.md)
- [Project structure](docs/project-structure.zh-CN.md)
- [SafeSym bridge](docs/safesym-bridge.md)
- [Project decisions](docs/project-decisions.zh-CN.md)

## Tests

```bash
pytest tests/safesym_bridge -q
```

Browser integration tests that launch Playwright Chromium may require local process-launch permission.
