"""Command-line entry points for exploration and knowledge admission."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from vera.admission import build_admitted_knowledge
from vera.grounded_web.location_exploration import ExplorationLimits
from vera.grounded_web.resume import ResumePolicy, validate_resume_graph
from vera.runtime.browser_runner import run_stagehand_exploration
from vera.runtime.graph_loader import load_web_kobe_graph_json

_CONFIG_KEYS = {
    "steps", "max_candidates", "limits", "stagehand_execution_mode",
    "exploration_condition", "random_seed", "use_openai_visual_delta",
    "use_openai_risk_detection", "visual_delta_model", "action_outcome_model",
    "risk_detection_model", "model", "business_profile", "viewport_width",
    "viewport_height", "allow_test_site_final_order", "vlm_request_timeout_seconds",
    "stagehand_action_timeout_seconds",
}


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    unknown = set(config) - _CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown configuration keys: {', '.join(sorted(unknown))}")
    limits = config.get("limits", {})
    if not isinstance(limits, dict) or set(limits) - ExplorationLimits().to_dict().keys():
        raise ValueError("invalid exploration limits")
    for key, value in limits.items():
        if type(value) is not int or value < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("steps", "max_candidates", "viewport_width", "viewport_height"):
        if key in config and (type(config[key]) is not int or config[key] < 1):
            raise ValueError(f"{key} must be a positive integer")
    for key in ("use_openai_visual_delta", "use_openai_risk_detection", "allow_test_site_final_order"):
        if key in config and type(config[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    config["limits"] = ExplorationLimits.from_dict(limits)
    return config


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VERA: evidence-grounded web exploration")
    commands = parser.add_subparsers(dest="command", required=True)
    explore = commands.add_parser("explore", help="Explore an application and record evidence")
    explore.add_argument("--url", required=True)
    explore.add_argument("--config", type=Path, required=True)
    explore.add_argument("--output", type=Path, required=True, help="Run directory")
    explore.add_argument("--app-name", default="web")
    explore.add_argument("--site-purpose", default=None)
    explore.add_argument("--headed", action="store_true")
    explore.add_argument("--resume", action="store_true", help="Resume the graph in the run directory")

    admit = commands.add_parser("admit", help="Build the evidence-supported knowledge view")
    admit.add_argument("--graph", type=Path, required=True)
    admit.add_argument("--evidence", type=Path, default=None)
    admit.add_argument("--artifact-root", type=Path, default=Path.cwd())
    admit.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "explore":
            config = load_config(args.config)
            graph_path = args.output / "graph.json"
            if args.resume:
                graph = load_web_kobe_graph_json(graph_path)
                validate_resume_graph(graph, app_name=args.app_name)
                config.update(resume_graph=graph, resume_policy=ResumePolicy())
            elif args.output.exists() and any(args.output.iterdir()):
                raise ValueError("run directory is not empty; use a new directory or --resume")
            asyncio.run(run_stagehand_exploration(
                graph_path, start_url=args.url, app_name=args.app_name,
                stagehand_trace_path=args.output / "execution_trace.json",
                screenshot_dir=args.output / "screenshots",
                headless=not args.headed, site_purpose=args.site_purpose,
                **config,
            ))
        elif args.command == "admit":
            if args.output.resolve() in {
                args.graph.resolve(),
                (args.evidence or args.graph.with_name("graph_evidence.json")).resolve(),
            }:
                raise ValueError("knowledge output must differ from the source artifacts")
            _write_json(args.output, build_admitted_knowledge(
                args.graph, evidence_path=args.evidence, artifact_root=args.artifact_root,
            ))
    except (ValueError, OSError) as error:
        parser.exit(1, f"ERROR: {error}\n")
    print(f"Wrote output to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
