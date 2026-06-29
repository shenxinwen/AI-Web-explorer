from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a SafeSym FSM for SauceDemo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/saucedemo_fsm.json"),
        help="Path to write the generated FSM JSON.",
    )
    args = parser.parse_args(argv)

    fsm = build_saucedemo_fsm()
    validation = validate_fsm(fsm)
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote SafeSym FSM to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
