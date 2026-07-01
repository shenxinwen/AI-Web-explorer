import json

from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_observed_flow,
    write_observed_fsm,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


def test_write_observed_fsm_writes_valid_json(tmp_path):
    output_path = tmp_path / "observed.json"

    result_path = write_observed_fsm(
        transitions=build_saucedemo_mvp_transitions(),
        output_path=output_path,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    actions = [action for page in data["pages"] for action in page["actions"]]
    assert any(action["id"] == "order_place_confirm" for action in actions)


def test_run_saucedemo_observed_flow_is_async_callable():
    assert callable(run_saucedemo_observed_flow)
