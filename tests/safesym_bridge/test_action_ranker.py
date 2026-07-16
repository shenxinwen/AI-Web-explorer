from ai_web_explorer.grounded_web.action_ranker import rank_interactables


def test_rank_interactables_prefers_empty_fill_targets_over_populated_inputs():
    ranked = rank_interactables(
        [
            {
                "semantic_id": "a_name_input",
                "description": "Full name",
                "locator": "#name",
                "action_kind": "fill",
                "metadata": {"value": "Alice"},
                "explored": False,
            },
            {
                "semantic_id": "z_email_input",
                "description": "Email",
                "locator": "#email",
                "action_kind": "fill",
                "metadata": {"value": ""},
                "explored": False,
            },
        ]
    )

    assert [item["semantic_id"] for item in ranked] == [
        "z_email_input",
        "a_name_input",
    ]
