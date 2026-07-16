from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    run_saucedemo_explored_capability_graph,
    run_saucedemo_explored_graph,
    run_saucedemo_explored_pddl,
    run_web_kobe_exploration,
    write_capability_graph,
    write_observed_graph,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.observed_graph import build_observed_graph
from ai_web_explorer.safesym_bridge.pddl_compiler import write_pddl_artifacts
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)


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
        elif args.mode == "web-kobe-explore":
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
        elif args.mode == "web-kobe-graph":
            output_path = write_web_kobe_graph(
                build_debug_web_kobe_graph(),
                args.output,
            )
        elif args.mode == "pddl":
            output_path = write_saucedemo_pddl(args.output)
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
