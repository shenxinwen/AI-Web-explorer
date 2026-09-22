# Paper Experiment Artifact Organization Design

## Objective

Reorganize the frozen C1--C3 experiment files so that collaborators can find
the paper-ready evidence quickly, while preserving protocol evolution and audit
history and keeping large raw artifacts out of the main Git repository until
their privacy, licensing, and distribution status is reviewed.

The reorganization must not recalculate, edit, or reinterpret any frozen C1,
C2, or C3 result.

## Current State

- Local `main` is 22 commits ahead of `origin/main`.
- The tracked result packages under `paper/experiments/results/` contain about
  0.31 MB and are suitable for ordinary Git collaboration.
- Ignored formal artifacts under `outputs/paper/formal/` contain more than
  4,300 files and about 390 MB, dominated by screenshots.
- Result directories currently mix final reports, pilot records, readiness
  audits, partial reviews, manifests, and superseded naming such as
  `*_ai_initial`.
- Some raw traces contain credential-related or email-like text and require a
  value-level sanitization review before publication.
- C3 external screenshots were derived from an external dataset and require a
  redistribution-license check before publication.
- The repository root currently has no explicit license file.

## Organization Model

Use three conceptual layers:

1. **Final:** canonical paper-facing reports, confirmed gold, machine-readable
   metrics, frozen configs, and figures.
2. **Provenance:** experiment design history, pilot/readiness records,
   superseded outputs, failure/replacement decisions, and intermediate reviews.
3. **Raw:** complete trajectories, screenshots, per-call model outputs, and
   browser traces. Raw artifacts remain under ignored `outputs/` paths in this
   change and are not added to Git.

The tracked layout will be:

```text
paper/experiments/
├── README.md
├── registry.md
├── configs/
├── core_functions/
└── results/
    ├── README.md
    ├── E002/
    │   ├── README.md
    │   ├── final/
    │   └── provenance/
    ├── E003/
    │   ├── README.md
    │   ├── final/
    │   └── provenance/
    └── E004/
        ├── README.md
        ├── final/
        └── provenance/
```

Each experiment-level `README.md` is the stable entry point. It identifies the
paper claim, canonical files, frozen sample/run counts, raw local roots, and the
boundary between final evidence and provenance.

## Planned Classification

### E002 / C3

`final/` will contain:

- `c3_final_results.md`;
- exploration-linked and external formal reports;
- external error analysis;
- the main metric figure;
- frozen configuration and final/formal artifact manifests.

`provenance/` will contain:

- experiment design and external-context protocol;
- readiness and feasibility audits;
- formal sampling audit;
- pilot result records.

### E003 / C1

`final/` will contain:

- the current result `README.md`, renamed to `c1_final_results.md`;
- canonical `c1_metrics.json`;
- confirmed gold CSV files.

`provenance/` will contain `c1_metrics_generated.json`, documented as a
superseded/generated summary rather than the canonical paper metric file.

### E004 / C2

`final/` will contain:

- `c2_final_results.md`;
- the accepted coverage ledger in Markdown and CSV;
- the final machine-readable metric file, renamed from
  `c2_metrics_consolidated_ai_initial.json` to `c2_metrics_final.json` without
  changing its contents;
- final figures.

`provenance/` will contain:

- the current chronological `README.md`, renamed to
  `experiment_history.md`;
- execution-status snapshots;
- partial AI-initial review reports;
- core-inventory audit records.

The experiment entry README will explain that the final coverage ledger was
human-confirmed even where historical filenames contain `ai_initial`.

## Naming Rules

- Use lowercase snake_case for files.
- Keep stable experiment IDs (`E002`, `E003`, `E004`) because they are already
  referenced throughout the paper records.
- Use `*_final.*` only for canonical, frozen paper-facing artifacts.
- Retain explicit version suffixes (`_v1`) for protocols, schemas, manifests,
  and audits whose versions have archival meaning.
- Do not rename raw run directories or replacement/archived run identifiers;
  their names are part of the audit trail.
- Avoid `ai_initial` in canonical final filenames. Historical provenance files
  may retain it when it accurately describes their original role.

## Link and Reference Updates

Update all tracked references in:

- `paper/STATUS.md`;
- `paper/05_experiments.md`, `paper/06_results.md`, and
  `paper/07_reproducibility.md`;
- `paper/figures/figure_manifest.md`;
- `paper/experiments/registry.md`;
- result-package internal links;
- analysis and plotting script defaults or documented commands.

Raw artifact paths remain unchanged. Frozen manifest checksums that refer to
file contents remain valid because tracked artifacts are moved or renamed
without content edits. If a manifest records a path as well as a checksum, the
new entry README will distinguish the historical recorded path from the current
repository path instead of rewriting the frozen manifest.

## Safety and Preservation Rules

- Use Git-aware moves so file history remains visible.
- Do not delete ignored raw outputs, failed runs, replacement runs, pilot data,
  screenshots, model responses, or human-confirmed labels.
- Do not modify frozen numeric results, gold labels, figures, or manifest
  contents.
- Do not add ignored `outputs/` directories to Git in this change.
- Do not commit the generated manuscript PDF.
- Keep the current uncommitted manuscript Experimental Setup changes separate
  from the artifact-organization commit.

## Verification

Before moving files, record SHA-256 hashes for every tracked artifact classified
as final. After moving, verify the same content hashes.

Then verify:

1. `git diff --check` passes.
2. Every experiment README links to existing files.
3. Repository-wide references to old tracked paths are either updated or
   explicitly documented as historical paths.
4. Canonical metric and figure paths used by scripts and paper documentation
   resolve.
5. No file under `outputs/` becomes tracked.
6. Frozen result numbers in the final reports are unchanged.
7. `git status` contains only the intended organization changes plus the
   pre-existing manuscript draft and ignored PDF.

No analysis script will be rerun as part of this reorganization, because the
task is to preserve and expose frozen results rather than recompute them.

## Raw Artifact Publication Follow-up

Raw artifacts are a separate release decision. Before publication they require:

- a value-level credential and personal-data review;
- confirmation that external screenshots can be redistributed;
- an explicit repository/data license decision;
- a compact manifest and archive format;
- selection among Git LFS, GitHub Releases, or a dedicated artifact host.

This follow-up is not required for collaborators to begin paper writing from
the tracked final packages.
