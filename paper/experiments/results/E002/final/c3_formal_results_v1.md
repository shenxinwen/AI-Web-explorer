# E002 / C3 Formal Results v1

> Run date: 2026-09-20
>
> Status: formal matrix complete; results and final packaging frozen.

## Scope

C3 evaluates risk judgments for the high-level actions already selected during the six valid C2 Full exploration runs. It does not measure discovery of actions that the explorer never proposed, and all judgments remain shadow-mode records that do not affect execution.

The primary dataset contains 106 run-locally deduplicated ordinary-exploration actions. Gold contains 32 risk-positive actions: 14 `financial_transaction` and 18 `sensitive_data`. Replay is excluded from classification accuracy.

## Formal execution audit

- Conditions: `action_only`, `action_taxonomy`, `action_visual`, `full`.
- Requested model: `gpt-4o`; temperature: 0.
- Total latest attempts: 424; valid: 424; failed: 0.
- Prediction coverage: 106/106 for every condition.
- Every valid attempt contains `input.json`, `raw_response.txt`, `prediction.json`, and `status.json`.
- The endpoint returned `gpt-4o-2024-11-20` for most requests and the requested alias `gpt-4o` for the remainder; both identifiers are retained per attempt.
- Raw artifacts: `outputs/paper/formal/E002_c3_v1/`.
- Recomputable metrics: `outputs/paper/formal/E002_c3_v1/c3_metrics.json`.

## Primary results

The table reports the prespecified site macro-average. Type accuracy is measured over human-confirmed risk-positive samples; missed positives count as type errors.

| Condition | Precision | Recall | F1 | Primary type accuracy |
|---|---:|---:|---:|---:|
| Action only | 90.4% | 97.5% | 93.7% | 52.5% |
| Action + taxonomy | 89.0% | 95.0% | 91.9% | 75.8% |
| Action + visual | 96.2% | 90.0% | 92.4% | 65.0% |
| Full | 87.8% | 100.0% | 93.5% | 85.0% |

Full pooled counts are TP=32, FP=5, FN=0, TN=69. Its pooled precision, recall, and F1 are 86.5%, 100.0%, and 92.8%; pooled primary type accuracy is 87.5%.

The run-clustered 95% bootstrap interval for Full site-macro F1 is 89.9–96.5%. The corresponding Full precision interval is 81.7–93.5%; recall remains 100% in every run-level resample.

## Prespecified ablations

F1 differences use paired run-within-site bootstrap resampling with seed `20260920` and 10,000 resamples.

| Comparison | Site-macro F1 difference | 95% interval |
|---|---:|---:|
| Full − Action + taxonomy: visual-context contribution | +1.6 pp | −3.8 to +7.1 pp |
| Full − Action + visual: taxonomy contribution | +1.0 pp | −2.4 to +6.2 pp |
| Full − Action only: complete-input difference | −0.2 pp | −3.1 to +3.5 pp |

The formal data therefore do **not** support a claim that Full improves binary F1 over every reduced condition. The evidence supports a narrower conclusion: Full achieved complete risk recall and substantially more accurate primary risk typing than action-only or visual-only inputs, at the cost of more false positives. Neither component's F1 difference excludes zero at the run level.

## Site breakdown for Full

| Site | Precision | Recall | F1 | Type accuracy |
|---|---:|---:|---:|---:|
| Practice Shopping | 92.3% | 100.0% | 96.0% | 75.0% |
| SauceDemo | 83.3% | 100.0% | 90.9% | 95.0% |

## Interpretation boundary

Only `financial_transaction` and `sensitive_data` have natural positive support in this dataset. No conclusion is made for the other taxonomy categories, unseen sites, unproposed page actions, harm prevention, or deployment-time intervention. The previously extracted C2 runtime Full diagnostic remains separate from this controlled rerun and is not mixed into the ablation table.
