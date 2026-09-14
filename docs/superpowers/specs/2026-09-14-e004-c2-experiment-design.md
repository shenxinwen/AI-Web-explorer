# E004 C2 Experiment Design

## Objective

Evaluate whether structured functional exploration discovers a larger fraction
of a small website's core functionality than ungated random exploration, and
whether persistent-frontier replay further improves coverage by returning to
locations whose functional candidates remain unfinished.

C2 evaluates exploration and evidence production. It inherits C1's definition
of interaction-supported knowledge but does not repeat C1's comparison of
knowledge-admission policies.

## Claim

Under a fixed candidate-attempt budget, structured functional exploration uses
high-level functional candidates, dependency-aware execution, and candidate
state memory to obtain greater interaction-supported core-function coverage
than ungated random exploration. Persistent-frontier replay can further improve
coverage by recovering functional candidates stranded by a linear trajectory,
with replay interactions reported as a separate cost.

The experiment does not claim that replay, frontier search, high-level actions,
or state graphs are novel by themselves. It evaluates their role in producing
evidence-supported functional knowledge in the AI Web Explorer pipeline.

## Sites

- SauceDemo
- Practice Shopping

Every run starts from the frozen entry URL in a clean browser context. Model,
prompt, viewport, candidate limit, executor, outcome observer, retry limits,
and evidence capture settings remain fixed across conditions.

## Conditions

### Ungated Random

- Use the same frozen high-level functional candidates as the other conditions.
- Randomly select among unfinished candidates at the current semantic location.
- Do not enforce candidate dependency eligibility before selection.
- Preserve failed, no-change, uncertain, and evidence-incomplete attempts.
- Do not recover a previous location after leaving it.
- Use and record a frozen random seed for each run.

This is a sanity baseline representing random selection over proposed actions,
not a reproduction of a particular external system and not random pixel-level
clicking.

### Linear Functional Exploration

- Use high-level functional candidates with frozen execution instances and
  expected outcomes.
- Enforce declared action dependencies.
- Use the existing deterministic candidate ordering and candidate lifecycle
  memory.
- Continue along the current trajectory.
- Do not replay a previous location when the current location is exhausted.

### Full Functional Frontier Exploration

- Use exactly the same candidate generation, dependency handling, ordering,
  retry policy, and evidence capture as Linear.
- Persist unfinished candidates by semantic location.
- When the current location is exhausted, select an eligible unfinished
  frontier, reset to the entry, replay a known path, and continue normal
  exploration at the restored location.

Linear versus Full is the primary controlled ablation because frontier recovery
is their only intended difference.

## Budgets

Pilot runs use at most 10 normal candidate action attempts. Formal runs use at
most 25 normal candidate action attempts. A run may stop early when no eligible
candidate or recoverable frontier remains.

Replay path actions do not consume the candidate-attempt budget because they
restore context rather than test a new functional hypothesis. They are bounded
and reported separately:

- at most 2 replay attempts per frontier;
- at most 4 replay attempts per run;
- every replay GUI action and completed replay-path step is counted;
- replay failure, mismatch, and no-progress recovery remain in the record.

Total GUI actions equal normal candidate executions plus replay path actions.
This total is a cost diagnostic and the denominator of the cost-aware secondary
efficiency metric.

## Supported Function Definition

Within one run, a function is identified by:

`site + semantic_location + canonical_action_id`

It is interaction-supported when at least one valid attempt has complete
required execution evidence and human review concludes that the before/after
evidence supports the candidate's core functional outcome. Multiple attempts
of the same function count once.

Core coverage uses the site-specific core-function lists frozen before E004.
Functions discovered outside those lists are reported separately and never
added to the denominator after seeing results.

## Primary Metrics

### Supported Core Coverage

`number of interaction-supported core functions / frozen core-function total`

Report both the fraction and raw count, for example `8/10 (80%)`. This is the
primary outcome because the two sites have small, enumerable core-function
sets.

### Supported Functions

The number of unique interaction-supported functions in a run, including both
matched core functions and supported functions outside the frozen core list.
Report the two parts separately as well as their total.

### Supported per Attempt

`unique interaction-supported functions / normal candidate action attempts`

This measures evidence-producing efficiency under the shared candidate budget.

## Secondary and Diagnostic Metrics

- supported-knowledge growth over normal candidate attempts;
- executor success rate, reported only as a diagnostic and never as a proxy for
  supported knowledge;
- dependency-violation attempts in Ungated Random;
- failed, no-change, uncertain, and evidence-incomplete attempts;
- repeated attempts of already completed functions;
- stop reason and actual candidate attempts used;
- total GUI actions and `supported functions / total GUI actions`;
- replay attempts, successes, failures, mismatches, and completed path steps;
- unfinished candidates recovered and attempted after replay;
- replay-mediated supported functions: functions first supported by a normal
  candidate attempt following successful recovery of their frontier.

Deepest workflow stage is qualitative case evidence, not a main metric.

## Experiment Size

Pilot:

- 2 sites x 3 conditions x 1 run;
- 6 runs total;
- at most 10 normal candidate attempts per run;
- pilot results validate instrumentation and metric computability and do not
  enter the paper's formal result tables.

Formal experiment, only after pilot approval:

- 2 sites x 3 conditions x 3 runs;
- 18 runs total;
- at most 25 normal candidate attempts per run.

## Required Comparisons

- Ungated Random versus Linear evaluates the combined system-level effect of
  dependency-aware functional exploration and candidate lifecycle memory. It
  must not be used to attribute gains to either component individually.
- Linear versus Full evaluates the marginal effect of persistent-frontier
  recovery on supported coverage and evidence production.
- Replay cost is always reported beside replay-mediated knowledge gains.

## Pilot Readiness Gates

Before starting the six pilot runs:

1. Each condition must be selectable explicitly and echoed into run metadata.
2. Random selection and its seed must be persisted.
3. Every normal attempt must retain its frozen candidate, execution instance,
   expected outcome, before/after evidence, executor status, and outcome trace.
4. Replay history must link a successful recovery to the first subsequent
   normal candidate attempt at the recovered frontier.
5. Candidate attempts and replay GUI actions must have separate counters.
6. All three primary metrics must be computable from a fixture or historical
   artifact before any live pilot run.
7. No C1 formal output may be modified, overwritten, or included as E004 data.

## Interpretation Boundaries

If Full improves supported coverage per candidate attempt but not per total GUI
action, the conclusion is that recovery improves coverage at additional replay
cost, not that it improves total interaction efficiency. If Ungated Random
performs worse, the result supports the structured exploration package as a
whole; it does not independently validate dependency-recognition accuracy.

