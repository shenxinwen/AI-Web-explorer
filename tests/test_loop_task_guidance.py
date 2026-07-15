from ai_web_explorer import loop, webstate


def test_task_guided_action_selection_prefers_matching_action():
    explore_loop = object.__new__(loop.ExploreLoop)
    explore_loop._config = loop.LoopConfig(task="add a product to cart")
    state = webstate.WebState(
        title="Local shop",
        title_embedding=[],
        urls=["https://example.test"],
        description=[],
        actions=[
            webstate.Action(
                description="Click on the button to view the shopping cart.",
                part=0,
                priority=10,
            ),
            webstate.Action(
                description="Click on the button to add Sample Product A to the cart.",
                part=0,
                priority=10,
            ),
        ],
        transitions=[],
    )

    selected = explore_loop._select_action(state)

    assert selected is state.actions[1]


def test_task_guided_action_selection_falls_back_when_no_task():
    explore_loop = object.__new__(loop.ExploreLoop)
    explore_loop._config = loop.LoopConfig()
    action = webstate.Action(
        description="Click on the button to view the shopping cart.",
        part=0,
        priority=11,
    )
    state = webstate.WebState(
        title="Local shop",
        title_embedding=[],
        urls=["https://example.test"],
        description=[],
        actions=[action],
        transitions=[],
    )

    assert explore_loop._select_action(state) is action
