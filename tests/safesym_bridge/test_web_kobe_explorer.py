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
from ai_web_explorer.grounded_web.state_embedding import StateEmbeddingRecord
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
                signature={"cart_has_items": False},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"cart_has_items": True},
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
    assert edge.schema_delta == {"cart_has_items": {"before": False, "after": True}}
    assert edge.observed_delta[0].field == "cart_has_items"


@pytest.mark.anyio
async def test_explore_one_step_preserves_deterministic_node_naming():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    nodes_by_id = {node.node_id: node for node in graph.nodes}
    source = nodes_by_id[graph.edges[0].source_node_id]
    assert source.node_label == "listing"
    assert source.state_summary == "listing state"
    assert source.naming_provenance == {"source": "deterministic_fallback"}


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
    assert edge.planning_delta.verified_added_facts == ["cart_has_items"]


@pytest.mark.anyio
async def test_explore_one_step_propagates_planning_delta_to_target_node():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    target = nodes_by_id[edge.target_node_id]
    assert target.planning_state is not None
    assert target.planning_state.active_facts == ["cart_has_items"]
    assert edge.planning_transition is not None
    assert edge.planning_transition.pre_facts == []
    assert edge.planning_transition.added_facts == ["cart_has_items"]
    assert edge.planning_transition.post_facts == ["cart_has_items"]


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

    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_has_items": False},
        )

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


class ReportedFailureWithObservedChangeAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_error = None

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_error = "tool reported failure after changing the page"
        return False


@pytest.mark.anyio
async def test_explore_one_step_accepts_observed_change_after_backend_failure():
    explorer = WebKobeExplorer(
        adapter=ReportedFailureWithObservedChangeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "succeeded_with_observed_change"
    assert edge.execution_trace.success is True
    assert edge.execution_trace.error == "tool reported failure after changing the page"
    assert edge.execution_trace.metadata["backend_reported_success"] is False


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
        "backend_reported_success": True,
    }


class ScreenshotAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.captured_labels = []

    async def capture_screenshot(self, label: str):
        self.captured_labels.append(label)
        return f"outputs/{label}.png"


class StagehandThinkingFailureVisualChangeAdapter(ScreenshotAdapter):
    def __init__(self):
        super().__init__()
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing"},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing"},
            ),
        ]
        self.last_execution_error = None

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_error = "Thinking mode does not support this tool_choice"
        return False


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
async def test_explore_one_step_accepts_stagehand_tool_choice_error_with_visual_change():
    adapter = StagehandThinkingFailureVisualChangeAdapter()

    def visual_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"visible_change_summary":"The product now shows In cart: 1.",'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],'
            '"evidence":["product card shows In cart: 1"],'
            '"confidence":0.8}'
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
    assert edge.status == "succeeded_with_observed_change"
    assert edge.execution_trace.success is True
    assert edge.execution_trace.error == "Thinking mode does not support this tool_choice"
    assert edge.execution_trace.metadata["backend_reported_success"] is False
    assert edge.planning_transition is not None
    assert edge.planning_transition.added_facts == ["cart_has_items"]


@pytest.mark.anyio
async def test_explore_one_step_records_visual_delta_candidates_without_verifying_them():
    adapter = ScreenshotAdapter()
    provider_calls = []

    def visual_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        provider_calls.append((before_screenshot_path, after_screenshot_path))
        return (
            '{"visible_change_summary":"Final confirmation control appears.",'
            '"candidate_added_facts":["order_place_pending_sensitive"],'
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
        "cart_has_items",
    ]
    assert edge.planning_delta.verified_added_facts == ["cart_has_items"]
    assert (
        edge.execution_trace.metadata["visual_change_summary"]
        == "Final confirmation control appears."
    )
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
            signature={"cart_has_items": False},
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


@pytest.mark.anyio
async def test_explore_one_step_applies_semantic_naming_without_changing_ids():
    class NamingAdapter(FakeAdapter):
        async def list_interactables(self, state):
            return [
                {
                    "semantic_id": "stagehand_000_click_add_to_cart",
                    "description": "click Add to cart",
                    "locator": "#add",
                    "action_kind": "click",
                    "input_values": {},
                    "explored": False,
                }
            ]

        async def execute(self, action: BrowserAction):
            self.executed.append(action)
            return True

    def semantic_naming_provider(request):
        assert request.action is not None
        return {
            "node_label": "Product list",
            "state_summary": "Inventory page before adding an item.",
            "action_label": "Add product to cart",
            "canonical_action_name": "product_add_to_cart",
        }

    adapter = NamingAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="shop"),
        goal="Add a product to the cart.",
        semantic_naming_provider=semantic_naming_provider,
    )

    graph = await explorer.explore_one_step()

    assert adapter.executed[0].semantic_id == "stagehand_000_click_add_to_cart"
    assert graph.nodes[0].node_label == "product_list"
    assert graph.nodes[0].state_summary == "Inventory page before adding an item."
    assert graph.edges[0].action.semantic_id == "stagehand_000_click_add_to_cart"
    assert graph.edges[0].action.action_label == "Add product to cart"
    assert graph.edges[0].action.canonical_action_name == "product_add_to_cart"


@pytest.mark.anyio
async def test_explore_one_step_applies_transition_naming_from_visual_summary():
    adapter = ScreenshotAdapter()
    seen_requests = []

    def visual_provider(prompt, *, before_screenshot_path, after_screenshot_path):
        return (
            '{"visible_change_summary":"The page changed from a sign-in form '
            'to an account dashboard.",'
            '"candidate_added_facts":[],'
            '"candidate_removed_facts":[],'
            '"evidence":[],'
            '"confidence":0.7}'
        )

    def semantic_naming_provider(request):
        seen_requests.append(request)
        if request.naming_task == "transition":
            return {
                "action_label": "Log in",
                "canonical_action_name": "log_in",
                "confidence": 0.9,
            }
        return {}

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        goal="Complete a task on the website.",
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        semantic_naming_provider=semantic_naming_provider,
    )

    graph = await explorer.explore_one_step()

    transition_requests = [
        request for request in seen_requests if request.naming_task == "transition"
    ]
    assert len(transition_requests) == 1
    assert (
        transition_requests[0].visual_change_summary
        == "The page changed from a sign-in form to an account dashboard."
    )
    edge = graph.edges[0]
    assert edge.action.semantic_id == "add_to_cart_product"
    assert edge.action.action_label == "Log in"
    assert edge.action.canonical_action_name == "log_in"
    assert edge.action.naming_provenance == {
        "source": "llm_transition_naming",
        "confidence": 0.9,
    }


class RevisitMemoryAdapter(RepeatedStateAdapter):
    def __init__(self):
        super().__init__()
        self.exploration_contexts = []

    def set_exploration_context(self, prompt_block):
        self.exploration_contexts.append(prompt_block)


@pytest.mark.anyio
async def test_explore_one_step_builds_memory_context_for_revisited_state():
    adapter = RevisitMemoryAdapter()

    def embed(text):
        return [1.0, 0.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
        state_embedding_records=[
            StateEmbeddingRecord(
                node_id="listing__existing",
                summary_text="listing state",
                embedding=[1.0, 0.0, 0.0],
            )
        ],
    )

    await explorer.explore_one_step()
    await explorer.explore_one_step()

    assert adapter.exploration_contexts
    assert any("Exploration memory:" in item for item in adapter.exploration_contexts)
    assert explorer.state_embedding_records
