from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandObservedAction,
    StagehandStepTrace,
    stagehand_action_to_browser_action,
    stagehand_trace_metadata,
)


def test_stagehand_action_to_browser_action_uses_method_selector_and_description():
    action = StagehandObservedAction(
        description="Click the Login button",
        method="click",
        selector="#login-button",
        arguments=[],
        raw={"backendNodeId": 123},
    )

    browser_action = stagehand_action_to_browser_action(action, index=2)

    assert browser_action.action_kind == "click"
    assert browser_action.locator == "#login-button"
    assert browser_action.semantic_id == "stagehand_002_click_login_button"
    assert browser_action.description == "Click the Login button"
    assert browser_action.input_values == {}


def test_stagehand_action_to_browser_action_maps_fill_argument_to_selector_value():
    action = StagehandObservedAction(
        description="Fill username",
        method="fill",
        selector="#user-name",
        arguments=["standard_user"],
        raw={},
    )

    browser_action = stagehand_action_to_browser_action(action, index=0)

    assert browser_action.action_kind == "fill"
    assert browser_action.input_values == {"#user-name": "standard_user"}


def test_stagehand_trace_metadata_preserves_raw_action_and_result():
    trace = StagehandStepTrace(
        instruction="continue toward checkout overview",
        observed_action=StagehandObservedAction(
            description="Click checkout",
            method="click",
            selector="#checkout",
            arguments=[],
            raw={"backendNodeId": 99},
        ),
        act_result=StagehandActResult(
            success=True,
            message="Clicked checkout",
            action_description="Clicked button with text Checkout",
            raw={"actionId": "act_123"},
        ),
    )

    metadata = stagehand_trace_metadata(trace)

    assert metadata["action_source"] == "stagehand"
    assert metadata["stagehand_instruction"] == "continue toward checkout overview"
    assert metadata["stagehand_method"] == "click"
    assert metadata["stagehand_selector"] == "#checkout"
    assert metadata["stagehand_arguments"] == []
    assert metadata["stagehand_act_result"]["success"] is True
    assert metadata["stagehand_observed_action"]["backendNodeId"] == 99
