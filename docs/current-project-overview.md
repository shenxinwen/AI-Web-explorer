# Current Project Overview

AI Web Explorer is an open-ended exploration system for understanding website functionality. It uses visual observation to discover business locations and actions, validates those actions through real browser interaction and outcome observation, and records the resulting experience in a resumable `WebKobeGraph`.

The project's primary value is website understanding through exploration. Minimal Semantic PDDL and SafeSym are downstream uses of that understanding and provide a strict way to test whether the learned model is explicit, reviewable, and plan-ready.

```text
explore a website
  -> discover its functions
  -> validate action outcomes
  -> build a reusable functional model
  -> project the model to PDDL
  -> inspect, constrain, and plan with SafeSym
```

## Acceptance goals

1. Explore a website instead of executing a hard-coded task script.
2. Generate valid PDDL that SafeSym can consume and solve.
3. Keep the exploration, graph, and PDDL logic reasonably general across sites.

A solvable PDDL model does not by itself prove complete website understanding. Candidate coverage, semantic-location stability, action causality, and persistent cross-location state require independent exploration evidence.

## Core ideas

- The VLM observes and proposes semantic business actions.
- Local structured memory tracks candidates, dependencies, completion, failure, and retry state.
- Stagehand executes one already-selected business action; it does not plan the whole workflow.
- Actions become verified experience only after execution and outcome observation.
- Candidate pools are scoped by `semantic location`, not raw node ID or the whole website.
- Normal exploration discovers and mutates knowledge; replay only restores a known browser context.
- `WebKobeGraph` may retain rich evidence, while Minimal Semantic PDDL projects only conservative, planner-facing semantics.

## Main concepts

A `semantic location` is a stable business context such as `login_form`, `product_catalog`, or `shopping_cart`. Each location owns a candidate pool keyed by canonical action. Candidate records track `pending`, `completed`, `failed`, or stale state, direct same-location `requires`, attempt counts, and failure evidence.

An action candidate is a hypothesis about visible functionality. Stagehand executes it using either a representative single atomic action or a required composite sequence. The VLM then observes the action outcome, visible evidence, and any location change. Only successfully executed and observed actions can enter the planner-facing model.

A `frontier` is a known semantic location with unfinished executable candidates. If the current location is exhausted, the controller can reset to the start URL and replay a saved semantic-action path to another frontier. Replay does not scan, discover, observe new outcomes, mutate the graph, or consume formal candidate attempts. It hands control back to the Explorer after context restoration.

`WebKobeGraph` is the accumulated, auditable experience model. Minimal Semantic PDDL is a conservative projection of verified locations, actions, explicit dependencies, completion facts, and validated business facts. SafeSym consumes this projection for parsing, safety injection, and optional base/safe planning.

## Active flow

```text
VLM screenshot observation
  -> semantic actions + same-location requires
  -> semantic-location candidate pool
  -> dependency-aware local selection
  -> Stagehand execution
  -> VLM outcome observation
  -> WebKobeGraph update
  -> bounded frontier replay when needed
  -> Minimal Semantic PDDL
  -> SafeSym
```

## Current validation boundary

Exploration acceptance covers autonomous candidate discovery, bounded retries, action execution, outcome observation, frontier selection, and replay-based continuation. Website-understanding acceptance covers meaningful semantic locations, representative capabilities, evidence-backed outcomes, correct candidate-pool reuse, and the absence of obvious action or location duplication. PDDL/SafeSym acceptance covers valid domain/problem output, evidence-backed preconditions and effects, no promotion of failed or speculative actions, SafeSym parsing and safety injection, and optional planner solves.

Practice Shopping and SauceDemo experiments have exercised the real exploration, semantic projection, replay, and planning chain. The latest SauceDemo resume experiment restored an unfinished cart frontier and allowed normal exploration to continue without repeating unrelated `add_to_cart` behavior.

## Current limitations

- Persistent cross-location business state such as `cart_has_items` is incomplete.
- Semantic-location naming and matching still depend heavily on VLM stability.
- Replay currently trusts successful path execution instead of proving arrival from page content.
- Candidate recall, action granularity, and dependency quality need broader cross-site evidence.
- SafeSym success proves planning compatibility, not complete or correct website understanding.

The maintained detailed description is the [Chinese project overview](current-project-overview.zh-CN.md). Component ownership is documented in [Project Structure](project-structure.zh-CN.md), and the projection workflow is documented in [SafeSym Bridge](safesym-bridge.md).
