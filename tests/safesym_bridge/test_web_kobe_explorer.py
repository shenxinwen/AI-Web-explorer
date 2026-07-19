import pytest

from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmActionSelectionResult,
    LlmActionSelectionTrace,
)
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeAdapter:
    app_name = "fake"

    def __init__(self):
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": False},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_nonempty": True},
            ),
        ]
        self.executed = []

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "add_to_cart_product",
                "description": "Add to cart",
                "locator": "button.add",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


class RepeatedStateAdapter:
    app_name = "fake"

    def __init__(self):
        self.executed = []

    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_count": 0},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "first_action",
                "description": "First action",
                "locator": "#first",
                "action_kind": "click",
                "explored": False,
            },
            {
                "semantic_id": "second_action",
                "description": "Second action",
                "locator": "#second",
                "action_kind": "click",
                "input_values": {"#name": "Alice"},
                "explored": False,
            },
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_records_self_loop_delta():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.total_steps_completed == 1
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.source_node_id.startswith("listing__")
    assert edge.target_node_id.startswith("listing__")
    assert edge.source_node_id != edge.target_node_id
    assert edge.action.semantic_id == "add_to_cart_product"
    assert edge.schema_delta == {"cart_nonempty": {"before": False, "after": True}}
    assert edge.observed_delta[0].field == "cart_nonempty"


@pytest.mark.anyio
async def test_explore_one_step_records_profile_verified_planning_delta():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.planning_delta is not None
    assert edge.planning_delta.verified_added_facts == ["cart_nonempty"]


@pytest.mark.anyio
async def test_explore_one_step_preserves_initial_start_node_across_steps():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    first_graph = await explorer.explore_one_step()
    second_graph = await explorer.explore_one_step()

    assert second_graph.start_node_id == first_graph.edges[0].source_node_id


@pytest.mark.anyio
async def test_explore_one_step_skips_previously_explored_self_loop_action():
    adapter = RepeatedStateAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    assert [action.semantic_id for action in adapter.executed] == [
        "first_action",
        "second_action",
    ]
    assert adapter.executed[1].input_values == {"#name": "Alice"}
    assert [edge.action.semantic_id for edge in graph.edges] == [
        "first_action",
        "second_action",
    ]


class FailingDiagnosticAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_error = None

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_error = "locator_not_visible"
        return False


@pytest.mark.anyio
async def test_explore_one_step_records_backend_execution_error():
    explorer = WebKobeExplorer(
        adapter=FailingDiagnosticAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "failed_execution"
    assert edge.execution_trace.error == "locator_not_visible"


class StagehandMetadataAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_metadata = {}

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_metadata = {
            "action_source": "stagehand",
            "stagehand_selector": action.locator,
        }
        return True


@pytest.mark.anyio
async def test_explore_one_step_preserves_backend_execution_metadata():
    explorer = WebKobeExplorer(
        adapter=StagehandMetadataAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.edges[0].execution_trace.metadata == {
        "action_source": "stagehand",
        "stagehand_selector": "button.add",
    }


class ScreenshotAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.captured_labels = []

    async def capture_screenshot(self, label: str):
        self.captured_labels.append(label)
        return f"outputs/{label}.png"


@pytest.mark.anyio
async def test_explore_one_step_records_optional_before_after_screenshots():
    adapter = ScreenshotAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        capture_screenshots=True,
    )

    graph = await explorer.explore_one_step()

    metadata = graph.edges[0].execution_trace.metadata
    assert adapter.captured_labels == ["before_0001", "after_0001"]
    assert metadata["before_screenshot_path"] == "outputs/before_0001.png"
    assert metadata["after_screenshot_path"] == "outputs/after_0001.png"


@pytest.mark.anyio
async def test_explore_one_step_records_visual_delta_candidates_without_verifying_them():
    adapter = ScreenshotAdapter()
    provider_calls = []

    def visual_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        provider_calls.append((before_screenshot_path, after_screenshot_path))
        return (
            '{"candidate_added_facts":["order_place_pending_sensitive"],'
            '"candidate_removed_facts":[],'
            '"evidence":["final confirmation control appears visible"],'
            '"confidence":0.7}'
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert provider_calls == [("outputs/before_0001.png", "outputs/after_0001.png")]
    assert edge.planning_delta.candidate_added_facts == [
        "order_place_pending_sensitive",
        "cart_nonempty",
    ]
    assert edge.planning_delta.verified_added_facts == ["cart_nonempty"]
    assert edge.execution_trace.metadata["visual_delta_trace"]["status"] == "summarized"


class TypedFactsAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.fact_sets = [
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=0,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=3,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
        ]

    async def observe_state(self):
        self.last_state_facts = self.fact_sets[min(len(self.executed), 1)]
        return await super().observe_state()


@pytest.mark.anyio
async def test_explore_one_step_uses_typed_delta_when_adapter_exposes_facts():
    explorer = WebKobeExplorer(
        adapter=TypedFactsAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.edges[0].observed_delta[0].field == "result_count"
    assert graph.edges[0].observed_delta[0].delta_type == "numeric_changed"
    assert graph.edges[0].observed_delta[0].evidence[0].selector == "#result-count"


class NoChangeAdapter(FakeAdapter):
    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_nonempty": False},
        )


@pytest.mark.anyio
async def test_explore_one_step_marks_success_without_delta_as_no_observed_change():
    explorer = WebKobeExplorer(
        adapter=NoChangeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "no_observed_change"
    assert edge.execution_trace.success is True
    assert edge.observed_delta == []


class NavigationOnlyAdapter:
    app_name = "fake"

    def __init__(self):
        self.executed = []

    async def observe_state(self):
        if not self.executed:
            return StateSnapshot(
                page_id="inventory",
                url="https://example.test/inventory",
                title="Inventory",
                signature={"cart_count": 1},
            )
        return StateSnapshot(
            page_id="cart",
            url="https://example.test/cart",
            title="Cart",
            signature={"cart_count": 1},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "cart_open",
                "description": "Open cart",
                "locator": ".cart",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_marks_navigation_without_schema_delta_as_success():
    explorer = WebKobeExplorer(
        adapter=NavigationOnlyAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.action.semantic_id == "cart_open"
    assert edge.source_node_id.startswith("inventory__")
    assert edge.target_node_id.startswith("cart__")
    assert edge.schema_delta is None
    assert edge.observed_delta == []
    assert edge.status == "succeeded_with_navigation"


class CartBeforeProductAdapter:
    app_name = "saucedemo"

    def __init__(self):
        self.executed = []

    async def observe_state(self):
        return StateSnapshot(
            page_id="inventory",
            url="https://www.saucedemo.com/inventory.html",
            title="Swag Labs",
            signature={"cart_count": len(self.executed), "is_logged_in": True},
        )

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "cart_open",
                "description": "Click the shopping cart link",
                "locator": ".shopping_cart_link",
                "action_kind": "click",
                "input_values": {},
                "explored": False,
                "metadata": {"data-action": "open-cart"},
            },
            {
                "semantic_id": "product_add_to_cart",
                "description": "Click Add to cart",
                "locator": '[data-test="add-to-cart-sauce-labs-backpack"]',
                "action_kind": "click",
                "input_values": {},
                "explored": False,
            },
        ]

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explore_one_step_can_use_selector_to_choose_goal_relevant_action():
    adapter = CartBeforeProductAdapter()
    seen_requests = []

    def selector(request):
        seen_requests.append(request)
        selected = next(
            action
            for action in request.candidate_actions
            if action.semantic_id == "product_add_to_cart"
        )
        return LlmActionSelectionResult(
            selected_action=selected,
            trace=LlmActionSelectionTrace(
                goal=request.goal,
                state={"page_id": request.state.page_id},
                candidate_actions=[
                    {"id": action.semantic_id} for action in request.candidate_actions
                ],
                prompt="fake prompt",
                raw_response='{"selected_action_id":"product_add_to_cart"}',
                llm_response={"selected_action_id": "product_add_to_cart"},
                status="selected",
            ),
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="saucedemo"),
        goal="Complete a checkout order.",
        action_selector=selector,
    )

    graph = await explorer.explore_one_step()

    assert seen_requests[0].goal == "Complete a checkout order."
    assert [action.semantic_id for action in seen_requests[0].candidate_actions] == [
        "cart_open",
        "product_add_to_cart",
    ]
    assert adapter.executed[0].semantic_id == "product_add_to_cart"
    assert graph.edges[0].action.semantic_id == "product_add_to_cart"
    assert explorer.selection_traces[0]["status"] == "selected"
