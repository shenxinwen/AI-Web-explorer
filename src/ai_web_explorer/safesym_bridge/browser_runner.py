from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import ObservedTransition
from ai_web_explorer.safesym_bridge.validator import validate_fsm


def write_observed_fsm(
    transitions: list[ObservedTransition],
    output_path: Path,
) -> Path:
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=transitions,
    )
    validation = validate_fsm(fsm)
    if not validation.ok:
        joined = "; ".join(validation.errors)
        raise ValueError(f"Observed FSM failed validation: {joined}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fsm.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path
