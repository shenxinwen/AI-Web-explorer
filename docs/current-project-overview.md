# Current Project Overview

The project turns visually observed web interaction into a planner-facing semantic model without site-specific fixed workflows.

```text
VLM observation -> location-scoped candidates + dependencies
-> local selection -> Stagehand execution -> VLM outcome
-> WebKobeGraph -> optional frontier replay -> Minimal Semantic PDDL -> SafeSym
```

Normal exploration owns discovery and graph mutation. Replay only resets the start URL and executes a saved semantic-action path to restore a frontier with unfinished candidates. Successful replay hands control back to the Explorer.

Implemented capabilities include bounded candidate attempts, dependency-aware selection, action-outcome observation, resumable checkpoints, bounded frontier replay, semantic planning projection, and SafeSym smoke validation.

Remaining limitations include VLM semantic-location stability, missing observed dependencies, minimal replay arrival evidence, and limited cross-site end-to-end planning evidence.

See [the Chinese overview](current-project-overview.zh-CN.md) for the maintained detailed description.
