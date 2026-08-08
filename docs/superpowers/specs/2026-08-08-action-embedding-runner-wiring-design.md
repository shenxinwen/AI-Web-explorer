# Action Embedding Runner Wiring

## Goal

Make the real `web-kobe-stagehand-explore` entry point enable the action-semantic
deduplication already supported by `WebKobeExplorer`.

## Design

The runner already creates one compatible embedding provider from the
`EMBEDDING_*` environment variables when `--state-embeddings` is enabled. Pass
that same provider to both `state_embedding_provider` and
`action_embedding_provider` when constructing `WebKobeExplorer`.

This reuses the configured embedding service without adding environment
variables, persistent graph fields, or a second client. State matching and
action matching remain logically separate because the explorer still receives
them through two explicitly named parameters.

When `--state-embeddings` is disabled, both parameters remain `None`. Existing
exact-name action deduplication therefore remains the safe fallback.

## Error Handling

Provider creation keeps its existing behavior. Runtime action embedding errors
continue to fall back to exact-name matching through
`semantically_matches_action`; they must not stop exploration.

## Test

Add a runner-level regression test that captures the constructed explorer and
asserts that the resolved provider is passed to both named parameters. Run the
test before implementation to confirm it fails because the action parameter is
missing, then make the single wiring change and rerun the focused exploration
tests.

## Non-goals

- No new embedding configuration.
- No threshold changes.
- No PDDL changes.
- No retry policy changes for the visual candidate provider.
