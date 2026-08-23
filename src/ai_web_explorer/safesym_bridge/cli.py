from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    build_debug_web_kobe_graph,
    run_stagehand_exploration,
    run_web_kobe_exploration,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    compile_web_kobe_graph_to_domain,
    compile_web_kobe_graph_to_pddl,
    load_web_kobe_graph_json,
    read_web_kobe_graph_json_data,
)
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_domain
from ai_web_explorer.safesym_bridge.location_pddl import compile_location_problem
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
)
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_domain
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_problem
from ai_web_explorer.safesym_bridge.surface_pddl import compile_surface_domain
from ai_web_explorer.safesym_bridge.surface_pddl import compile_surface_problem
from ai_web_explorer.grounded_web.planning_abstraction import (
    build_planning_state_graph,
)
from ai_web_explorer.grounded_web.semantic_planning import (
    build_semantic_planning_graph,
)
from ai_web_explorer.grounded_web.semantic_model import normalize_semantic_id
from ai_web_explorer.grounded_web.embedding_provider import (
    create_embedding_provider_from_env,
)
from ai_web_explorer.safesym_bridge.web_kobe_pddl_smoke import (
    write_web_kobe_pddl_smoke,
)
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import (
    write_web_kobe_safesym_smoke,
)
from ai_web_explorer.grounded_web.exploration_semantics import (
    validate_final_order_authorization,
)
from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits
from ai_web_explorer.grounded_web.resume import (
    ResumePolicy,
    resolve_retry_keys,
    validate_resume_graph,
)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _clean_output_dir_for(paths: list[Path | None]) -> Path:
    resolved_paths = [path for path in paths if path is not None]
    if not resolved_paths:
        raise ValueError("At least one output path is required for cleanup.")
    output_dir = resolved_paths[0].parent
    if any(path.parent != output_dir for path in resolved_paths):
        raise ValueError(
            "--clean-output-dir requires output, trace, and screenshot paths "
            "to share the same parent directory."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return output_dir


def _phase_a_embedding_provider():
    try:
        return create_embedding_provider_from_env()
    except ValueError:
        return None


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
    web_kobe_pddl_parser.add_argument(
        "--goal-fact",
        default=None,
        help=(
            "Optional profile fact predicate to use as the PDDL goal. "
            "Defaults to the goal node location predicate."
        ),
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
        "--goal-fact",
        default=None,
        help=(
            "Optional profile fact predicate to use as the PDDL goal. "
            "Defaults to the goal node location predicate."
        ),
    )
    web_kobe_pddl_from_graph_parser.add_argument(
        "--start-node",
        default=None,
        help="Optional start node override. Defaults to graph.start_node_id.",
    )
    web_kobe_domain_from_graph_parser = subparsers.add_parser(
        "web-kobe-domain-from-graph",
        help="Write only domain.pddl from an explored Web-KOBE graph JSON.",
    )
    web_kobe_domain_from_graph_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to an explored Web-KOBE graph JSON.",
    )
    web_kobe_domain_from_graph_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_domain"),
        help="Directory to write domain.pddl.",
    )
    web_kobe_phase_a_parser = subparsers.add_parser(
        "web-kobe-phase-a",
        aliases=["web-kobe-consolidate"],
        help=(
            "Build a planning-state graph and write planning artifacts plus "
            "the Phase-A domain.pddl."
        ),
    )
    web_kobe_phase_a_parser.add_argument(
        "--graph",
        type=Path,
        required=True,
        help="Path to the raw explored Web-KOBE graph JSON.",
    )
    web_kobe_phase_a_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_phase_a"),
        help="Directory to write raw/planning/report/domain artifacts.",
    )
    web_kobe_phase_a_parser.add_argument(
        "--projection",
        choices=["trace", "location", "surface", "semantic"],
        default="trace",
    )
    web_kobe_phase_a_parser.add_argument("--start-node", default=None)
    web_kobe_phase_a_parser.add_argument("--goal-node", default=None)
    web_kobe_phase_a_parser.add_argument("--start-location", default=None)
    web_kobe_phase_a_parser.add_argument("--goal-location", default=None)
    web_kobe_phase_a_parser.add_argument(
        "--goal-fact", action="append", default=[],
    )
    web_kobe_phase_a_parser.add_argument("--start-checkpoint", default=None)
    web_kobe_phase_a_parser.add_argument("--goal-checkpoint", default=None)
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
        "--goal-fact",
        default=None,
        help=(
            "Optional profile fact predicate to use as the PDDL goal. "
            "Defaults to the goal node location predicate."
        ),
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
    stagehand_explore_parser = subparsers.add_parser(
        "web-kobe-stagehand-explore",
        help="Run generic Stagehand-backed Web-KOBE exploration with graph memory.",
    )
    stagehand_explore_parser.add_argument("--url", required=True)
    stagehand_explore_parser.add_argument("--app-name", default="web")
    stagehand_explore_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/latest/stagehand_explore_graph.json"),
    )
    stagehand_explore_parser.add_argument(
        "--stagehand-trace",
        type=Path,
        default=Path("outputs/latest/stagehand_explore_trace.json"),
    )
    stagehand_explore_parser.add_argument("--model", default=None)
    stagehand_explore_parser.add_argument(
        "--max-exploration-steps", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--max-candidates",
        type=_positive_int,
        default=None,
        help="Maximum VLM business candidates per node.",
    )
    stagehand_explore_parser.add_argument(
        "--max-consecutive-no-progress", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--max-action-attempts-per-candidate", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--max-replay-attempts-per-frontier", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--max-total-replays", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--max-vlm-scan-attempts", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--vlm-request-timeout-seconds", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--stagehand-action-timeout-seconds", type=_positive_int, default=None
    )
    stagehand_explore_parser.add_argument(
        "--viewport-width", type=_positive_int, default=1440
    )
    stagehand_explore_parser.add_argument(
        "--viewport-height", type=_positive_int, default=1000
    )
    stagehand_explore_parser.add_argument(
        "--allow-test-site-final-order", action="store_true"
    )
    stagehand_explore_parser.add_argument("--screenshot-dir", type=Path, default=None)
    stagehand_explore_parser.add_argument(
        "--clean-output-dir",
        action="store_true",
        help=(
            "Delete existing files in the shared output directory before the "
            "run. Intended for per-site latest experiment directories."
        ),
    )
    stagehand_explore_parser.add_argument(
        "--embedding-path",
        type=Path,
        default=Path("outputs/latest/state_embeddings.json"),
    )
    stagehand_explore_parser.add_argument(
        "--state-embeddings",
        action="store_true",
    )
    stagehand_explore_parser.add_argument("--embedding-model", default=None)
    stagehand_explore_parser.add_argument(
        "--embedding-dimension", type=int, default=None
    )
    stagehand_explore_parser.add_argument("--site-purpose", default=None)
    stagehand_explore_parser.add_argument(
        "--business-profile",
        choices=["none", "ecommerce_checkout"],
        default=None,
    )
    stagehand_explore_parser.add_argument("--openai-visual-delta", action="store_true")
    stagehand_explore_parser.add_argument("--visual-delta-model", default=None)
    stagehand_explore_parser.add_argument("--action-outcome-model", default=None)
    stagehand_explore_parser.add_argument(
        "--stagehand-execution-mode",
        choices=["observed_action", "observe_act"],
        default="observed_action",
    )
    stagehand_explore_parser.add_argument(
        "--frontier-replay",
        action="store_true",
        help="Opt in to reset-and-replay of reachable under-explored frontiers.",
    )
    stagehand_explore_parser.add_argument(
        "--resume-graph",
        type=Path,
        default=None,
        help="Resume from a previously checkpointed graph JSON.",
    )
    stagehand_explore_parser.add_argument(
        "--resume-retry-action",
        action="append",
        default=[],
        help="Explicitly authorize retrying a failed or inflight action ID.",
    )
    stagehand_explore_parser.add_argument(
        "--resume-action-max-attempts",
        type=_positive_int,
        default=2,
        help="Maximum attempts for explicitly authorized resume actions.",
    )
    stagehand_explore_parser.add_argument("--headed", action="store_true")
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
                goal_fact=args.goal_fact,
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
                goal_fact=args.goal_fact,
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
        elif args.mode == "web-kobe-domain-from-graph":
            graph = load_web_kobe_graph_json(args.graph)
            domain = compile_web_kobe_graph_to_domain(graph)
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "domain.pddl").write_text(domain, encoding="utf-8")
            output_path = args.output
        elif args.mode in {"web-kobe-phase-a", "web-kobe-consolidate"}:
            if args.projection == "semantic" and any(
                value is not None
                for value in (
                    args.start_node,
                    args.goal_node,
                    args.start_checkpoint,
                    args.goal_checkpoint,
                )
            ):
                web_kobe_phase_a_parser.error(
                    "semantic projection accepts location/fact goals, not node or checkpoint flags"
                )
            if args.projection == "trace" and (
                args.start_node is not None or args.goal_node is not None
            ):
                web_kobe_phase_a_parser.error(
                    "node query flags require --projection location"
                )
            if args.projection in {"location", "surface"} and (
                args.start_checkpoint is not None
                or args.goal_checkpoint is not None
            ):
                web_kobe_phase_a_parser.error(
                    "checkpoint query flags require --projection trace"
                )
            if args.projection == "trace" and (
                (args.start_checkpoint is None)
                != (args.goal_checkpoint is None)
            ):
                web_kobe_phase_a_parser.error(
                    "--start-checkpoint and --goal-checkpoint must be provided together"
                )
            if args.projection == "location" and (
                (args.start_node is None) != (args.goal_node is None)
            ):
                web_kobe_phase_a_parser.error(
                    "--start-node and --goal-node must be provided together"
                )
            if args.projection == "surface" and args.start_node is not None:
                web_kobe_phase_a_parser.error(
                    "surface projection uses graph.start_node_id; omit --start-node"
                )
            args.output.mkdir(parents=True, exist_ok=True)
            problem_path = args.output / "problem.pddl"
            problem_path.unlink(missing_ok=True)
            raw_graph_data = read_web_kobe_graph_json_data(args.graph)
            graph = load_web_kobe_graph_json(args.graph)
            artifacts = build_planning_state_graph(
                graph,
                embedding_provider=_phase_a_embedding_provider(),
            )
            (args.output / "raw_graph.json").write_text(
                json.dumps(raw_graph_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (args.output / "planning_graph.json").write_text(
                json.dumps(
                    artifacts.planning_graph.to_dict(),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (args.output / "planning_abstraction_report.json").write_text(
                json.dumps(artifacts.report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if args.projection == "semantic":
                semantic_graph, semantic_report = build_semantic_planning_graph(graph)
                semantic_report_data = semantic_report.to_dict()
                (args.output / "semantic_planning_graph.json").write_text(
                    json.dumps(
                        semantic_graph.to_dict(), indent=2, ensure_ascii=False
                    ),
                    encoding="utf-8",
                )
                usable_semantic = bool(
                    semantic_graph.start_location
                    and semantic_graph.locations
                    and semantic_graph.actions
                )
                if usable_semantic and args.start_location is not None and (
                    normalize_semantic_id(args.start_location)
                    != normalize_semantic_id(semantic_graph.start_location)
                ):
                    raise ValueError(
                        "start_location_mismatch: "
                        f"{args.start_location} != {semantic_graph.start_location}"
                    )
                if usable_semantic:
                    projection = compile_minimal_semantic_domain(semantic_graph)
                    report_data = dict(semantic_report_data)
                    report_data["fallback_projection"] = None
                    if args.goal_location is not None or args.goal_fact:
                        problem = compile_minimal_semantic_problem(
                            semantic_graph,
                            goal_location=args.goal_location,
                            goal_facts=args.goal_fact,
                        )
                        problem_path.write_text(problem.problem, encoding="utf-8")
                else:
                    projection = compile_location_domain(
                        artifacts.planning_graph,
                        edge_mappings=artifacts.report.edge_mappings,
                    )
                    report_data = dict(semantic_report_data)
                    report_data["fallback_projection"] = "location"
                    report_data["fallback_reason"] = "no_usable_semantic_actions"
                    if args.goal_location is not None or args.goal_fact:
                        report_data["fallback_goal_requested"] = {
                            "goal_location": args.goal_location,
                            "goal_facts": list(args.goal_fact),
                        }
                        report_data["fallback_goal_handled"] = False
            elif args.projection == "trace":
                projection = compile_trace_domain(graph)
            elif args.projection == "location":
                projection = compile_location_domain(
                    artifacts.planning_graph,
                    edge_mappings=artifacts.report.edge_mappings,
                )
            else:
                projection = compile_surface_domain(graph)
            (args.output / "domain.pddl").write_text(
                projection.domain,
                encoding="utf-8",
            )
            (args.output / "projection_report.json").write_text(
                json.dumps(
                    report_data if args.projection == "semantic" else projection.report,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            if args.projection == "semantic":
                (args.output / "semantic_projection_report.json").write_text(
                    json.dumps(
                        report_data,
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
            if args.projection == "trace" and args.start_checkpoint is not None:
                problem = compile_trace_problem(
                    graph,
                    start_checkpoint_id=args.start_checkpoint,
                    goal_checkpoint_id=args.goal_checkpoint,
                )
                problem_path.write_text(
                    problem.problem,
                    encoding="utf-8",
                )
            elif args.projection == "location" and args.start_node is not None:
                problem = compile_location_problem(
                    artifacts.planning_graph,
                    start_node_id=args.start_node,
                    goal_node_id=args.goal_node,
                )
                problem_path.write_text(
                    problem.problem,
                    encoding="utf-8",
                )
            elif args.projection == "surface" and args.goal_node is not None:
                problem = compile_surface_problem(
                    graph,
                    goal_node_id=args.goal_node,
                )
                problem_path.write_text(
                    problem.problem,
                    encoding="utf-8",
                )
            elif args.projection == "semantic":
                report_data = json.loads(
                    (args.output / "semantic_projection_report.json").read_text(
                        encoding="utf-8"
                    )
                )
                if report_data.get("fallback_goal_handled") is False:
                    raise ValueError(
                        "semantic_fallback_cannot_verify_goal: "
                        "explicit semantic goals require a usable semantic projection"
                    )
            else:
                problem_path.unlink(missing_ok=True)
            output_path = args.output
        elif args.mode == "web-kobe-pddl-smoke":
            graph = load_web_kobe_graph_json(args.graph)
            result = write_web_kobe_pddl_smoke(
                graph,
                args.output,
                start_node_id=args.start_node,
                goal_node_id=args.goal_node,
                goal_fact=args.goal_fact,
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
        elif args.mode == "web-kobe-stagehand-explore":
            validate_final_order_authorization(
                start_url=args.url,
                allowed=args.allow_test_site_final_order,
            )
            budget_selected = any(
                value is not None
                for value in (
                    args.max_exploration_steps,
                    args.max_consecutive_no_progress,
                    args.max_action_attempts_per_candidate,
                    args.max_replay_attempts_per_frontier,
                        args.max_total_replays,
                        args.max_vlm_scan_attempts,
                    )
                )
            limits = None
            if budget_selected:
                limits = ExplorationLimits(
                        max_exploration_steps=(
                            args.max_exploration_steps
                            or ExplorationLimits().max_exploration_steps
                        ),
                    max_consecutive_no_progress=(
                        args.max_consecutive_no_progress
                        or ExplorationLimits().max_consecutive_no_progress
                    ),
                    max_action_attempts_per_candidate=(
                        args.max_action_attempts_per_candidate
                        or ExplorationLimits().max_action_attempts_per_candidate
                    ),
                    max_replay_attempts_per_frontier=(
                        args.max_replay_attempts_per_frontier
                        or ExplorationLimits().max_replay_attempts_per_frontier
                    ),
                    max_total_replays=(
                        args.max_total_replays
                        or ExplorationLimits().max_total_replays
                    ),
                    max_vlm_scan_attempts=(
                        args.max_vlm_scan_attempts
                        or ExplorationLimits().max_vlm_scan_attempts
                    ),
                    max_candidates_per_location=(
                        args.max_candidates
                        or ExplorationLimits().max_candidates_per_location
                    ),
                )
            effective_max_candidates = args.max_candidates or 5
            resume_graph = None
            resume_policy = None
            if args.resume_retry_action and args.resume_graph is None:
                raise ValueError("resume retry action requires --resume-graph")
            if args.resume_graph is not None and args.clean_output_dir:
                raise ValueError(
                    "--clean-output-dir cannot be combined with --resume-graph"
                )
            if args.resume_retry_action and args.resume_action_max_attempts < 2:
                raise ValueError(
                    "resume action max attempts must be at least 2"
                )
            if args.resume_graph is not None:
                resume_graph = load_web_kobe_graph_json(args.resume_graph)
                validate_resume_graph(resume_graph, app_name=args.app_name)
                resume_policy = ResumePolicy(
                    retry_keys=resolve_retry_keys(
                        resume_graph,
                        args.resume_retry_action,
                    ),
                    max_attempts=(
                        args.resume_action_max_attempts
                        if args.resume_retry_action
                        else 2
                    ),
                )
            if args.clean_output_dir:
                _clean_output_dir_for(
                    [
                        args.output,
                        args.stagehand_trace,
                        args.screenshot_dir,
                        args.embedding_path,
                    ]
                )
            if (
                resume_graph is not None
                and args.output.resolve() != args.resume_graph.resolve()
            ):
                write_web_kobe_graph(resume_graph, args.output)
            runner_kwargs = {
                "start_url": args.url,
                "app_name": args.app_name,
                "stagehand_trace_path": args.stagehand_trace,
                "model": args.model,
                "steps": args.max_exploration_steps,
                "headless": not args.headed,
                "screenshot_dir": args.screenshot_dir,
                "embedding_path": args.embedding_path,
                "use_state_embeddings": args.state_embeddings,
                "embedding_model": args.embedding_model,
                "embedding_dimension": args.embedding_dimension,
                "site_purpose": args.site_purpose,
                "business_profile": args.business_profile,
                "use_openai_visual_delta": args.openai_visual_delta,
                "visual_delta_model": args.visual_delta_model,
                "action_outcome_model": args.action_outcome_model,
                "stagehand_execution_mode": args.stagehand_execution_mode,
                "max_candidates": effective_max_candidates,
                "frontier_replay": args.frontier_replay or resume_graph is not None,
                "resume_graph": resume_graph,
                "resume_policy": resume_policy,
            }
            if args.viewport_width != 1440:
                runner_kwargs["viewport_width"] = args.viewport_width
            if args.viewport_height != 1000:
                runner_kwargs["viewport_height"] = args.viewport_height
            if budget_selected:
                runner_kwargs.update(
                    {
                        "limits": limits,
                    }
                )
            if args.allow_test_site_final_order:
                runner_kwargs["allow_test_site_final_order"] = True
            if args.vlm_request_timeout_seconds is not None:
                runner_kwargs["vlm_request_timeout_seconds"] = (
                    args.vlm_request_timeout_seconds
                )
            if args.stagehand_action_timeout_seconds is not None:
                runner_kwargs["stagehand_action_timeout_seconds"] = (
                    args.stagehand_action_timeout_seconds
                )
            output_path = asyncio.run(
                run_stagehand_exploration(
                    args.output,
                    **runner_kwargs,
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
