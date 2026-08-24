# Project Structure

The active runtime has two packages:

- `grounded_web`: observation, semantic-location candidate pools, action execution, outcome observation, graph updates, resume, and frontier replay.
- `safesym_bridge`: Playwright/Stagehand orchestration, graph loading, semantic planning projection, Minimal Semantic PDDL, SafeSym smoke, and CLI entry points.

The public flow is:

```text
cli/browser_runner -> controller -> explorer -> WebKobeGraph
                                     ^
                                     `-- resume/frontier_replay

WebKobeGraph -> semantic_planning -> minimal_semantic_pddl -> SafeSym
```

The public CLI consists of `web-kobe-stagehand-explore`, `web-kobe-semantic-pddl`, and `web-kobe-safesym-smoke`. Legacy Trace/Location/Surface PDDL projectors and fixed/debug graph commands are not part of the current structure.

See [the Chinese structure document](project-structure.zh-CN.md) for component responsibilities and data ownership.
