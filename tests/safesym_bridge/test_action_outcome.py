import json

import pytest

from ai_web_explorer.grounded_web.action_outcome import (
    ActionOutcomeResult,
    build_action_outcome_prompt,
    parse_action_outcome,
    semantic_observation_from_action_outcome,
    summarize_action_outcome,
)
from ai_web_explorer.grounded_web.openai_visual_delta import (
    DEFAULT_OPENAI_ACTION_OUTCOME_MODEL,
    create_openai_visual_delta_provider_from_env,
    create_openai_action_outcome_provider_from_env,
)


def test_action_outcome_parser_accepts_minimal_success_contract():
    result = parse_action_outcome(
        {
            "outcome": "success",
            "location_change": False,
            "evidence": "The same form remains visible with the value entered.",
        }
    )

    assert isinstance(result, ActionOutcomeResult)
    assert result.outcome == "success"
    assert result.location_change is False
    assert result.evidence == (
        "The same form remains visible with the value entered.",
    )


@pytest.mark.parametrize("outcome", ["failed", "uncertain"])
def test_action_outcome_parser_accepts_failure_and_uncertain(outcome):
    result = parse_action_outcome(
        {"outcome": outcome, "location_change": False, "evidence": []}
    )

    assert result.outcome == outcome


@pytest.mark.parametrize(
    "payload",
    [
        {"outcome": "success", "location_change": "false", "evidence": []},
        {"outcome": "unknown", "location_change": False, "evidence": []},
        {"outcome": "success", "location_change": False},
        {
            "outcome": "success",
            "location_change": False,
            "evidence": [],
            "completion_facts": ["should_not_be_here"],
        },
        [],
    ],
)
def test_action_outcome_parser_rejects_invalid_or_planner_fields(payload):
    with pytest.raises(ValueError):
        parse_action_outcome(payload)


def test_action_outcome_prompt_has_exactly_three_response_fields():
    prompt = build_action_outcome_prompt("Fill the visible form.")
    payload = json.loads(prompt)

    assert set(payload["output_schema"]) == {
        "outcome",
        "location_change",
        "evidence",
    }
    assert "same active interaction surface" in payload["instruction"].lower()
    assert "filtering" in payload["instruction"].lower()
    assert "search" in payload["instruction"].lower()
    assert "sorting" in payload["instruction"].lower()
    assert "pagination" in payload["instruction"].lower()
    assert "brief toast" in payload["instruction"].lower()
    assert "completion_facts" not in prompt
    assert "semantic_profile_context" not in prompt


def test_action_outcome_prompt_contains_domain_neutral_few_shots():
    payload = json.loads(build_action_outcome_prompt("Apply a visible filter"))

    assert set(payload) == {
        "instruction",
        "action_description",
        "output_schema",
        "few_shot_examples",
    }
    assert set(payload["output_schema"]) == {
        "outcome",
        "location_change",
        "evidence",
    }
    assert len(payload["few_shot_examples"]) == 5
    instruction = payload["instruction"].lower()
    assert "prefer a definite success or failed judgment" in instruction
    assert "same main heading, controls, and page layout" in instruction
    assert "location_change must be false" in instruction
    examples_text = json.dumps(payload["few_shot_examples"], ensure_ascii=False)
    for token in ("filter", "sorting", "export", "form", "detail"):
        assert token in examples_text.lower()
    assert '"outcome": "uncertain"' not in examples_text


def test_action_outcome_summary_preserves_raw_trace_and_errors():
    result = summarize_action_outcome(
        before_screenshot_path="before.png",
        after_screenshot_path="after.png",
        action_description="Fill the visible form.",
        provider=lambda prompt, **kwargs: (
            '{"outcome":"success","location_change":false,"evidence":[]}'
        ),
    )

    assert result.trace.status == "summarized"
    assert json.loads(result.trace.raw_response)["outcome"] == "success"
    assert result.trace.error_type is None


def test_success_action_outcome_projects_to_coarse_observation_and_keeps_location_change():
    observation = semantic_observation_from_action_outcome(
        parse_action_outcome(
            {
                "outcome": "success",
                "location_change": True,
                "evidence": ["A new interface is active."],
            }
        ),
        source_location="checkout",
        target_location_hint="checkout",
        target_node_id="checkout_after_open",
    )

    assert observation is not None
    assert observation.source_location == "checkout"
    assert observation.target_location == "checkout_after_open"
    assert observation.action_role == "navigation"
    assert observation.completion_facts == []


@pytest.mark.parametrize("outcome", ["failed", "uncertain"])
def test_non_success_action_outcome_has_no_coarse_observation(outcome):
    result = parse_action_outcome(
        {"outcome": outcome, "location_change": False, "evidence": []}
    )
    assert (
        semantic_observation_from_action_outcome(
            result,
            source_location="checkout",
            target_location_hint="checkout",
            target_node_id="after",
        )
        is None
    )


def test_openai_visual_provider_defaults_to_mini_and_honors_explicit_model():
    class FakeClient:
        pass

    def factory(**kwargs):
        return FakeClient()

    provider = create_openai_visual_delta_provider_from_env(
        openai_factory=factory,
        load_dotenv=lambda: None,
        environ={"OPENAI_API_KEY": "test-key"},
    )
    explicit = create_openai_visual_delta_provider_from_env(
        model="gpt-4o",
        openai_factory=factory,
        load_dotenv=lambda: None,
        environ={"OPENAI_API_KEY": "test-key"},
    )

    assert provider.model == "gpt-4o-mini"
    assert explicit.model == "gpt-4o"


def test_openai_action_outcome_provider_has_independent_model_precedence():
    class FakeClient:
        pass

    def factory(**kwargs):
        return FakeClient()

    common = {
        "openai_factory": factory,
        "load_dotenv": lambda: None,
        "environ": {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_ACTION_OUTCOME_MODEL": "env-outcome-model",
        },
    }
    default = create_openai_action_outcome_provider_from_env(
        **{**common, "environ": {"OPENAI_API_KEY": "test-key"}}
    )
    from_env = create_openai_action_outcome_provider_from_env(**common)
    explicit = create_openai_action_outcome_provider_from_env(
        model="explicit-outcome-model", **common
    )

    assert DEFAULT_OPENAI_ACTION_OUTCOME_MODEL == "gpt-4o"
    assert default.model == "gpt-4o"
    assert from_env.model == "env-outcome-model"
    assert explicit.model == "explicit-outcome-model"
