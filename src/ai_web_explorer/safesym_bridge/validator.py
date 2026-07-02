from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from ai_web_explorer.safesym_bridge.models import SafeSymFsm


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]


def validate_fsm(fsm: SafeSymFsm) -> ValidationResult:
    errors: list[str] = []

    if not fsm.app:
        errors.append("meta.app is required")
    if not fsm.initial_page_id:
        errors.append("meta.initial_page_id is required")
    if not fsm.pages:
        errors.append("pages must not be empty")

    page_ids = {page.id for page in fsm.pages}
    if fsm.initial_page_id and fsm.initial_page_id not in page_ids:
        errors.append(f"initial_page_id {fsm.initial_page_id} is not a page")

    all_action_ids: list[str] = []
    known_schema_paths = {
        path for page in fsm.pages for path in page.signature_schema
    }

    for page in fsm.pages:
        if not page.id:
            errors.append("page id is required")
        if not page.signature_schema:
            errors.append(f"page {page.id} signature_schema must not be empty")

        for action in page.actions:
            all_action_ids.append(action.id)
            if not action.id:
                errors.append(f"action on page {page.id} is missing id")
            if not action.name:
                errors.append(f"action {action.id} is missing name")
            if action.from_page not in page_ids:
                errors.append(
                    f"action {action.id} points to unknown from page {action.from_page}"
                )
            if action.to_page not in page_ids:
                errors.append(
                    f"action {action.id} points to unknown to page {action.to_page}"
                )
            for effect in action.effects:
                path = str(effect.get("path", ""))
                if path not in known_schema_paths:
                    errors.append(
                        f"action {action.id} effect path {path} is not in signature_schema"
                    )

    if "order_place_confirm" not in all_action_ids:
        errors.append("required action order_place_confirm is missing")

    return ValidationResult(ok=not errors, errors=errors)


def validate_with_safesym_loader(
    fsm_path: str,
    safesym_root: str,
) -> ValidationResult:
    root = Path(safesym_root)
    if not root.exists():
        return ValidationResult(ok=False, errors=["SafeSym root does not exist"])

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        loader = importlib.import_module("safeww.fsm.loader")
    except Exception as exc:
        return ValidationResult(
            ok=False,
            errors=[f"could not import SafeSym loader: {exc}"],
        )

    try:
        if hasattr(loader, "load_fsm"):
            loader.load_fsm(fsm_path)
        elif hasattr(loader, "FsmDocument") and hasattr(loader.FsmDocument, "from_path"):
            loader.FsmDocument.from_path(fsm_path)
        else:
            return ValidationResult(
                ok=False,
                errors=["SafeSym loader has no load_fsm or FsmDocument.from_path"],
            )
    except Exception as exc:
        return ValidationResult(
            ok=False,
            errors=[f"SafeSym loader rejected FSM: {exc}"],
        )

    return ValidationResult(ok=True, errors=[])
