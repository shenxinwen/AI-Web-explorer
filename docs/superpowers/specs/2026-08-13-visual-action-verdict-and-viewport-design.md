# Visual Action Verdict and Viewport Design

## Goal

Fix two experiment problems without changing the location-scoped exploration or
PDDL architecture:

1. let a VLM answer the narrow question of whether an executed action caused an
   action-consistent visible change from the before/after screenshots;
2. use a larger, configurable browser viewport so the screenshot-based candidate
   scan can see the main product region on ordinary desktop pages.

## Action verdict

Add a small visual action-verdict boundary separate from semantic Visual Delta.
Its input is only the executed action description and the existing before/after
screenshots. Its response contract is one boolean JSON field:

```json
{"succeeded": true}
```

Here, `succeeded` deliberately means "a visible change consistent with the
executed action is observable". It does not mean that hidden business state is
known, and it must not directly create completion facts, business facts,
locations, or PDDL effects.

A positive verdict is additional observed-change evidence. A negative verdict
does not erase stronger deterministic evidence such as a URL/path or structured
state change. Provider errors, malformed JSON, and missing screenshots produce an
unknown verdict and preserve the existing fallback behavior; they do not abort
the experiment. Store the prompt/response/status in execution metadata so the
decision remains auditable.

The existing Visual Delta call remains responsible for semantic location,
completion-fact vocabulary selection, and planning evidence. The two contracts
must not be merged into another large response schema.

## Viewport

Create the generic Stagehand exploration page with an explicit desktop viewport,
defaulting to `1440 x 1000`. Expose positive integer CLI options
`--viewport-width` and `--viewport-height`, and pass them through
`run_stagehand_exploration()` to `browser.new_page(viewport=...)`.

This is configuration, not site logic. Do not mention shopping, products, cart,
or selectors in the viewport implementation. Do not switch screenshots to
`full_page=True`, because very tall screenshots increase VLM cost and can reduce
visual detail.

## Boundaries

- Preserve open exploration, location-scoped one-shot memory, replay, resume,
  semantic profiles, Visual Delta, and Minimal Semantic PDDL behavior.
- Do not change Stagehand tool-choice handling in this patch.
- Do not add site-specific action names or DOM selectors.
- Do not treat the boolean verdict as a business fact.
- Do not make paid API calls while implementing or testing.

## Acceptance

- The verifier sends the action description plus both screenshots and accepts
  only a literal boolean `succeeded` value.
- Positive visual verdicts can prevent a visibly changed action from being
  classified as `no_observed_change`.
- Unknown/failed verdicts leave existing state-change logic intact.
- The generic experiment opens a `1440 x 1000` page by default and supports
  custom positive dimensions through the CLI.
- Focused and complete non-browser test suites pass, with no shopping-specific
  production branches.
