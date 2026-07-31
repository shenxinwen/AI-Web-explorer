# Current Project Overview

This is the high-level project handoff. It records the current direction,
phase, main problems, and next priorities. Detailed module structure lives in
`docs/project-structure.md`; decision rationale lives in
`docs/project-decisions.zh-CN.md`. The Chinese version,
`docs/current-project-overview.zh-CN.md`, is for human review.

## One-line Goal

This project is not a general-purpose web-agent product. It is a SafeSym-facing
web exploration and planning-modeling system:

```text
real website interaction
  -> observe page and business-state changes before and after actions
  -> build WebKobeGraph
  -> abstract planner-facing states and actions
  -> project into PDDL
  -> let SafeSym parse, inject safety checks, and validate planning artifacts
```

The core problem is not making a model finish one website task. The core problem
is:

```text
turn real web interaction into a stable, reviewable, plannable state graph that
SafeSym can consume.
```

Stagehand, Playwright, VLM/LLM providers, and embeddings are tools or evidence
sources. Web-KOBE must own graph structure, state memory, PDDL semantics, and
exploration control.

## Current Phase

The project has completed the early end-to-end validation chain:

```text
real browser execution -> graph -> PDDL -> SafeSym smoke
```

It is now moving from the task-guided checkout baseline toward bounded
exploration V1. The current target is a minimal usable exploration loop:

```text
observe current state
  -> generate immediately executable business action candidates
  -> choose one action using graph memory / embedding memory / repetition penalty
  -> execute the action
  -> observe before/after business changes
  -> update node, edge, planning_state, and planning_transition
  -> generate or update PDDL/SafeSym artifacts
  -> continue or stop based on budget, repetition, frontier, or business coverage
```

Current objective status:

```text
real browser chain: established
graph/PDDL/SafeSym engineering chain: established
VLM visual delta: connected
business affordance generation: initial version exists
embedding memory: connected for similar-state lookup and repetition guidance
free exploration strategy: not stable yet
profile fact verifier: not real yet
PDDL semantic quality: consumable, but not stable or readable enough
```

Detailed pipeline and module ownership are recorded in
`docs/project-structure.md`.

## Current Architectural Judgments

### 1. WebKobeGraph is the active graph model

The old `WebObservedGraph` exploration stack has been removed from the active
source tree. The active exploration, PDDL, and SafeSym chain should use:

```text
WebKobeGraph
WebKobeNode
WebKobeEdge
PlanningState
PlanningTransition
BusinessAffordance
BusinessTransition
```

Historical `WebObservedGraph` designs remain only in old spec/plan documents.

### 2. Profile facts should have lower influence

Profile facts are not the complete set of possible web states. Their new
position is:

```text
candidate PDDL predicate vocabulary + preferred observation targets +
cross-site semantic alignment anchors
```

The graph should be able to record both profile facts and generated facts. PDDL
should still conservatively consume profile facts by default. Generated fact
recording, promotion, and projection remain open design work.

### 3. Stagehand is the operation layer, not state truth

Stagehand can observe, propose candidates, execute actions, and provide traces.
It should not directly decide:

- node identity;
- planning facts;
- PDDL predicates/effects;
- safety triggers;
- exploration completion.

State truth should come from Web-KOBE before/after observations, VLM/structured
evidence, graph memory, and a future verifier.

### 4. PDDL projection should stay deterministic

The PDDL projector should consume graph semantics. It should not call LLM/VLM
directly and should not freely invent predicates.

Current PDDL inputs are mainly:

```text
node location
node.planning_state.active_facts
edge.action.canonical_action_name
edge.planning_transition.pre_facts
edge.planning_transition.added_facts
edge.planning_transition.removed_facts
```

Naming work is deferred. The intended boundary is that LLM/VLM may help produce
semantic labels during exploration, while the projector only normalizes and
projects stored graph semantics.

## Main Problems

### P0: profile facts still carry too much responsibility

Profile facts currently influence VLM prompts, fact classification, lightweight
structured verification, planning_state propagation, and PDDL predicates. They
have not yet been fully downgraded into planner-facing references.

The concrete issue: `planning_transition` is still filtered through profile
facts, making generated facts hard to carry into node state.

### P0: PDDL semantic quality is still unstable

SafeSym can structurally consume current artifacts, but PDDL quality is not
stable enough:

- location predicates may still degrade into names such as `at_shopping_002`;
- action preconditions depend on correct source-node localization;
- incomplete profile facts make PDDL degrade into a location path;
- generated facts are not projected by default, so real business states may be
  lost.

### P1: exploration does not yet have a real frontier

The system has business affordances and embedding memory, but not mature:

- candidate action ranking;
- tried-action memory;
- duplicate/no-op penalty;
- backtracking;
- coverage stop conditions.

It is closer to bounded single-path exploration than mature free exploration.

### P1: WebKobeExplorer has centralization risk

`WebKobeExplorer` coordinates observation, action choice, VLM, embedding,
source matching, edge construction, planning transition, and backtracking. It is
the current mainline core, but new exploration policy should not keep growing
inside `explore_one_step`.

### P2: graph still mixes business state and low-level UI structure

`interactable_elements`, selectors, and low-level action traces still exist in
the graph structure. Keep them short term for compatibility and debugging, but
the business graph should gradually center on:

```text
business_affordances + business_transition + planning_transition
```

### P2: verifier is missing

Facts currently come mostly from VLM candidates or lightweight structured rules.
A future verifier must decide which facts become planner-facing truth.

Short term, preserve provenance and evidence.

## Next Priorities

1. Fix the profile-fact hard-whitelist issue so the graph can record generated
   facts while PDDL stays conservative by default.
2. Run an experiment to verify whether embedding source matching affects edge
   sources correctly.
3. Inspect graph and PDDL quality, especially source/target,
   precondition/effect, and node labels.
4. Revisit PDDL naming strategy after graph semantics are stable.
5. Once the graph layer stabilizes, refactor or detach `interactable_elements`
   and other low-level UI fields.
6. Gradually split `WebKobeExplorer` to avoid further centralization.

## Experiment Management

Keep only the latest valid output for each site:

```text
outputs/experiments/<site_name>/latest/
```

Each experiment report should record:

- command and models;
- prompt mode;
- execution mode;
- stop reason;
- graph node and edge counts;
- node merge / revisit behavior;
- embedding records and memory hits;
- final planning facts;
- generated facts;
- PDDL readiness;
- SafeSym consumability;
- anomalies and failed/no-op edges;
- screenshot-backed human-verifiable state changes;
- objective conclusion for structural chain, semantic chain, and exploration
  ability.

## Related Documents

```text
docs/project-structure.md
  Current pipeline, module boundaries, and major functions.

docs/project-structure.zh-CN.md
  Chinese version of the project structure document.

docs/project-decisions.zh-CN.md
  Project decision record. Update it after meaningful architecture, pipeline,
  data-structure, or mainline cleanup changes.

docs/safesym-bridge.md
  SafeSym bridge commands and experiment usage.

docs/current-project-overview.zh-CN.md
  Chinese version of this overview.
```
