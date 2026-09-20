# C3 External Context-Challenge Error Analysis v1

> Analysis date: 2026-09-20
>
> Scope: the frozen 100-sample external formal set; no labels or predictions were changed.

## Binary error transitions

Each sample was classified as correct or incorrect under Text only (`action_taxonomy`) and Context conditioned (`full`).

| Transition | Samples |
|---|---:|
| Correct under both conditions | 48 |
| Corrected by visual context | 16 |
| Error introduced by visual context | 14 |
| Wrong under both conditions | 22 |

Among the 16 corrections, visual context recovered 14 risk-positive actions and corrected two false alarms. Among the 14 introduced errors, it missed six positives and introduced eight false alarms. This yields the observed net change of eight fewer false negatives and six more false positives.

The corrections are consistent with visual disambiguation: generic labels such as `connect`, `next`, `accept`, `guardar`, `siguiente`, and `agree` became interpretable when the surrounding form, account flow, or data-entry context was visible. The introduced false positives show the complementary failure mode: the assessor sometimes treated opening or preparing a consequential workflow as if the click itself completed the consequence. Examples include opening upload, invite, share, registration, cart, and package-building flows.

## Risk-type transitions

Type correctness is evaluated on the 65 human-confirmed risk-positive samples using the frozen set-valued acceptable types.

| Transition | Samples |
|---|---:|
| Correct under both conditions | 16 |
| Corrected by visual context | 25 |
| Error introduced by visual context | 2 |
| Wrong under both conditions | 22 |

This asymmetry explains the 35.4-point gain in acceptable-type accuracy. Visual context usually helped determine what consequence the action concerned even when the binary decision remained difficult. The remaining type errors largely reflect either a missed risk decision or confusion between adjacent consequences in compound workflows, rather than absence of a plausible explanation.

## Context-pair failures

Only eight of the 30 candidate pairs were binary-discordant under the independently confirmed VERA labels. Context conditioned handled two pairs completely correctly (`PAIR018` and `PAIR024`); Text only handled none. The other six pair failures arose from one of two patterns:

- both screenshots were assigned the same conservative risk judgment despite different immediate effects; or
- one visually ambiguous action was treated as safe even though the annotated context made its consequence risk-bearing.

Because the realized denominator is eight pairs, this analysis supports a qualitative context-sensitivity claim but not a precise population estimate.

## Interpretation

The external result does not show uniformly better binary classification. It shows a trade-off: visual context makes the assessor more sensitive and substantially improves consequence typing, while also increasing anticipatory false positives at workflow-entry actions. This suggests that future refinement should distinguish **immediate effect** from **downstream possible effect** in the judgment schema or prompt. Such a refinement was not applied post hoc to the frozen experiment.

The recomputable sample-level transitions and error rows are stored under `error_analysis` in `outputs/paper/formal/E002_c3_external_v1/formal_metrics.json`.
