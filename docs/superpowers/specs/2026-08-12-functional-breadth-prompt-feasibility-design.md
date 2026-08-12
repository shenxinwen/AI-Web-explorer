# Functional-Breadth Prompt Feasibility Design

## Objective

Validate whether a prompt-only change can keep generic website exploration from spending most of a bounded run inside one local function. The experiment must preserve open-ended exploration and must not introduce site-specific rules, parameterized actions, cross-node memory, or scheduler changes.

## Observed failure

The current affordance prompt prioritizes actions that are visibly executable now. On the shopping fixture, local filter controls are prominent and easy to execute, so `apply_filters` is returned first. Each filter variation creates a new raw state whose local tried-action set is empty. The selector therefore chooses `apply_filters` again, and the forward explorer builds a nominally deep but functionally narrow chain.

## Considered approaches

1. **Static prompt-only breadth guidance (selected).** Ask the VLM to cover distinct functional families and rank surface/workflow transitions above major functions, and major functions above local refinements. This is the smallest experiment and isolates whether the VLM can supply better candidates.
2. **Inject cross-node exploration history.** Give candidate generation recent action-family history. This should be stronger but changes the request/data flow and does not isolate prompt classification quality.
3. **Scheduler-level action-family novelty.** Track and penalize recently explored families. This is the likely durable mechanism, but it is outside the feasibility experiment.

## Prompt behavior

The prompt will:

- state that the objective is breadth of functional coverage, not interaction count;
- request at most one representative action per functional family;
- classify each action using the already-supported `relevance_hint` field;
- rank likely new surface, object, dialog, page, or workflow-stage actions as `core`;
- rank major same-surface functions as `supporting`;
- rank local presentation/refinement operations as `low_value` when broader actions exist;
- require one concrete visible target and reject ambiguous umbrella actions;
- include the explorer goal in the prompt payload;
- remain domain-neutral, using functional scope rather than hard-coded names such as filters, products, or carts.

No response-model or graph-schema field will be added. The existing parser already consumes `relevance_hint` and `confidence`, and the existing selector already ranks them.

## Data flow

```text
current screenshot + exploration goal
  -> functional-breadth affordance prompt
  -> diverse visible action candidates with relevance_hint
  -> existing affordance parser
  -> existing relevance-based selector
  -> existing Stagehand execution and graph collection
```

## Verification

Automated tests will first prove that the generated prompt contains the exploration goal, breadth constraint, one-action-per-family rule, concrete-target rule, and the `relevance_hint` output field. Existing affordance parsing and selection tests must continue to pass.

A bounded live experiment on `https://practiceautomatedtesting.com/shopping` will then compare against the baseline:

- baseline: the first six productive transitions are dominated by the same local function;
- feasibility success: early candidates span multiple functional families, and the executed trace reaches at least one non-refinement function before repeating the same refinement family;
- failure: the run still repeatedly selects one local family despite the prompt, indicating that history-aware selection is required.

The experiment evaluates exploration breadth only. Replay success, parameterized action determinism, state merging, and SafeSym solvability remain separately reported and are not acceptance criteria for this prompt-only change.
