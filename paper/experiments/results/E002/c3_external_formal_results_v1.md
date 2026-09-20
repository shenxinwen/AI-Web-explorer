# C3 External Context-Challenge Formal Results v1

> Run date: 2026-09-20
>
> Status: complete two-condition run; descriptive results frozen. Confidence intervals remain to be added before paper use.

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

Binary confusion counts were `TP=38, FP=11, FN=27, TN=24` for Text only and `TP=46, FP=17, FN=19, TN=18` for Context conditioned. Prediction coverage was 100% in both conditions.

Only eight of the 30 candidate pairs were binary-discordant after independent VERA annotation. Pair metrics use those eight pairs: Text only classified neither pair jointly correctly, while Context conditioned classified two pairs jointly correctly and made the correct risk flip on the same two pairs.

## Initial interpretation

Visual context improved recall by 12.3 percentage points and F1 by 5.2 points, while precision decreased by 4.6 points. Thus, the context-conditioned assessor identified more of the human-confirmed risk actions but also became more conservative, producing six additional false positives.

Acceptable-type accuracy increased by 35.4 points. This supports the narrower claim that visual context helps connect an ambiguous action label to a plausible environmental consequence and explanatory risk category. The pair result points in the same direction but remains weak in absolute terms: only 2/8 discordant pairs were fully correct.

These are descriptive point estimates. The result does not yet include pair/singleton cluster-bootstrap intervals, and the small realized discordant-pair subset limits strong claims about risk-flip performance.
