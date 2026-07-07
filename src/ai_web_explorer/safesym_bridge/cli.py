from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate SauceDemo graph and PDDL artifacts for SafeSym."
    )
    subparsers = parser.add_subparsers(dest="mode")

    explore_graph_parser = subparsers.add_parser(
        "explore-graph",
        help="Run graph-guided browser exploration and write graph JSON.",
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

    explore_pddl_parser = subparsers.add_parser(
        "explore-pddl",
        help="Explore with browser and write graph-derived PDDL.",
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

    if args.mode == "explore-graph":
        output_path = asyncio.run(
            run_saucedemo_explored_graph(
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
    else:
        parser.print_help()
        return 2

    print(f"Wrote output to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
