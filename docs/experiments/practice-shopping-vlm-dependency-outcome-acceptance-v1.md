# Practice Shopping VLM Dependency and Outcome Acceptance v1

Date: 2026-08-18

This report records the offline prompt/model acceptance evidence used for the
active location-scoped candidate and action-outcome path. It does not claim a
new live browser run.

## Evidence summary

| Area | Result | Interpretation |
| --- | --- | --- |
| Candidate prompt v1 | 9/9 structurally valid | Semantic NO-GO: field-chain dependencies and covered-background actions remained. |
| Candidate prompt v2 with three generic few-shots | 9/9 structurally valid | Shopping actions were independent, checkout dependency grouping was stable, and confirmation returned only `download_invoice_pdf`. |
| Action outcome, `gpt-4o-mini`, initial prompt | Filtering `location_change=false`: 0/3 | The initial prompt was insufficient for this transition. |
| Action outcome, `gpt-4o-mini`, strengthened prompt | Filtering `location_change=false`: 1/3; other five cases 15/15 | The strengthened boundary improved most transitions but did not fully resolve filtering. |
| Action outcome, `gpt-4o`, strengthened prompt | Filtering-only control: 3/3 | The comparison supports `gpt-4o` for this known weak transition. |

The accepted active configuration is therefore `gpt-4o-mini` for candidate
observation and `gpt-4o` for action-outcome observation. The `gpt-4o`
comparison covers only the filtering transition, not all transition types, so
it is not a complete model benchmark.

## Scope and boundaries

The candidate response remains the strict four-field `actions` contract with
`action_id`, `description`, `target`, and `requires`. The action-outcome
response remains the strict three-field contract with `outcome`,
`location_change`, and `evidence`. The new prompt examples are domain-neutral;
they do not provide a site profile, action contracts, candidate history, facts,
or a workflow answer.

No Stagehand call, browser execution, PDDL generation, SafeSym injection, or
planner run occurred in this offline experiment. No screenshots, credentials,
or raw runtime JSON are committed. Runtime-only artifacts, when produced by a
separate approved evaluator, belong under:

`outputs/experiments/practice_automated_testing/vlm_dependency_acceptance_v1/`

## Next acceptance stage

A real Practice Shopping run is the next acceptance stage. It must separately
review candidate quality, action-outcome evidence, graph projection, Minimal
Semantic PDDL, and SafeSym behavior. This implementation does not claim that
live acceptance has passed.
