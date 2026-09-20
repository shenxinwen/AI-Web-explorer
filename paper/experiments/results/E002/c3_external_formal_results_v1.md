# C3 External Context-Challenge Formal Results v1

> Run date: 2026-09-20
>
> Status: complete two-condition run with frozen cluster-bootstrap uncertainty estimates and post-run error analysis.

## Execution audit

- Formal samples: 100, including 30 candidate context pairs and 40 diversity samples.
- Human-confirmed VERA gold: 65 risk-positive and 35 risk-negative.
- Main conditions: `action_taxonomy` (Text only) and `full` (Context conditioned).
- Requested model: `gpt-4o`; temperature: 0; prompt version: `c3-ablation-prompt-v1`.
- Calls: 200/200 valid, zero failed, zero missing required artifact files.
- Returned model field: `gpt-4o-2024-11-20` for 182 calls and provider alias `gpt-4o` for 18 calls, split evenly across conditions.
- Raw artifacts: `outputs/paper/formal/E002_c3_external_v1/runs/`.
- Recomputed metrics: `outputs/paper/formal/E002_c3_external_v1/formal_metrics.json`.

## Main results

| Condition | Precision | Recall | F1 | Acceptable-type accuracy | Pair joint accuracy | Correct risk-flip rate |
|---|---:|---:|---:|---:|---:|---:|
| Text only | 77.6% | 58.5% | 66.7% | 27.7% | 0.0% | 0.0% |
| Context conditioned | 73.0% | 70.8% | 71.9% | 63.1% | 25.0% | 25.0% |

![C3 external main metrics](c3_external_main_metrics.png)

Binary confusion counts were `TP=38, FP=11, FN=27, TN=24` for Text only and `TP=46, FP=17, FN=19, TN=18` for Context conditioned. Prediction coverage was 100% in both conditions.

Only eight of the 30 candidate pairs were binary-discordant after independent VERA annotation. Pair metrics use those eight pairs: Text only classified neither pair jointly correctly, while Context conditioned classified two pairs jointly correctly and made the correct risk flip on the same two pairs.

## Initial interpretation

Visual context improved recall by 12.3 percentage points and F1 by 5.2 points, while precision decreased by 4.6 points. Thus, the context-conditioned assessor identified more of the human-confirmed risk actions but also became more conservative, producing six additional false positives.

Acceptable-type accuracy increased by 35.4 points. This supports the narrower claim that visual context helps connect an ambiguous action label to a plausible environmental consequence and explanatory risk category. The pair result points in the same direction but remains weak in absolute terms: only 2/8 discordant pairs were fully correct.

## Cluster-bootstrap uncertainty

Using 10,000 deterministic bootstrap replicates with the 30 context pairs as paired clusters and the 40 diversity samples as singleton clusters (`seed=20260920`):

| Metric | Text only 95% CI | Context conditioned 95% CI | Full−Text difference (95% CI) |
|---|---:|---:|---:|
| Precision | [65.9%, 88.9%] | [61.0%, 84.4%] | −4.5 pp [−15.1, +4.7] |
| Recall | [43.9%, 72.6%] | [58.7%, 82.4%] | +12.3 pp [−2.0, +27.4] |
| F1 | [54.5%, 76.7%] | [61.8%, 80.6%] | +5.2 pp [−5.6, +17.1] |
| Acceptable-type accuracy | [15.9%, 40.6%] | [50.0%, 75.5%] | +35.4 pp [+21.7, +49.3] |
| Pair joint / correct flip | [0.0%, 0.0%] | [0.0%, 60.0%] | +25.0 pp [0.0, +60.0] |

The F1 and recall difference intervals include zero, so the binary improvement should be described as a positive point estimate rather than a statistically resolved gain. The acceptable-type improvement is the clearest formal result. The small realized discordant-pair subset limits strong claims about risk-flip performance.

## Error analysis

Across all 100 samples, visual context corrected 16 binary decisions, introduced 14 errors, left 48 correct under both conditions, and left 22 wrong under both. The 16 corrections comprised 14 recovered positives and two corrected false alarms; the 14 introduced errors comprised six missed positives and eight new false alarms. Thus, the net recall improvement came with a clear conservatism cost.

For acceptable risk type, context corrected 25 decisions and introduced only two type errors; 16 were correct and 22 wrong under both conditions. The strongest supported contribution is therefore improved grounding of the risk consequence and its formal category, rather than uniformly superior binary discrimination.

The new false positives often treated entry into an upload, invitation, sharing, registration, cart, or package-building workflow as though the immediate click had already produced the downstream effect. This identifies an immediate-effect versus possible-downstream-effect boundary for future work; the frozen prompt and labels were not changed after observing it. Full details are in `c3_external_error_analysis_v1.md` and the `error_analysis` section of the recomputable metrics JSON.

## Claim boundary

The external formal set supports the claim that current visual context changes risk judgments and materially improves acceptable risk-type grounding. It provides positive but statistically unresolved binary F1 and recall estimates, and weak pair-level evidence because only eight candidate pairs were label-discordant. It does not establish end-to-end harm prevention, deployment-time intervention effectiveness, or generalization to actions not supplied to the assessor.
