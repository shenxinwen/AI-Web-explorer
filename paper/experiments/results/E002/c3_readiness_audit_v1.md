# E002 / C3 Readiness Audit v1

> Audit date: 2026-09-20
>
> Status: readiness passed; formal matrix not yet started.

## Dataset and trace audit

- Source: six valid C2 Full runs, three per site.
- Ordinary exploration attempts: 130; all have unique attempt IDs, decodable before screenshots, and runtime risk records.
- Frozen primary set: 106 samples after removing 24 repeated actions within the same run and semantic location. Cross-run repetitions remain.
- Gold: 32 risk-positive samples (`financial_transaction` 14, `sensitive_data` 18), reviewed and confirmed by the human reviewer.
- Primary-sample linkage: 106/106 samples link to source site, run, attempt, action, semantic location, screenshot, and runtime risk record.
- Replay remains an auxiliary logging audit and is excluded from classification accuracy.

No C2 configuration, artifact, metric, or result was modified.

## Runtime Full diagnostic

The already-recorded C2 Full shadow judgments were joined to the frozen C3 gold as a diagnostic. They are not a substitute for the controlled four-condition ablation.

| Scope | Precision | Recall | F1 | Type accuracy |
|---|---:|---:|---:|---:|
| Practice Shopping | 92.3% | 100.0% | 96.0% | 75.0% |
| SauceDemo | 90.9% | 100.0% | 95.2% | 100.0% |
| Site macro-average | 91.6% | 100.0% | 95.6% | 87.5% |
| Pooled 106 samples | 91.4% | 100.0% | 95.5% | 90.6% |

Pooled confusion counts are TP=32, FP=3, FN=0, TN=71. Run-clustered bootstrap with seed `20260920` and 10,000 resamples gives a site-macro 95% interval of 85.7–97.7% for precision and 92.2–98.8% for F1. Recall is 100% in every resample.

Observed errors are concentrated at annotation boundaries: opening a cart, removing a cart item, and adding an item were over-classified as risky; three payment-detail actions were detected as risky but assigned `financial_transaction` rather than the gold `sensitive_data` primary type.

Machine-readable point estimates and intervals are in `outputs/paper/pilot/E002_c3_v1/c3_readiness_metrics.json`.

## Pilot implementation readiness

- A frozen, balanced 20-sample pilot manifest exists: 10 samples per site, with 5 positive and 5 negative samples per site.
- The four input conditions are mechanically isolated: action only, action + taxonomy, action + visual context, and Full.
- Full reuses the deployed C3 system prompt exactly. Reduced conditions remove only the unavailable input assumptions; category keys remain as the output schema, while taxonomy definitions and examples appear only in taxonomy conditions.
- Every attempt writes immutable input and status records; valid responses additionally write raw response and parsed prediction. Retries create a new attempt directory.
- Metric recomputation covers pooled and per-site confusion counts, site macro-averages, type accuracy, coverage, and run-clustered bootstrap intervals.
- Fifteen failed `action_only` attempt directories from the first connectivity attempt are retained and excluded from accuracy.

## External-model pilot result

The frozen 20-sample, four-condition pilot completed with 80/80 valid latest attempts and no new failures. Every valid attempt contains an input record, raw response, parsed prediction, status, model identifier, and sample linkage.

| Condition | Precision | Recall | Site-macro F1 | Type accuracy |
|---|---:|---:|---:|---:|
| Action only | 100.0% | 90.0% | 94.4% | 60.0% |
| Action + taxonomy | 90.0% | 90.0% | 90.0% | 90.0% |
| Action + visual | 100.0% | 90.0% | 94.4% | 80.0% |
| Full | 83.3% | 100.0% | 90.9% | 90.0% |

These values are readiness diagnostics, not formal results. Full trades two false positives for zero false negatives on this deliberately balanced small subset. The prompt and taxonomy must not be tuned against these outcomes before the formal run.

## Formal-run gate

All predefined readiness checks now pass. The remaining operational step is explicit authorization for the larger formal transfer: four conditions over 106 samples, including 212 visual requests carrying the frozen before-action screenshots, action labels, and taxonomy where applicable. Formal outputs must be written to `outputs/paper/formal/E002_c3_v1/`; pilot attempts must not be copied into formal results.

No adapted external-method score will be reported as a numerical baseline. Closely related methods may be used only to motivate the evaluation design and position the contribution.
