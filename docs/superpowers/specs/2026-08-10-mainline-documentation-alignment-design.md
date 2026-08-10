# Mainline Documentation Alignment Design

## Goal

Make the five active project documents describe one consistent mainline: VLM proposes possible business actions, local memory selects one, Stagehand attempts it, after-action observation verifies what happened, the raw graph preserves stable GUI observations, deterministic planning abstraction produces a planning graph, and Phase A projects only cross-planning-state transitions into `domain.pddl`.

This change updates documentation only. It does not change code, run a real browser experiment, add graph fields, or redesign Visual Delta classification.

## Active Documents

- `docs/current-project-overview.zh-CN.md`
- `docs/current-project-overview.md`
- `docs/project-structure.zh-CN.md`
- `docs/project-structure.md`
- `docs/project-decisions.zh-CN.md`

Historical files under `docs/superpowers/specs/` and `docs/superpowers/plans/` remain historical records. They are not rewritten to look current.

## Documentation Roles

### Current project overview

Lead with the end-to-end mainline and clearly separate:

- a VLM candidate action from an execution-verified transition;
- raw observation nodes from planning states;
- code that is implemented from behavior that still needs a real experiment;
- current limitations from future work.

Remove or rewrite stale claims such as "business states cannot yet be merged" when the implementation exists but has not yet been validated on a real run. Describe the current explorer as forward-only; historical frontier recovery is not active.

Visual Delta remains an observer. Its current bounded categories are implementation facts, but their quality and final taxonomy remain an explicit review item.

### Project structure

Map each mainline responsibility to the current modules and artifacts:

```text
VLM candidates
-> local selection
-> Stagehand attempt
-> after-action observation and local verifier
-> raw graph plus evidence sidecar
-> per-step checkpoint
-> planning abstraction
-> planning graph and audit report
-> Phase A domain.pddl
```

Document that candidate affordances are not automatically verified capabilities. A successful observed edge is the evidence for a verified transition. Planning groups may aggregate candidate capabilities, but provenance identifies where each candidate was observed.

### Project decisions

Add one dated decision recording the agreed mainline and its boundaries. Preserve older decisions, but mark directly conflicting statements as superseded instead of silently deleting history.

## Agreed Boundaries

- VLM proposes actions that appear executable; it does not own global planning state.
- Local memory selects one candidate and performs local semantic deduplication.
- Stagehand only attempts the selected action. After-action evidence determines the recorded outcome.
- Stable visible changes become raw observations; failure and no observed change remain auditable self-loops.
- Raw graph records observed history. Detailed screenshots and model traces belong in sidecars.
- Embeddings find candidates and reduce repetition; they do not decide state identity.
- Profile facts are strong but incomplete local semantic anchors. VLM does not receive them.
- Planning abstraction only merges with strong evidence and preserves unknown changes separately.
- Presentation actions remain graph capabilities/self-loops but do not enter Phase A PDDL.
- Phase A emits only state-level `domain.pddl`; it does not emit `problem.pddl`, concrete business objects, supporting facts, or Visual Delta candidate facts.
- Exploration is currently forward-only. Maximum steps and current-route exhaustion bound a real run; replay and historical frontier recovery are out of scope.
- Checkpoint prevents completed work from being lost. It is not resume or replay.
- The current Visual Delta taxonomy is a pending review topic, not a settled ontology.

## Cleanup Rules

- Delete duplicated explanations when one canonical section is enough.
- Replace active references to removed modules or old canonical-graph terminology.
- Keep historical decisions only when their historical status is explicit.
- Keep Chinese and English overview/structure semantically aligned.
- Do not add another active project-entry document.

## Validation

- Search active documents for removed modules and superseded terminology.
- Compare Chinese and English headings and mainline claims.
- Confirm every active module path mentioned in structure documents exists.
- Confirm overview statements distinguish implemented behavior from unvalidated experiment results.
- Run `git diff --check` and inspect the final documentation diff.
