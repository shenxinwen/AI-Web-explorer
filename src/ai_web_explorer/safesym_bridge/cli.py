from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import (
    run_stagehand_exploration,
    write_web_kobe_graph,
)
from ai_web_explorer.safesym_bridge.graph_loader import (
    load_web_kobe_graph_json,
)
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
)
from ai_web_explorer.grounded_web.semantic_planning import (
    build_semantic_planning_graph,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explore web pages into Web-KOBE graphs and project them to "
            "SafeSym/PDDL-facing artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="mode")

    semantic_pddl_parser = subparsers.add_parser(
        "web-kobe-semantic-pddl",
        help="Project an explored graph directly to Minimal Semantic PDDL.",
    )
    semantic_pddl_parser.add_argument("--graph", type=Path, required=True)
    semantic_pddl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/web_kobe_semantic_pddl"),
    )
    semantic_pddl_parser.add_argument("--goal-location", default=None)
    semantic_pddl_parser.add_argument("--goal-fact", action="append", default=[])
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
    stagehand_explore_parser.add_argument(
        "--disallow-final-order",
        action="store_true",
        help="Prevent the explorer from submitting a final confirmation.",
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
        "--openai-risk-detection", action="store_true"
    )
    stagehand_explore_parser.add_argument("--risk-detection-model", default=None)
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
        if args.mode == "web-kobe-semantic-pddl":
            graph = load_web_kobe_graph_json(args.graph)
            semantic_graph, semantic_report = build_semantic_planning_graph(graph)
            if not (
                semantic_graph.start_location
                and semantic_graph.locations
                and semantic_graph.actions
            ):
                raise ValueError("no_usable_semantic_actions")
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "semantic_planning_graph.json").write_text(
                json.dumps(semantic_graph.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (args.output / "semantic_projection_report.json").write_text(
                json.dumps(
                    semantic_report.to_dict(),
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            domain = compile_minimal_semantic_domain(semantic_graph)
            (args.output / "domain.pddl").write_text(domain.domain, encoding="utf-8")
            if args.goal_location is not None or args.goal_fact:
                problem = compile_minimal_semantic_problem(
                    semantic_graph,
                    goal_location=args.goal_location,
                    goal_facts=args.goal_fact,
                )
                (args.output / "problem.pddl").write_text(
                    problem.problem, encoding="utf-8"
                )
            else:
                (args.output / "problem.pddl").unlink(missing_ok=True)
            output_path = args.output
        elif args.mode == "web-kobe-safesym-smoke":
            result = write_web_kobe_safesym_smoke(
                args.task_dir,
                safesym_root=args.safesym_root,
                rules=args.rules,
                fast_downward=args.fast_downward,
            )
            output_path = result.report_path
        elif args.mode == "web-kobe-stagehand-explore":
            final_order_allowed = validate_final_order_authorization(
                start_url=args.url,
                allowed=not args.disallow_final_order,
            )
            defaults = ExplorationLimits()
            limits = ExplorationLimits(
                max_exploration_steps=(
                    args.max_exploration_steps or defaults.max_exploration_steps
                ),
                max_action_attempts_per_candidate=(
                    args.max_action_attempts_per_candidate
                    or defaults.max_action_attempts_per_candidate
                ),
                max_replay_attempts_per_frontier=(
                    args.max_replay_attempts_per_frontier
                    or defaults.max_replay_attempts_per_frontier
                ),
                max_total_replays=(
                    args.max_total_replays or defaults.max_total_replays
                ),
                max_vlm_scan_attempts=(
                    args.max_vlm_scan_attempts or defaults.max_vlm_scan_attempts
                ),
                max_candidates_per_location=(
                    args.max_candidates or defaults.max_candidates_per_location
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
                raise ValueError("resume action max attempts must be at least 2")
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
                "use_openai_risk_detection": args.openai_risk_detection,
                "risk_detection_model": args.risk_detection_model,
                "stagehand_execution_mode": args.stagehand_execution_mode,
                "max_candidates": effective_max_candidates,
                "limits": limits,
                "frontier_replay": args.frontier_replay or resume_graph is not None,
                "resume_graph": resume_graph,
                "resume_policy": resume_policy,
                "allow_test_site_final_order": final_order_allowed,
            }
            if args.viewport_width != 1440:
                runner_kwargs["viewport_width"] = args.viewport_width
            if args.viewport_height != 1000:
                runner_kwargs["viewport_height"] = args.viewport_height
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
