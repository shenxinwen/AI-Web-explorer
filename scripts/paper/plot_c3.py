"""Plot the frozen C3 external formal comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def build_plot_data(metrics: Mapping[str, Any]) -> dict[str, list[float]]:
    result = {}
    for key, label in (
        ("action_taxonomy", "Text only"),
        ("full", "Context conditioned"),
    ):
        pooled = metrics[key]["classification"]["pooled"]
        result[label] = [
            100 * pooled["precision"],
            100 * pooled["recall"],
            100 * pooled["f1"],
            100 * metrics[key]["acceptable_type"]["accuracy"],
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    data = build_plot_data(metrics)
    labels = ["Precision", "Recall", "F1", "Acceptable type"]
    positions = np.arange(len(labels))
    width = 0.36
    fig, axis = plt.subplots(figsize=(8.2, 4.6))
    colors = ("#7A8A99", "#2878B5")
    for index, (condition, values) in enumerate(data.items()):
        offset = (index - 0.5) * width
        bars = axis.bar(positions + offset, values, width, label=condition, color=colors[index])
        axis.bar_label(bars, fmt="%.1f", padding=2, fontsize=9)
    axis.set_ylabel("Score (%)")
    axis.set_ylim(0, 100)
    axis.set_xticks(positions, labels)
    axis.legend(frameon=False, ncol=2, loc="upper center")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200)
    plt.close(fig)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
