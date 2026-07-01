from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.browser_runner import run_saucedemo_observed_flow
from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import SafeSymFsm
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def build_saucedemo_fsm() -> SafeSymFsm:
    return build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )


def write_fixed_fsm(output_path: Path) -> Path:
    fsm = build_saucedemo_fsm()
    validation = validate_fsm(fsm)
    if not validation.ok:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Fixed FSM failed validation: {joined}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a SafeSym FSM for SauceDemo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write the generated FSM JSON. Defaults to outputs/saucedemo_fsm.json.",
    )
    subparsers = parser.add_subparsers(dest="mode")

    fixed_parser = subparsers.add_parser("fixed", help="Write the fixed SauceDemo MVP FSM.")
    fixed_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_fsm.json"),
        help="Path to write the generated FSM JSON.",
    )

    observed_parser = subparsers.add_parser(
        "observed",
        help="Run a real browser flow and write the observed SauceDemo FSM.",
    )
    observed_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_observed_fsm.json"),
        help="Path to write the generated FSM JSON.",
    )
    observed_parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window while running the observed flow.",
    )

    args = parser.parse_args(argv)

    try:
        if args.mode == "observed":
            output_path = asyncio.run(
                run_saucedemo_observed_flow(
                    args.output,
                    headless=not args.headed,
                )
            )
        else:
            output_path = write_fixed_fsm(
                args.output or Path("outputs/saucedemo_fsm.json")
            )
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Wrote SafeSym FSM to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
