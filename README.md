# AI Web Explorer

AI Web Explorer observes real webpages, discovers semantic business actions, executes them through Stagehand, records the results in a `WebKobeGraph`, and projects the graph to Minimal Semantic PDDL for SafeSym.

```text
VLM screenshot observation
  -> semantic-location candidate pool + requires
  -> dependency-aware local selection
  -> pre-execution VLM risk annotation (shadow mode)
  -> Stagehand execution
  -> VLM outcome observation
  -> WebKobeGraph update
  -> frontier replay when context recovery is needed
  -> Minimal Semantic PDDL
  -> SafeSym
```

Replay only restores a previously explored context by resetting the start URL and replaying a saved semantic-action path. It never discovers candidates or mutates exploration state; normal exploration resumes after replay succeeds.

Optional risk detection assesses every selected normal-exploration and replay action from the current screenshot, its high-level label, and a versioned taxonomy. It records a binary risk decision without blocking execution.

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
  --openai-risk-detection \
  --risk-detection-model gpt-4o \
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

## Site-scoped adapters

The generic exploration path remains the default. Controlled demo sites may opt
into narrowly scoped execution support without changing candidate discovery or
evidence verification. For the RealWorld demo, `--site-adapter realworld`
supplies unique fictional registration values and adds a short post-action wait
for its asynchronous navigation. It also marks the visibly authenticated home
state separately so it is not merged with the anonymous home state. Other sites,
including SauceDemo, are unchanged unless this flag is explicitly provided.

Frontier replay records every attempt in `replay_attempt_history`, including the
target node, replay path, failed edge, completed step count, and reason. A
successful action sequence is accepted only after a fresh observation matches
stable target-state identity fields.

Replay is part of normal exploration, not a separate experiment. Continue a run
by pointing `--resume-graph` and `--output` to the same canonical graph while
keeping its trace and screenshots in the same `run_xx/` directory. These
artifacts then grow as one exploration run. Replay keeps separate diagnostic
counters but is not counted as a discovered functional action.
