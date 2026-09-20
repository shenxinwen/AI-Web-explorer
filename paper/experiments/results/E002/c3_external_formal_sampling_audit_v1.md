# C3 External Formal Sampling Audit v1

> Sampling date: 2026-09-20
>
> Status: candidate manifest generated; no formal model calls have started. Screenshot availability and human annotation remain pre-run gates.

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

## Artifacts

- Blinded annotation/evaluation manifest: `outputs/paper/formal/E002_c3_external_v1/formal_samples_blinded.json`
- Private sampling audit manifest: `outputs/paper/formal/E002_c3_external_v1/formal_samples_audit.json`
- Machine-readable sampling audit: `outputs/paper/formal/E002_c3_external_v1/sampling_audit.json`
- Sampler: `scripts/paper/build_c3_external_formal_manifest.py`

SHA-256 at generation time:

- blinded manifest: `214807B7CB2575FCD229EC0B192B295D860AC81EDD929FC8052DE21DA6C1942D`
- audit manifest: `1699AAE723680EE45AE6FE72F1F4193AA72A2C5F2B4B708AC5291CB4C09FA68C`

## Remaining gate

Before any model execution, retrieve or verify the 100 screenshots, record download failures without replacement after results are visible, and prepare a prediction-blind human annotation package. Only samples with valid screenshots and complete traceability may enter the formal result.
