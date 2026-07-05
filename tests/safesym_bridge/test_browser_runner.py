import json
import os

import pytest

from ai_web_explorer.safesym_bridge.browser_runner import (
    run_saucedemo_observed_flow,
    write_observed_graph,
    write_observed_fsm,
)
from ai_web_explorer.safesym_bridge.task_spec import build_saucedemo_mvp_transitions


@pytest.fixture
def anyio_backend():
    return "asyncio"


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


def test_write_observed_graph_writes_graph_json(tmp_path):
    output_path = tmp_path / "saucedemo_observed_graph.json"

    result_path = write_observed_graph(
        transitions=build_saucedemo_mvp_transitions(),
        output_path=output_path,
    )

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert any(node["id"] == "inventory" for node in data["nodes"])
    assert any(
        edge["semantic_action"] == "order_place_confirm" for edge in data["edges"]
    )


def test_run_saucedemo_observed_flow_is_async_callable():
    assert callable(run_saucedemo_observed_flow)


@pytest.mark.skipif(
    os.getenv("RUN_SAUCEDEMO_BROWSER_TEST") != "1",
    reason="Set RUN_SAUCEDEMO_BROWSER_TEST=1 to run the real browser smoke test.",
)
@pytest.mark.anyio
async def test_run_saucedemo_observed_flow_smoke(tmp_path):
    output_path = tmp_path / "saucedemo_observed_fsm.json"

    result_path = await run_saucedemo_observed_flow(output_path)

    assert result_path == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    actions = [action for page in data["pages"] for action in page["actions"]]
    assert any(action["id"] == "order_place_confirm" for action in actions)
