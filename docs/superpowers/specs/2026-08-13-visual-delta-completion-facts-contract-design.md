# Visual Delta Completion Facts Contract Design

## Context

The 2026-08-13 Practice Shopping run showed that the VLM could recognize
`products_filtered` and `products_found`, but returned `completion_facts` as a
copy of the profile vocabulary object rather than as selected fact IDs. The
semantic parser correctly treated the object as untrusted and produced no
completion facts. Three ordinary actions then counted as no semantic progress,
and the run stopped after five formal actions.

## Goal

Make the Visual Delta prompt unambiguously require
`completion_facts: list[str]`, while retaining fail-closed parsing and explicit
audit evidence for a malformed field.

## Non-goals

- Do not fix Stagehand multi-step/tool-choice action-boundary pollution.
- Do not infer completion facts from `candidate_added_facts`.
- Do not convert object keys into completed facts.
- Do not add shopping-specific branches to the parser or PDDL compiler.
- Do not run another paid website experiment in the implementation task.

## Approaches considered

### Selected: explicit response schema plus fail-closed audit

Add a typed `output_schema` to the prompt and state that profile dictionaries
are reference vocabularies, not response templates. `completion_facts` must be
a list containing only directly observed selected IDs, or `[]`. If a provider
still returns an object, keep the semantic location and role when otherwise
valid, discard the malformed completion facts, and record
`completion_facts_must_be_list_of_fact_ids` in the trace.

This is the smallest change that addresses the observed failure without
weakening planner-facing semantics.

### Rejected: accept object keys as completion facts

The observed response copied every vocabulary entry, including unobserved
facts. Promoting its keys would claim that sorting, filtering, searching,
pagination, and product-detail viewing all completed at once.

### Deferred: provider-native structured output

The configured OpenAI-compatible VLM and DeepSeek-backed Stagehand providers
do not share one reliable structured-output implementation. Provider-specific
schema enforcement would expand the scope and reduce portability.

## Design

`visual_delta._prompt_for_request()` will add an `output_schema` whose array
fields are shown as arrays and whose scalar fields are shown as scalars. The
instruction will explicitly distinguish:

- `semantic_profile_context.completion_facts`: allowed IDs plus evidence
  descriptions;
- response `completion_facts`: only the IDs visibly completed by this action;
- `[]`: required when no approved completion fact is directly supported.

The runtime parser remains conservative. A new contract-shape check records a
stable rejection reason when `completion_facts` is present but is not a list of
strings. It must not coerce the value, promote candidate facts, or reject an
otherwise valid location/role observation.

## Testing

Add focused tests proving that:

1. the prompt contains the typed output schema and the reference-vocabulary
   warning;
2. a valid list still produces approved completion facts;
3. the exact object-shaped response seen in the real run produces no
   completion facts and records the contract rejection;
4. object keys never enter `PlanningDelta`, `SemanticPlanningGraph`, or PDDL;
5. the existing location-scoped feasibility pipeline and full non-browser test
   suite remain green.

## Acceptance criteria

- `completion_facts` is unambiguously specified as `list[str]` in the prompt.
- Malformed object output is fail-closed and auditable.
- Valid approved lists continue through semantic projection.
- No website/action name branch is added outside the experiment profile.
- No unrelated Stagehand, replay, controller, or PDDL refactor is included.
