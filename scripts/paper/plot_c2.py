"""Render static C2 result figures from the frozen metrics JSON."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def mean_padded_curves(curves: list[list[int]], budget: int) -> list[float]:
    return [
        sum(curve[min(index, len(curve) - 1)] for curve in curves) / len(curves)
        for index in range(budget)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = json.loads(args.metrics.read_text(encoding="utf-8"))["runs"]
    grouped: dict[tuple[str, str], list[list[int]]] = defaultdict(list)
    for run in runs:
        grouped[(run["site"], run["condition"])].append(run["coverage_growth_curve"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    styles = {"random": ("Random", "#777777"), "linear": ("Linear", "#1f77b4"), "full": ("Full", "#d62728")}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharex=True)
    for axis, site, total in zip(axes, ("practice_shopping", "saucedemo"), (16, 22)):
        for condition, (label, color) in styles.items():
            curve = mean_padded_curves(grouped[(site, condition)], 25)
            axis.plot(range(1, 26), [value / total for value in curve], label=label, color=color)
        axis.set_title("Practice Shopping" if site == "practice_shopping" else "SauceDemo")
        axis.set_xlabel("Ordinary candidate attempts")
        axis.set_ylabel("Function coverage")
        axis.set_ylim(0, 0.7)
        axis.grid(alpha=0.25)
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(args.output_dir / "c2_coverage_growth.png", dpi=200)
    plt.close(fig)

    labels = ["Practice\nrun_02", "SauceDemo\nrun_02", "SauceDemo\nrun_03"]
    added = [2, 3, 3]
    cost = [1, 20, 28]
    fig, axis = plt.subplots(figsize=(6.5, 3.6))
    x = range(len(labels))
    axis.bar([value - 0.18 for value in x], added, width=0.36, label="Replay-added coverage")
    axis.set_ylabel("New covered functions")
    second = axis.twinx()
    second.bar([value + 0.18 for value in x], cost, width=0.36, color="#d62728", label="Replay GUI actions")
    second.set_ylabel("Replay GUI actions")
    axis.set_xticks(list(x), labels)
    axis.legend(loc="upper left", frameon=False)
    second.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(args.output_dir / "c2_replay_cost.png", dpi=200)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
