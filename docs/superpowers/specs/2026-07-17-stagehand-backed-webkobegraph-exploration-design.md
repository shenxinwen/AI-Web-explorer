# Stagehand-Backed WebKobeGraph Exploration MVP Design

Date: 2026-07-17

## Context

The project should not compete with general web agents on browser task
completion. Existing tools such as Stagehand already provide browser operation
capabilities, including page action discovery and execution. The project's
distinct value is the SafeSym-facing model extraction layer:

```text
real web interaction trajectory
-> before/after observations
-> WebKobeGraph state transitions
-> PDDL domain/problem artifacts
-> SafeSym safety injection and planner consumption
```

The next stage should therefore treat Stagehand as a web operation backend, not
as a replacement for WebKobeGraph, PDDL projection, or SafeSym integration.

## Goal

Build a SauceDemo MVP that uses Stagehand for single-step page action discovery
and execution while this project owns state observation, transition recording,
graph construction, and PDDL/SafeSym-facing artifacts.

Target task:

```text
Start at the SauceDemo login page and reach checkout_overview after adding one
item to the cart.
```

Target path:

```text
login
-> inventory
-> inventory/cart_nonempty
-> cart
-> checkout_info
-> checkout_overview
```

The MVP does not click `Finish` / place the order.

## Non-Goals

- Do not build a competing general-purpose web agent.
- Do not use the removed legacy `explore` runtime.
- Do not let a full autonomous Stagehand `agent()` run the whole task as one
  opaque operation.
- Do not implement node deduplication, repeated-region abstraction, product-card
  parameterization, or full-site crawling in this stage.
- Do not treat Stagehand's predicted action result as a fact.
- Do not project failed, no-change, or ambiguous transitions into PDDL actions.

## Architecture

The exploration loop runs one graph edge at a time:

```text
observe before state
-> ask Stagehand to discover or execute one next task-relevant action
-> observe after state
-> compute schema_delta and typed_delta
-> append a WebKobeGraph edge with Stagehand evidence
-> repeat until checkout_overview or max_steps
```

Stagehand owns:

- action discovery from the current page;
- action grounding inside the browser;
- execution of one low-level browser interaction, such as click or fill;
- raw action/result evidence.

This project owns:

- before/after state observation;
- node creation and later node matching policy;
- edge creation;
- observed delta computation;
- transition validation;
- PDDL projection;
- SafeSym smoke integration;
- all planner-facing artifacts.

## Stagehand Integration Boundary

Preferred mode is `observe` then `act` for a single step:

```text
stagehand.observe(<task-scoped next-action instruction>)
stagehand.act(<selected observed action>)
```

The integration should record, when available:

- Stagehand instruction;
- raw observed action;
- method;
- selector;
- arguments;
- action description;
- action result;
- action history or trace;
- error details.

If `observe` is not adequate for a page, a fallback may use one scoped
natural-language `act` instruction. Even then, the loop must still observe
before and after the action and record one transition.

The Stagehand action is evidence for what was executed, not evidence for the
state transition effect. Effects come only from post-action observation.

## Data Model Additions

The existing `BrowserAction` / `WebKobeEdge` model can be extended or wrapped
with Stagehand-specific evidence. The graph edge should preserve at least:

```text
action_source = "stagehand"
stagehand_instruction
stagehand_observed_action
stagehand_act_result
stagehand_method
stagehand_selector
stagehand_arguments
execution_success
execution_error
before_observation_id
after_observation_id
schema_delta
typed_delta
```

The exact field placement can be chosen during implementation. A conservative
first option is to store Stagehand-specific fields in edge evidence or execution
trace metadata, then promote stable fields later if needed.

## PDDL Projection Policy

The projector should continue to include only verified observed transitions.

Eligible edges:

- Stagehand action execution succeeded;
- after observation exists;
- target node exists;
- transition has an observed schema delta, typed delta, or clear node/navigation
  change;
- edge status is a successful status such as verified observed change or
  succeeded with navigation.

Excluded edges:

- execution failed;
- no observed change;
- ambiguous transition;
- unexpected error;
- insufficient before/after evidence.

Excluded edges remain useful for diagnostics but must not become planner action
effects.

## SauceDemo MVP Acceptance Criteria

The stage is successful when:

1. The smoke starts at the SauceDemo login page.
2. Stagehand performs single-step actions, not an opaque full-task run.
3. The run reaches `checkout_overview` without clicking `Finish`.
4. Each step records before and after observations.
5. The resulting WebKobeGraph contains the login, inventory, cart, checkout
   info, and checkout overview states or state equivalents.
6. Each successful edge records Stagehand action evidence and observed delta or
   node/navigation change.
7. WebKobeGraph-to-PDDL projection produces non-empty domain/problem artifacts.
8. The smoke report explains which edges were projected and which were
   excluded.

## Testing Strategy

Use fake Stagehand providers for default automated tests so CI does not require
network access, browser credentials, or paid model calls.

Suggested tests:

- adapter converts a fake Stagehand observed action into internal action
  evidence;
- one-step exploration records before/after observations around a fake
  Stagehand act result;
- failed or no-change Stagehand actions are retained in the graph but excluded
  from PDDL;
- the SauceDemo smoke command wires Stagehand-backed exploration without using
  the legacy explore runtime;
- PDDL smoke still rejects undeclared predicates and unreachable goals.

Real SauceDemo + Stagehand browser tests should remain opt-in, similar to the
existing real browser smoke gates.

## Deferred Work

- Node deduplication and conservative merge policy.
- Region detection and repeated product-card representative sampling.
- Abstracting product-specific edges into parameterized actions.
- Stagehand `agent()` as an external baseline, not the main graph-construction
  loop.
- SafeSym safety-rule triggers for the final `Finish` / order placement action.
- Comparing Stagehand-backed exploration against the current DOM-only baseline.

## Rationale

This design lets the project reuse a capable web operation layer while keeping
the project focused on its differentiator: converting observed web behavior into
auditable graph transitions and planner-facing artifacts.

The central invariant remains:

```text
Stagehand may decide and execute the next browser action.
Only this project decides what state transition was observed and what enters
WebKobeGraph, PDDL, and SafeSym.
```
