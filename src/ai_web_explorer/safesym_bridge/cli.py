from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_explored_capability_graph,
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
    write_capability_graph,
    write_observed_graph,
)
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def write_saucedemo_pddl(output_dir: Path) -> Path:
    graph = build_observed_graph(
        app="saucedemo",
        start_node="login",
        transitions=build_saucedemo_mvp_transitions(),
    )
    write_pddl_artifacts(graph, output_dir)
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate SauceDemo graph and PDDL artifacts. "
            "Recommended path: explore-graph or explore-pddl."
        )
    )
    subparsers = parser.add_subparsers(dest="mode")

    graph_parser = subparsers.add_parser(
        "graph",
        help="Debug: write graph JSON from fixed MVP transitions.",
    )
    graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_observed_graph.json"),
        help="Path to write the generated observed graph JSON.",
    )
    capability_graph_parser = subparsers.add_parser(
        "capability-graph",
        help="Experimental: write capability graph JSON from fixed MVP transitions.",
    )
    capability_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_capability_graph.json"),
        help="Path to write the generated capability graph JSON.",
    )
    pddl_parser = subparsers.add_parser(
        "pddl",
        help="Debug: write PDDL from fixed-transition graph.",
    )
    pddl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/safesym_e2e/graph_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    explore_graph_parser = subparsers.add_parser(
        "explore-graph",
        help="Recommended: run graph-guided browser exploration and write graph JSON.",
    )
    explore_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_explored_graph.json"),
        help="Path to write the explored graph JSON.",
    )
    explore_graph_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )
    explore_capability_graph_parser = subparsers.add_parser(
        "explore-capability-graph",
        help="Experimental: run browser exploration and write capability graph JSON.",
    )
    explore_capability_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_explored_capability_graph.json"),
        help="Path to write the explored capability graph JSON.",
    )
    explore_capability_graph_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )
    explore_pddl_parser = subparsers.add_parser(
        "explore-pddl",
        help="Recommended: explore with browser and write graph-derived PDDL.",
    )
    explore_pddl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/safesym_e2e/explored_graph_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    explore_pddl_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )

    args = parser.parse_args(argv)

    try:
        if args.mode == "explore-graph":
            output_path = asyncio.run(
                run_saucedemo_explored_graph(
                    args.output,
                    headless=not args.headed,
                )
            )
        elif args.mode == "explore-capability-graph":
            output_path = asyncio.run(
                run_saucedemo_explored_capability_graph(
                    args.output,
                    headless=not args.headed,
                )
            )
        elif args.mode == "explore-pddl":
            output_path = asyncio.run(
                run_saucedemo_explored_pddl(
                    args.output,
                    headless=not args.headed,
                )
            )
        elif args.mode == "graph":
            output_path = write_observed_graph(
                build_saucedemo_mvp_transitions(),
                args.output,
            )
        elif args.mode == "capability-graph":
            output_path = write_capability_graph(
                build_saucedemo_mvp_transitions(),
                args.output,
            )
        elif args.mode == "pddl":
            output_path = write_saucedemo_pddl(args.output)
        else:
            parser.print_help()
            return 2
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Wrote output to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
