from ai_web_explorer import loop, webstate


class RecordingCollector:
    def __init__(self):
        self.events = []

    def on_state_observed(self, **kwargs):
        self.events.append(("state", kwargs["web_state"].title))

    def on_transition(self, **kwargs):
        self.events.append(
            (
                "transition",
                kwargs["source_state"].title,
                kwargs["action"].description,
                kwargs["target_state"].title,
            )
        )

    def on_action_selected(self, **kwargs):
        self.events.append(("selected", kwargs["action"].description))

    def on_action_executed(self, **kwargs):
        self.events.append(("executed", kwargs["action"].description, kwargs["success"]))


class FakeDescriber:
    def __init__(self, titles):
        self.titles = list(titles)

    def is_loading(self):
        return False

    def get_title(self, confirm, store_title):
        return self.titles.pop(0)

    def get_title_embedding(self, title):
        return []

    def get_description(self):
        return []

    def get_actions(self, title, description):
        return [
            webstate.Action(
                description=f"Go from {title}",
                part=0,
                priority=10,
            )
        ]


class FakeExecutor:
    def execute(self, action):
        return True, []


class FakePage:
    url = "https://example.test/start"

    def title(self):
        return "Browser title"

    def locator(self, selector):
        class EmptyLocator:
            first = None

            def count(self):
                return 0

        locator = EmptyLocator()
        locator.first = locator
        return locator


def _make_loop(collector):
    explore_loop = object.__new__(loop.ExploreLoop)
    explore_loop._domain = "example.test"
    explore_loop._url = "https://example.test/start"
    explore_loop._openai_client = None
    explore_loop._config = loop.LoopConfig(iterations=1)
    explore_loop._config.collector = collector
    explore_loop._webstates = []
    explore_loop._webstate_current = None
    explore_loop._action_current = None
    explore_loop._page = FakePage()
    explore_loop._describer = FakeDescriber(["Start", "Next"])
    explore_loop._executor = FakeExecutor()
    return explore_loop


def test_explore_loop_emits_collector_events_for_state_action_and_transition():
    collector = RecordingCollector()
    explore_loop = _make_loop(collector)

    explore_loop._explore()
    explore_loop._explore()

    assert collector.events == [
        ("state", "Start"),
        ("selected", "Go from Start"),
        ("executed", "Go from Start", True),
        ("state", "Next"),
        ("transition", "Start", "Go from Start", "Next"),
        ("selected", "Go from Next"),
        ("executed", "Go from Next", True),
    ]
