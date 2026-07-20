from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    run_web_kobe_exploration,
    run_saucedemo_openai_selector_step,
    run_saucedemo_stagehand_step,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import (
    write_web_kobe_safesym_smoke,
)
from ai_web_explorer.safesym_bridge.openai_selector_smoke import (
    write_openai_selector_smoke,
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
        "--screenshot-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory for before/after screenshots. This only "
            "captures local evidence; it does not call a VLM."
        ),
    )
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
    web_kobe_safesym_smoke_parser = subparsers.add_parser(
        "web-kobe-safesym-smoke",
        help="Run SafeSym parser/injection/planner smoke over PDDL artifacts.",
    )
    web_kobe_safesym_smoke_parser.add_argument(
        "--task-dir",
        type=Path,
        required=True,
        help="Directory containing domain.pddl and problem.pddl.",
    )
    web_kobe_safesym_smoke_parser.add_argument(
        "--safesym-root",
        type=Path,
        required=True,
        help="Path to the SafeSym repository root.",
    )
    web_kobe_safesym_smoke_parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="SafeSym safety rules JSON file.",
    )
    web_kobe_safesym_smoke_parser.add_argument(
        "--fast-downward",
        type=Path,
        default=None,
        help="Optional path to fast-downward.py for base/safe plan solves.",
    )
    openai_selector_smoke_parser = subparsers.add_parser(
        "web-kobe-openai-selector-smoke",
        help=("Run a real OpenAI-backed offline SauceDemo action-selection smoke."),
    )
    openai_selector_smoke_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/openai_selector_smoke.json"),
        help="Path to write the selector smoke report JSON.",
    )
    openai_selector_smoke_parser.add_argument(
        "--model",
        default=None,
        help=(
            "Optional OpenAI model override. Defaults to "
            "OPENAI_ACTION_SELECTOR_MODEL or the project default."
        ),
    )
    saucedemo_llm_step_parser = subparsers.add_parser(
        "web-kobe-saucedemo-llm-step-smoke",
        help=(
            "Bootstrap SauceDemo login, run OpenAI-guided Web-KOBE "
            "browser exploration steps, and write graph plus selector trace."
        ),
    )
    saucedemo_llm_step_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_llm_step_graph.json"),
        help="Path to write the Web-KOBE graph JSON.",
    )
    saucedemo_llm_step_parser.add_argument(
        "--selector-trace",
        type=Path,
        default=Path("outputs/saucedemo_llm_step_trace.json"),
        help="Path to write selector trace JSON.",
    )
    saucedemo_llm_step_parser.add_argument(
        "--model",
        default=None,
        help="Optional OpenAI model override.",
    )
    saucedemo_llm_step_parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="Number of Web-KOBE exploration steps to run after login bootstrap.",
    )
    saucedemo_llm_step_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running the smoke.",
    )
    saucedemo_stagehand_parser = subparsers.add_parser(
        "web-kobe-saucedemo-stagehand-smoke",
        help=(
            "Run Stagehand-backed single-step SauceDemo Web-KOBE exploration "
            "and write graph plus Stagehand trace."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_stagehand_graph.json"),
        help="Path to write the Web-KOBE graph JSON.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--stagehand-trace",
        type=Path,
        default=Path("outputs/saucedemo_stagehand_trace.json"),
        help="Path to write Stagehand execution trace JSON.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--model",
        default=None,
        help="Stagehand model name, or set STAGEHAND_MODEL.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--steps",
        type=int,
        default=8,
        help="Maximum number of Stagehand-backed graph steps.",
    )
    saucedemo_stagehand_parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory for before/after screenshots. This only "
            "captures local evidence; VLM analysis requires separate config."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--openai-visual-delta",
        action="store_true",
        help=(
            "Enable observation-side OpenAI vision comparison over captured "
            "before/after screenshots. Requires --screenshot-dir."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--visual-delta-model",
        default=None,
        help=(
            "Optional OpenAI vision model override for --openai-visual-delta. "
            "Defaults to OPENAI_VISUAL_DELTA_MODEL, OPENAI_VISION_MODEL, or "
            "the project default."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--allow-final-order",
        action="store_true",
        help=(
            "Allow the SauceDemo test-site smoke to click Finish and reach "
            "checkout complete. By default the run stops at checkout overview."
        ),
    )
    saucedemo_stagehand_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running the smoke.",
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
                    screenshot_dir=args.screenshot_dir,
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
        elif args.mode == "web-kobe-safesym-smoke":
            result = write_web_kobe_safesym_smoke(
                args.task_dir,
                safesym_root=args.safesym_root,
                rules=args.rules,
                fast_downward=args.fast_downward,
            )
            output_path = result.report_path
        elif args.mode == "web-kobe-openai-selector-smoke":
            result = write_openai_selector_smoke(
                args.output,
                model=args.model,
            )
            output_path = result.report_path
        elif args.mode == "web-kobe-saucedemo-llm-step-smoke":
            output_path = asyncio.run(
                run_saucedemo_openai_selector_step(
                    args.output,
                    selector_trace_path=args.selector_trace,
                    model=args.model,
                    steps=args.steps,
                    headless=not args.headed,
                )
            )
        elif args.mode == "web-kobe-saucedemo-stagehand-smoke":
            output_path = asyncio.run(
                run_saucedemo_stagehand_step(
                    args.output,
                    stagehand_trace_path=args.stagehand_trace,
                    model=args.model,
                    steps=args.steps,
                    headless=not args.headed,
                    screenshot_dir=args.screenshot_dir,
                    use_openai_visual_delta=args.openai_visual_delta,
                    visual_delta_model=args.visual_delta_model,
                    allow_final_order=args.allow_final_order,
                )
            )
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
