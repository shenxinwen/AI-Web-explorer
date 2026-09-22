# VERA Paper Experiments

This directory contains the frozen protocols, configurations, analysis scripts,
and paper-facing result packages for VERA.

## Start here

| Paper question | Experiment | Canonical result package |
| --- | --- | --- |
| C1 / RQ1: evidence-grounded knowledge admission | E003 | [`results/E003/`](results/E003/) |
| C2 / RQ2: execution-grounded model induction | E004 | [`results/E004/`](results/E004/) |
| C3 / RQ3: context-conditioned risk awareness | E002 | [`results/E002/`](results/E002/) |

Each result package separates:

- `final/`: frozen artifacts used for paper writing;
- `provenance/`: pilot, readiness, failure, replacement, and protocol-evolution records.

Complete trajectories, screenshots, and per-call model outputs remain under the
ignored local `outputs/paper/` tree. They are not part of the Git collaboration
package pending privacy, licensing, and distribution review.

The stable experiment IDs follow execution history rather than paper order:
E003 maps to C1, E004 to C2, and E002 to C3.

See [`registry.md`](registry.md) for the complete experiment registry and
[`protocol_v1.md`](protocol_v1.md) for the frozen common protocol.
