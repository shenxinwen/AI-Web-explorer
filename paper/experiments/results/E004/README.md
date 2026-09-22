# E004 / C2: Execution-Grounded Functional Model Induction

## Canonical artifacts

- [Final report](final/c2_final_results.md)
- [Human-confirmed coverage ledger](final/c2_coverage_mapping_ledger_v1.md)
- [Coverage ledger CSV](final/c2_coverage_mapping_ledger_v1.csv)
- [Canonical machine-readable metrics](final/c2_metrics_final.json)
- [Final figures](final/figures/)

The canonical package covers 18 valid formal-v2 runs over Random, Linear, and
Full conditions. The coverage ledger was human-confirmed before the final
summary was frozen. The canonical metric file was previously named
`c2_metrics_consolidated_ai_initial.json`; only its filename changed during
organization, not its contents.

For compatibility with the byte-preserved frozen report, an identical legacy
filename is retained beside `c2_metrics_final.json`. New manuscript references
and plotting commands should use `c2_metrics_final.json`.

The frozen report also retains its historical relative links to analysis
scripts. Use the repository-level commands in `paper/figures/figure_manifest.md`
instead of resolving those links from the reorganized directory.

## Provenance

[`provenance/`](provenance/) contains the chronological experiment history,
execution snapshots, partial AI-initial reviews, and the core-inventory audit.
Replacement and archived raw run identifiers are intentionally preserved in
these records.

## Local raw roots

- `outputs/paper/formal/E004_c2_v1/`
- `outputs/paper/formal/E004_c2_v2/`

The raw roots remain ignored and are not included in the Git collaboration
package.
