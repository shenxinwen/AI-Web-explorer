from ai_web_explorer.safesym_bridge.fsm_exporter import build_fsm
from ai_web_explorer.safesym_bridge.models import (
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions
from ai_web_explorer.safesym_bridge.validator import (
    validate_fsm,
    validate_with_safesym_loader,
)


def test_validate_saucedemo_mvp_fsm_passes():
    fsm = build_fsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        transitions=build_saucedemo_mvp_transitions(),
    )

    result = validate_fsm(fsm)

    assert result.ok is True
    assert result.errors == []


def test_validate_fsm_reports_broken_action_target():
    fsm = SafeSymFsm(
        app="saucedemo",
        initial_page_id="login",
        terminal_pages=["checkout_complete"],
        pages=[
            SafeSymPage(
                id="login",
                signature_schema={"$.username_filled": "boolean"},
                actions=[
                    SafeSymAction(
                        id="login_submit",
                        name="login_submit",
                        from_page="login",
                        to_page="missing_page",
                        is_navigation=True,
                        preconditions=[],
                        effects=[],
                    )
                ],
            )
        ],
    )

    result = validate_fsm(fsm)

    assert result.ok is False
    assert "action login_submit points to unknown to page missing_page" in result.errors


def test_validate_with_safesym_loader_reports_missing_root(tmp_path):
    fsm_path = tmp_path / "fsm.json"
    fsm_path.write_text("{}", encoding="utf-8")

    result = validate_with_safesym_loader(
        fsm_path=str(fsm_path),
        safesym_root=str(tmp_path / "missing_safesym"),
    )

    assert result.ok is False
    assert result.errors == ["SafeSym root does not exist"]
