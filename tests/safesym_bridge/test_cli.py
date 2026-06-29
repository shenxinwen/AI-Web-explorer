import json

from ai_web_explorer.safesym_bridge.cli import build_saucedemo_fsm, main


def test_build_saucedemo_fsm_contains_required_order_action():
    fsm = build_saucedemo_fsm()
    data = fsm.to_dict()
    actions = [action for page in data["pages"] for action in page["actions"]]

    assert any(action["id"] == "order_place_confirm" for action in actions)


def test_main_writes_json_file(tmp_path):
    output_path = tmp_path / "saucedemo_fsm.json"

    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"
    assert data["meta"]["initial_page_id"] == "login"
    assert data["meta"]["terminal_pages"] == ["checkout_complete"]
