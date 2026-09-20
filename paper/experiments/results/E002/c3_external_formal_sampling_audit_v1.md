# C3 External Formal Sampling Audit v1

> Sampling date: 2026-09-20
>
> Status: candidate manifest, screenshots, and human-confirmed gold are frozen; no formal model calls have started.

## Frozen construction

- Deterministic seed: `20260920`.
- Requested total: 100 samples.
- Realized context subset: 30 readable same-action pairs (60 samples).
- Realized diversity subset: 40 samples.
- Pilot exclusion: all 10 pilot screenshot IDs excluded.
- Diversity sampling strata: SAFE 14, LOW 13, HIGH 13. These WebGuard labels are sampling metadata only, not VERA gold.

Quality takes precedence over the maximum pair target. The sampler rejects inaccessible or malformed target strings, including embedded accessibility attributes, structured `name`/`value` fragments, numeric-only targets, known placeholder text, and strings at the source's apparent 30-character truncation boundary. The current qualified pool still supported 30 pairs without relaxing these rules.

## Audit results

- Source metadata rows: 6,491.
- Eligible rows after final-review, pilot, screenshot-ID, and action-text filters: 3,281.
- Excluded non-final labels: 1,535.
- Excluded unusable action targets: 1,665.
- Excluded pilot rows: 10.
- Selected samples: 100.
- Duplicate selected screenshot IDs: 0.
- Pilot overlap: 0.
- Unique websites: 80.
- Unique normalized action targets: 66.
- Blinded-manifest leakage check: no WebGuard label, reviewer reason, or source page URL fields.

## Screenshot gate

- First download pass: 84 valid, 16 transient SSL/timeout failures.
- Failed-only retry: 99 valid, 1 transient SSL failure.
- Final single-item retry: 100 valid, 0 failed.
- Valid formats: 100 PNG.
- Duplicate image-content hashes: 0.

All transient failures remain visible in the run history described above; the final machine-readable audit records the verified terminal state. No failed item was silently replaced with another source sample.

## Artifacts

- Blinded annotation/evaluation manifest: `outputs/paper/formal/E002_c3_external_v1/formal_samples_blinded.json`
- Private sampling audit manifest: `outputs/paper/formal/E002_c3_external_v1/formal_samples_audit.json`
- Machine-readable sampling audit: `outputs/paper/formal/E002_c3_external_v1/sampling_audit.json`
- Screenshot audit: `outputs/paper/formal/E002_c3_external_v1/screenshot_audit.json`
- Downloaded screenshots: `outputs/paper/formal/E002_c3_external_v1/screenshots/`
- Shuffled blind annotation sheet: `outputs/paper/formal/E002_c3_external_v1/annotations_blind.csv`
- Sampler: `scripts/paper/build_c3_external_formal_manifest.py`
- Screenshot validator: `scripts/paper/fetch_c3_external_screenshots.py`
- Annotation-sheet builder: `scripts/paper/build_c3_external_annotation_sheet.py`

SHA-256 at generation time:

- blinded manifest: `214807B7CB2575FCD229EC0B192B295D860AC81EDD929FC8052DE21DA6C1942D`
- audit manifest: `1699AAE723680EE45AE6FE72F1F4193AA72A2C5F2B4B708AC5291CB4C09FA68C`
- terminal screenshot audit: `F721926EF96E46CEA85F4FBDECD0531FD7050218FDB7CA864F23A4B62BAEB0D4`
- blind annotation sheet: `DDF80F00073BC3173E49837F2234D90466D6EE2170AA860DC6FA59024ADF98EC`

## Remaining gate

Human review was completed on 2026-09-20. All 100 AI-initial binary labels, acceptable type sets, and evidence statements were confirmed without correction and frozen as `outputs/paper/formal/E002_c3_external_v1/annotations_human_confirmed.csv` (SHA-256 `C879AA4BFBEAE4E1EE7CE354E733465FB1085A5DCEBE16E621BEEF3359ABF60B`).

The confirmed gold contains 65 risk-positive and 35 risk-negative samples. Primary explanatory types are: 24 `sensitive_data`, 21 `account_and_permission`, 18 `external_communication`, one `financial_transaction`, and one `destructive_change`. Eight of the 30 candidate context pairs are binary-discordant under VERA gold; pair metrics must use this prespecified realized subset rather than WebGuard source labels.

The remaining pre-run gate is configuration and traceability verification for the two frozen conditions. Formal execution must not tune prompts or resample after inspecting results.
