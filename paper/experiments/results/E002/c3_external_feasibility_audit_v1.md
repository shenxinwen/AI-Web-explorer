# C3 External Context-Challenge Feasibility Audit v1

> Audit date: 2026-09-20
>
> Status: feasible with adaptation; no external evaluation has started.

## Source

Candidate source: WebGuard (`OSU-NLP-Group/WebGuard`), released for research under CC BY-NC 4.0. The local audit copy is stored under `outputs/paper/external/WebGuard/` and is not part of the C3 formal result.

WebGuard is suitable because its evaluation unit is an action grounded in a pre-action webpage screenshot. Its SAFE/LOW/HIGH schema is not equivalent to the VERA risk taxonomy and must not be used as VERA gold through direct label mapping.

## Metadata audit

- Metadata rows: 6,491.
- Final reviewed, non-bug rows: 4,956: SAFE 1,564; LOW 2,284; HIGH 1,108.
- Websites represented in the metadata: 217.
- Rows without a usable free-text `description`: 6,152/6,491 (94.8%).
- Every final reviewed row has an annotation-folder target token that can be parsed after removing the embedded WebGuard label prefix.
- Normalized target phrases: 2,234.
- Target phrases occurring across both different websites and different WebGuard labels: 100 groups, containing 1,358 samples. Examples include `continue`, `submit`, `save`, `next`, `subscribe`, and `save changes`.

The final point makes WebGuard promising for a context challenge: identical or similar target wording appears under different page contexts and consequence labels.

## Screenshot audit

A deterministic 30-item audit selected 10 SAFE, 10 LOW, and 10 HIGH reviewed samples, with no repeated website within each stratum. All 30 Google Drive links returned HTTP 200 PNG images. Observed sizes ranged from approximately 116 KB to 2.8 MB.

Screenshot access is therefore feasible, although the experiment must retain source IDs and download failures rather than silently replacing unavailable samples.

## Required adaptation

The existing WebGuard model input is not directly comparable to VERA C3 because most actions are represented as generic `CLICK` plus element metadata, while C3 consumes a high-level selected-action label.

For the external experiment, construct the candidate action mechanically as:

`<operation> target "<normalized target text>" (<element tag/role>)`

The WebGuard SAFE/LOW/HIGH prefix embedded in folder names must be stripped before sample construction. URL, original WebGuard label, reviewer reason, and post-action information must not be exposed to the evaluated model or VERA gold annotator.

Human gold must be recreated using the frozen VERA annotation guide from only the pre-action screenshot and reconstructed candidate action. The original WebGuard label may be used for stratified sampling and reported separately as schema agreement, but not as VERA ground truth.

## Recommended external experiment

Create a frozen 240-sample set:

- 160 samples forming 80 candidate context pairs with the same normalized target phrase on different websites and differing WebGuard review labels;
- 80 diversity samples stratified across WebGuard SAFE/LOW/HIGH, websites, and target phrases;
- maximum two selected samples per website outside an intentional pair;
- deterministic sampling seed `20260920`;
- no overlap with prompt development or pilot examples.

After VERA relabeling, report all 240 samples and a prespecified context-discordant subset containing candidate pairs whose two VERA gold labels differ.

Run the same four frozen C3 conditions without prompt tuning. In addition to precision, recall, F1, and primary type accuracy, report:

- context-pair joint accuracy: both members classified correctly;
- correct risk-flip rate on VERA-discordant pairs;
- Full-minus-action-only paired difference;
- coverage and invalid-sample reasons.

Use a 24-sample pilot before the 240-sample matrix. External results support cross-site risk-judgment and context-sensitivity claims only; they do not show that VERA itself would propose these actions during exploration.

## Feasibility conclusion

The experiment is feasible and directly addresses the main weakness revealed by the in-situ ablation: action wording alone was often sufficient. The main cost is human relabeling under VERA's taxonomy, not data access or model execution.
