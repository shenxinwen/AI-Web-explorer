from ai_web_explorer.grounded_web.stagehand_prompt import (
    build_generic_stagehand_exploration_goal,
    build_site_input_context,
)


def test_generic_stagehand_exploration_goal_is_site_agnostic():
    goal = build_generic_stagehand_exploration_goal(site_purpose="demo store")

    assert "demo store" in goal
    assert "execute exactly one selected business action" in goal.lower()
    assert "Avoid low-value footer, legal, social, theme, and language actions" in goal
    assert "checkout" not in goal.lower()
    assert "payment" not in goal.lower()


def test_generic_stagehand_goal_can_enable_controlled_completion_boundary():
    goal = build_generic_stagehand_exploration_goal(
        site_purpose="controlled shopping test",
        allow_final_order=True,
    )

    assert "final confirmation is allowed" in goal
    assert "fictional values" in goal


def test_realworld_site_input_context_uses_valid_isolated_registration_values():
    context = build_site_input_context("realworld", run_token="abc123")

    assert "awe_abc123" in context
    assert "awe_abc123@example.com" in context
    assert "Test-password-1" in context


def test_default_site_input_context_does_not_affect_other_sites():
    assert build_site_input_context(None, run_token="ignored") is None
