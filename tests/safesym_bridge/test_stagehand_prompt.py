from ai_web_explorer.grounded_web.stagehand_prompt import (
    build_generic_stagehand_exploration_goal,
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
