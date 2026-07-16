import json

from ai_web_explorer.safesym_bridge.openai_selector_smoke import (
    build_saucedemo_inventory_selection_request,
    write_openai_selector_smoke,
)


def test_build_saucedemo_inventory_selection_request_models_current_problem():
    request = build_saucedemo_inventory_selection_request()

    assert request.goal == "Complete a SauceDemo checkout order."
    assert request.state.page_id == "inventory"
    assert request.state.signature["cart_count"] == 0
    assert [action.semantic_id for action in request.candidate_actions] == [
        "product_add_to_cart",
        "cart_open",
    ]


def test_write_openai_selector_smoke_writes_pass_report(tmp_path):
    output_path = tmp_path / "openai_selector_smoke.json"

    result = write_openai_selector_smoke(
        output_path,
        provider=lambda prompt: (
            '{"selected_action_id":"product_add_to_cart",'
            '"confidence":0.92,'
            '"reason":"Cart is empty, so add a product before opening cart."}'
        ),
    )

    assert result.report_path == output_path
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["expected_action_id"] == "product_add_to_cart"
    assert report["selected_action_id"] == "product_add_to_cart"
    assert report["selection_ready"] is True
    assert report["trace"]["status"] == "selected"


def test_write_openai_selector_smoke_records_wrong_choice(tmp_path):
    output_path = tmp_path / "openai_selector_smoke.json"

    result = write_openai_selector_smoke(
        output_path,
        provider=lambda prompt: (
            '{"selected_action_id":"cart_open",'
            '"confidence":0.61,'
            '"reason":"Open cart."}'
        ),
    )

    assert result.report.selection_ready is False
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["selected_action_id"] == "cart_open"
    assert report["failure_reason"] == "wrong_action_selected"
