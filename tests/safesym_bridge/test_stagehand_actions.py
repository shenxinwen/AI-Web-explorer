from ai_web_explorer.grounded_web.stagehand_actions import (
    StagehandActResult,
    StagehandStepTrace,
    stagehand_trace_metadata,
)


def test_stagehand_trace_metadata_preserves_instruction_and_result():
    trace = StagehandStepTrace(
        instruction="continue toward checkout overview",
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
    assert metadata["stagehand_act_result"]["success"] is True
    assert metadata["stagehand_observed_action"] is None
