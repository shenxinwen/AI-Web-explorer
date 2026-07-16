from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    run_web_kobe_exploration,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explore web pages into Web-KOBE graphs and project them to "
            "SafeSym/PDDL-facing artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="mode")

    web_kobe_graph_parser = subparsers.add_parser(
        "web-kobe-graph",
        help="Debug: write a Web-KOBE exploration graph JSON.",
    )
    web_kobe_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_graph.json"),
        help="Path to write the generated Web-KOBE graph JSON.",
    )
    web_kobe_explore_parser = subparsers.add_parser(
        "web-kobe-explore",
        help="Run real Playwright Web-KOBE exploration and write graph JSON.",
    )
    web_kobe_explore_parser.add_argument("--url", required=True)
    web_kobe_explore_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_explored_graph.json"),
        help="Path to write the explored Web-KOBE graph JSON.",
    )
    web_kobe_explore_parser.add_argument("--app-name", default="web")
    web_kobe_explore_parser.add_argument("--page-id", default=None)
    web_kobe_explore_parser.add_argument("--steps", type=int, default=1)
    web_kobe_explore_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running exploration.",
    )
    web_kobe_pddl_parser = subparsers.add_parser(
        "web-kobe-pddl",
        help="Debug: write PDDL from the debug Web-KOBE graph.",
    )
    web_kobe_pddl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    web_kobe_pddl_parser.add_argument(
        "--goal-node",
        required=True,
        help="Goal node ID for the generated Web-KOBE PDDL problem.",
    )
    web_kobe_pddl_from_graph_parser = subparsers.add_parser(
        "web-kobe-pddl-from-graph",
        help="Write PDDL from an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_pddl"),
        help="Directory to write domain.pddl and problem.pddl.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--goal-node",
        required=True,
        help="Goal node ID for the generated Web-KOBE PDDL problem.",
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--start-node",
        default=None,
        help="Optional start node override. Defaults to graph.start_node_id.",
    )
    web_kobe_pddl_smoke_parser = subparsers.add_parser(
        "web-kobe-pddl-smoke",
        help="Write Web-KOBE PDDL plus planning-readiness smoke report.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to an explored Web-KOBE graph JSON.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_pddl_smoke"),
        help="Directory to write domain.pddl, problem.pddl, and smoke_report.json.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--goal-node",
        required=True,
        help="Goal node ID for the generated Web-KOBE PDDL problem.",
    )
    web_kobe_pddl_smoke_parser.add_argument(
        "--start-node",
        default=None,
        help="Optional start node override. Defaults to graph.start_node_id.",
    )

    args = parser.parse_args(argv)

    try:
        if args.mode == "web-kobe-explore":
            output_path = asyncio.run(
                run_web_kobe_exploration(
                    args.url,
                    args.output,
                    app_name=args.app_name,
                    page_id=args.page_id,
                    steps=args.steps,
                    headless=not args.headed,
                )
            )
        elif args.mode == "web-kobe-graph":
            output_path = write_web_kobe_graph(
                build_debug_web_kobe_graph(),
                args.output,
            )
        elif args.mode == "web-kobe-pddl":
            graph = build_debug_web_kobe_graph()
            artifacts = compile_web_kobe_graph_to_pddl(
                graph,
                goal_node_id=args.goal_node,
            )
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "domain.pddl").write_text(
                artifacts.domain,
                encoding="utf-8",
            )
            (args.output / "problem.pddl").write_text(
                artifacts.problem,
                encoding="utf-8",
            )
            output_path = args.output
        elif args.mode == "web-kobe-pddl-from-graph":
            graph = load_web_kobe_graph_json(args.graph)
            artifacts = compile_web_kobe_graph_to_pddl(
                graph,
                start_node_id=args.start_node,
                goal_node_id=args.goal_node,
            )
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "domain.pddl").write_text(
                artifacts.domain,
                encoding="utf-8",
            )
            (args.output / "problem.pddl").write_text(
                artifacts.problem,
                encoding="utf-8",
            )
            output_path = args.output
        elif args.mode == "web-kobe-pddl-smoke":
            graph = load_web_kobe_graph_json(args.graph)
            result = write_web_kobe_pddl_smoke(
                graph,
                args.output,
                start_node_id=args.start_node,
                goal_node_id=args.goal_node,
            )
            output_path = result.output_dir
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
