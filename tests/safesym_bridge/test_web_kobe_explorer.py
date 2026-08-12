import json
from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.exploration_index import ExplorationContext
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.explorer import (
    WebKobeExplorer,
    _business_action_from_affordance,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import (
    PlanningState,
    PlanningTransition,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.grounded_web.state_embedding import (
    StateEmbeddingRecord,
    StateMatch,
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


def _default_visual_provider(
    *,
    action_name: str = "add_to_cart_product",
    action_label: str = "Add to cart",
    target_hint: str = "Add to cart control",
    added_facts: list[str] | None = None,
    removed_facts: list[str] | None = None,
    meaningful_change: bool = True,
    relevance: str = "core",
):
    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return (
                '{"business_affordances":['
                f'{{"action_name":"{action_name}",'
                f'"label":"{action_label}",'
                f'"relevance_hint":"{relevance}",'
                f'"target_hint":"{target_hint}",'
                '"confidence":0.9}'
                "],"
                '"state_summary":"Business page with actionable controls."}'
            )
        added = added_facts if added_facts is not None else ["cart_has_items"]
        removed = removed_facts if removed_facts is not None else []
        return (
            '{"visible_change_summary":"Business state changed.",'
            f'"business_action_name":"{action_name}",'
            f'"business_relevance":"{relevance}",'
            f'"meaningful_change":{str(meaningful_change).lower()},'
            f'"candidate_added_facts":{added!r},'
            f'"candidate_removed_facts":{removed!r},'
            '"evidence":["visible business evidence"],'
            '"confidence":0.8}'
        ).replace("'", '"')

    return provider


def _business_affordance_response(
    action_name: str = "add_to_cart_product",
    *,
    relevance: str = "core",
) -> str:
    return (
        '{"business_affordances":['
        f'{{"action_name":"{action_name}",'
        f'"label":"{action_name.replace("_", " ").title()}",'
        f'"relevance_hint":"{relevance}",'
        f'"target_hint":"visible {action_name.replace("_", " ")} control",'
        '"confidence":0.9}'
        "],"
        '"state_summary":"Business page with actionable controls."}'
    )


def _business_explorer(
    adapter,
    *,
    business_profile=None,
    visual_delta_provider=None,
    state_embedding_provider=None,
    state_embedding_records=None,
    enable_exploration_memory: bool = False,
    goal: str = "Explore the web task.",
    attempt_checkpoint=None,
):
    if not hasattr(adapter, "capture_screenshot"):
        captured_labels = []

        async def capture_screenshot(label: str):
            captured_labels.append(label)
            return f"outputs/{label}.png"

        adapter.captured_labels = captured_labels
        adapter.capture_screenshot = capture_screenshot

    return WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        goal=goal,
        business_profile=business_profile or ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_delta_provider or _default_visual_provider(),
        state_embedding_provider=state_embedding_provider,
        state_embedding_records=state_embedding_records,
        enable_exploration_memory=enable_exploration_memory,
        attempt_checkpoint=attempt_checkpoint,
    )


def test_explorer_restore_graph_preserves_candidates_without_current_browser_pointer():
    explorer = _business_explorer(FakeAdapter())
    graph = WebKobeGraph(
        app="fake",
        start_node_id="start",
        total_steps_completed=4,
        nodes=[
            _selection_node(
                "start",
                business_affordances=[BusinessAffordance("open_item")],
            ),
            _selection_node(
                "target",
                business_affordances=[BusinessAffordance("inspect")],
            ),
        ],
        edges=[],
        meta={"resume_cursor_node_id": "target"},
    )

    explorer.restore_graph(graph)

    assert explorer.start_node_id == graph.start_node_id
    assert explorer._current_node_id is None
    assert explorer.manager.to_graph(graph.start_node_id).to_dict() == graph.to_dict()
    assert explorer._visual_affordance_observed_node_ids == {"start", "target"}


def _selection_node(
    node_id: str,
    *,
    business_affordances: list[BusinessAffordance] | None = None,
) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=list(business_affordances or []),
    )


def _selection_edge(source: str, target: str, action_name: str) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_name,
        action=BrowserAction(
            action_kind="business_intent",
            locator=None,
            semantic_id=action_name,
            canonical_action_name=action_name,
        ),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            concrete_action_kind="business_intent",
            concrete_locator=None,
            concrete_target_sample=action_name,
            input_values_used={},
            before_observation_id=source,
            after_observation_id=target,
            success=True,
        ),
        status="succeeded_with_observed_change",
    )


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


class ExhaustedNodeBackAdapter:
    app_name = "fake"

    def __init__(self):
        self.back_calls = 0
        self.executed = []

    async def observe_state(self):
        return StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"url_path": "/listing"},
        )

    async def list_interactables(self, state):
        return []

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        return True

    async def go_back(self):
        self.back_calls += 1
        return True


@pytest.mark.anyio
async def test_explore_one_step_uses_ordinary_target_for_signature_change():
    explorer = _business_explorer(FakeAdapter())

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
async def test_explore_one_step_records_initial_source_embedding():
    calls = []

    def embed(summary_text):
        calls.append(summary_text)
        return [1.0, 0.0]

    explorer = _business_explorer(
        FakeAdapter(),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )

    graph = await explorer.explore_one_step()

    record_ids = {record.node_id for record in explorer.state_embedding_records}
    assert graph.start_node_id in record_ids
    assert {node.node_id for node in graph.nodes} <= record_ids
    assert calls


def test_ensure_source_embedding_does_not_repeat_provider_for_same_node():
    calls = []

    def embed(summary_text):
        calls.append(summary_text)
        return [1.0, 0.0]

    explorer = _business_explorer(
        FakeAdapter(),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))
    before = StateSnapshot(
        page_id="listing",
        url="https://example.test/listing",
        title="Listing",
        signature={"cart_has_items": False},
    )

    explorer._ensure_source_embedding(
        node_id="listing",
        before=before,
        before_interactables=[],
    )
    explorer._ensure_source_embedding(
        node_id="listing",
        before=before,
        before_interactables=[],
    )

    assert len(calls) == 1
    assert [record.node_id for record in explorer.state_embedding_records] == [
        "listing"
    ]


def test_ensure_source_embedding_skips_when_exploration_memory_disabled():
    calls = []

    def embed(summary_text):
        calls.append(summary_text)
        return [1.0, 0.0]

    explorer = _business_explorer(
        FakeAdapter(),
        enable_exploration_memory=False,
        state_embedding_provider=embed,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))

    explorer._ensure_source_embedding(
        node_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_has_items": False},
        ),
        before_interactables=[],
    )

    assert calls == []
    assert explorer.state_embedding_records == []


@pytest.mark.anyio
async def test_multi_step_graph_nodes_have_embedding_records():
    explorer = _business_explorer(
        FakeAdapter(),
        enable_exploration_memory=True,
        state_embedding_provider=lambda summary_text: [1.0, 0.0],
    )

    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    graph_node_ids = {node.node_id for node in graph.nodes}
    embedding_node_ids = {
        record.node_id for record in explorer.state_embedding_records
    }
    assert graph_node_ids <= embedding_node_ids


@pytest.mark.anyio
async def test_explore_one_step_preserves_deterministic_node_naming():
    explorer = _business_explorer(FakeAdapter())

    graph = await explorer.explore_one_step()

    nodes_by_id = {node.node_id: node for node in graph.nodes}
    source = nodes_by_id[graph.edges[0].source_node_id]
    assert source.node_label == "listing"
    assert source.state_summary == "Business page with actionable controls."
    assert source.naming_provenance == {"source": "deterministic_fallback"}


@pytest.mark.anyio
async def test_explore_one_step_records_profile_verified_planning_delta():
    explorer = _business_explorer(FakeAdapter())

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.planning_delta is not None
    assert edge.planning_delta.verified_added_facts == ["cart_has_items"]


@pytest.mark.anyio
async def test_explore_one_step_propagates_planning_delta_to_target_node():
    explorer = _business_explorer(FakeAdapter())

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
    explorer = _business_explorer(FakeAdapter())

    first_graph = await explorer.explore_one_step()
    second_graph = await explorer.explore_one_step()

    assert second_graph.start_node_id == first_graph.edges[0].source_node_id


@pytest.mark.anyio
async def test_two_steps_with_current_pointer_do_not_materialize_orphan_before_draft():
    adapter = FakeAdapter()
    explorer = _business_explorer(adapter)

    first_graph = await explorer.explore_one_step()
    first_snapshots = {
        node.node_id: dict(node.last_state_snapshot) for node in first_graph.nodes
    }
    second_graph = await explorer.explore_one_step()

    edge_endpoints = {
        node_id
        for edge in second_graph.edges
        for node_id in (edge.source_node_id, edge.target_node_id)
    }
    assert {node.node_id for node in second_graph.nodes} == edge_endpoints
    assert {
        node.node_id: dict(node.last_state_snapshot)
        for node in second_graph.nodes
        if node.node_id in first_snapshots
    } == {
        node_id: snapshot
        for node_id, snapshot in first_snapshots.items()
        if node_id in edge_endpoints
    }


@pytest.mark.anyio
@pytest.mark.parametrize("change_kind", ["presentation", "state_indicator", "surface", "mixed"])
async def test_explicit_visual_change_kind_materializes_observed_transition(change_kind):
    adapter = SamePageBusinessChangeAdapter()

    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("observe_page")
        return (
            '{"candidate_added_facts":[],"candidate_removed_facts":[],'
            f'"visual_change_kind":"{change_kind}"}}'
        )

    explorer = _business_explorer(adapter, visual_delta_provider=provider)

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "succeeded_with_observed_change"
    assert edge.source_node_id != edge.target_node_id
    assert edge.visual_change_kind == change_kind


@pytest.mark.anyio
async def test_explore_one_step_marks_repeated_self_loop_edge_unproductive():
    adapter = RepeatedStateAdapter()
    provider = _default_visual_provider(added_facts=[], removed_facts=[])
    explorer = _business_explorer(
        adapter,
        visual_delta_provider=provider,
    )
    explorer._select_action = lambda **_: BrowserAction(
        action_kind="business_intent",
        locator=None,
        semantic_id="first_action",
        canonical_action_name="first_action",
        description="First action",
    )

    first_graph = await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    assert [action.semantic_id for action in adapter.executed] == [
        "first_action",
        "first_action",
    ]
    assert [edge.action.semantic_id for edge in graph.edges] == ["first_action"]
    assert graph.edges[0].visit_count == 2
    assert first_graph.meta["last_step_graph_changed"] is True
    assert graph.meta["last_step_graph_changed"] is False


@pytest.mark.anyio
async def test_edge_novelty_uses_canonical_action_not_raw_alias():
    adapter = RepeatedStateAdapter()
    explorer = _business_explorer(
        adapter,
        visual_delta_provider=_default_visual_provider(
            added_facts=[],
            removed_facts=[],
        ),
    )
    actions = iter(
        [
            BrowserAction(
                action_kind="business_intent",
                locator=None,
                semantic_id="sort_by_name",
                canonical_action_name="sort_items",
            ),
            BrowserAction(
                action_kind="business_intent",
                locator=None,
                semantic_id="order_items_alphabetically",
                canonical_action_name="sort_items",
            ),
        ]
    )
    explorer._select_action = lambda **_: next(actions)

    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    assert [edge.action.semantic_id for edge in graph.edges] == [
        "sort_by_name",
        "order_items_alphabetically",
    ]
    assert graph.meta["last_step_graph_changed"] is False


@pytest.mark.anyio
async def test_explore_one_step_stops_forward_when_current_node_is_exhausted():
    adapter = ExhaustedNodeBackAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert adapter.back_calls == 0
    assert adapter.executed == []
    assert graph.total_steps_completed == 0
    assert graph.edges == []
    assert len(graph.nodes) == 1
    assert graph.meta["last_step_kind"] == "current_state_exhausted"
    assert graph.meta["last_step_status"] == "unproductive"


@pytest.mark.anyio
async def test_explore_one_step_does_not_fallback_to_low_level_interactables():
    adapter = FakeAdapter()
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert adapter.executed == []
    assert graph.total_steps_completed == 0
    assert graph.edges == []
    assert graph.meta["last_step_kind"] == "current_state_exhausted"
    assert graph.meta["last_step_status"] == "unproductive"


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
    explorer = _business_explorer(
        FailingDiagnosticAdapter(),
        visual_delta_provider=_default_visual_provider(
            added_facts=[],
            meaningful_change=False,
            relevance="unknown",
        ),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "failed_execution"
    assert edge.execution_trace.error == "locator_not_visible"
    assert graph.meta["resume_cursor_node_id"] == edge.source_node_id


class ReportedFailureWithObservedChangeAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.last_execution_error = None

    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        self.last_execution_error = "tool reported failure after changing the page"
        return False


@pytest.mark.anyio
async def test_explore_one_step_keeps_failed_action_on_source_node():
    explorer = _business_explorer(ReportedFailureWithObservedChangeAdapter())

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "failed_execution"
    assert edge.source_node_id == edge.target_node_id
    assert edge.execution_trace.success is False
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
    explorer = _business_explorer(StagehandMetadataAdapter())

    graph = await explorer.explore_one_step()

    metadata = graph.edges[0].execution_trace.metadata
    assert metadata["action_source"] == "stagehand"
    assert metadata["stagehand_selector"] is None
    assert metadata["backend_reported_success"] is True


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


class AssertingExecuteAdapter(FakeAdapter):
    def __init__(self, before_execute):
        super().__init__()
        self.before_execute = before_execute

    async def execute(self, action: BrowserAction):
        self.before_execute()
        self.executed.append(action)
        return True


@pytest.mark.anyio
async def test_explorer_checkpoints_inflight_before_adapter_execution():
    snapshots = []
    adapter = AssertingExecuteAdapter(
        before_execute=lambda: snapshots.append("adapter_execute")
    )
    explorer = _business_explorer(
        adapter,
        attempt_checkpoint=lambda graph: snapshots.append(graph.to_dict()),
    )
    explorer.manager.meta["resume_cursor_node_id"] = "old_cursor"

    graph = await explorer.explore_one_step()

    inflight = snapshots[0]["meta"]["inflight_action"]
    assert snapshots[0]["meta"]["resume_cursor_node_id"] == "old_cursor"
    assert inflight["source_node_id"] == graph.edges[0].source_node_id
    assert inflight["action_id"] == graph.edges[0].action.semantic_id
    assert inflight["attempt_id"]
    assert snapshots[1] == "adapter_execute"
    assert "inflight_action" not in graph.meta
    assert graph.meta["resume_cursor_node_id"] == graph.edges[0].target_node_id
    assert graph.execution_events[-1].execution_trace.metadata["attempt_id"] == (
        inflight["attempt_id"]
    )


class RaisingExecuteAdapter(FakeAdapter):
    async def execute(self, action: BrowserAction):
        self.executed.append(action)
        raise RuntimeError("execute interrupted")


@pytest.mark.anyio
async def test_execute_exception_leaves_durable_inflight_without_event():
    snapshots = []
    explorer = _business_explorer(
        RaisingExecuteAdapter(),
        attempt_checkpoint=lambda graph: snapshots.append(graph.to_dict()),
    )

    with pytest.raises(RuntimeError, match="execute interrupted"):
        await explorer.explore_one_step()

    assert len(snapshots) == 1
    assert explorer.manager.to_graph().execution_events == []
    assert "inflight_action" in explorer.manager.meta


class StagehandThinkingFailureUrlChangeAdapter(
    StagehandThinkingFailureVisualChangeAdapter
):
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
                page_id="cart",
                url="https://example.test/cart",
                title="Cart",
                signature={"url_path": "/cart"},
            ),
        ]


class StagehandThinkingFailureSignatureChangeAdapter(
    StagehandThinkingFailureVisualChangeAdapter
):
    def __init__(self):
        super().__init__()
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing", "search_query": ""},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing", "search_query": "chair"},
            ),
        ]


class SamePageLowValueChangeAdapter(ScreenshotAdapter):
    def __init__(self):
        super().__init__()
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing", "sort": "name"},
            ),
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"url_path": "/listing", "sort": "price"},
            ),
        ]

    async def list_interactables(self, state):
        return [
            {
                "semantic_id": "sort_by_price",
                "description": "Sort by price",
                "locator": "#sort",
                "action_kind": "click",
                "explored": False,
            }
        ]


class SamePageBusinessChangeAdapter(ScreenshotAdapter):
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


class SameUrlBusinessRevisitAdapter(ScreenshotAdapter):
    def __init__(self):
        super().__init__()
        self.states = [
            StateSnapshot(
                page_id="shopping",
                url="https://example.test/shopping",
                title="Shopping",
                signature={"url_path": "/shopping"},
            ),
            StateSnapshot(
                page_id="shopping",
                url="https://example.test/shopping",
                title="Shopping",
                signature={"url_path": "/shopping"},
            ),
        ]

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        if self.executed:
            return [
                {
                    "semantic_id": "open_checkout",
                    "description": "Open checkout",
                    "locator": "#checkout",
                    "action_kind": "click",
                    "explored": False,
                }
            ]
        return [
            {
                "semantic_id": "add_to_cart",
                "description": "Add to cart",
                "locator": "#add",
                "action_kind": "click",
                "explored": False,
            }
        ]


class SamePageCheckoutFlowAdapter(ScreenshotAdapter):
    def __init__(self):
        super().__init__()
        self.states = [
            StateSnapshot(
                page_id="shopping",
                url="https://example.test/shopping",
                title="Shopping",
                signature={"url_path": "/shopping"},
            )
        ]

    async def observe_state(self):
        return self.states[0]

    async def list_interactables(self, state):
        if len(self.executed) == 0:
            return [
                {
                    "semantic_id": "open_checkout",
                    "description": "Open checkout",
                    "locator": "#checkout",
                    "action_kind": "click",
                    "explored": False,
                }
            ]
        if len(self.executed) == 1:
            return [
                {
                    "semantic_id": "fill_contact_information",
                    "description": "Fill contact information",
                    "locator": "#contact",
                    "action_kind": "click",
                    "explored": False,
                }
            ]
        return [
            {
                "semantic_id": "choose_payment_method",
                "description": "Choose payment method",
                "locator": "#payment",
                "action_kind": "click",
                "explored": False,
            }
        ]


@pytest.mark.anyio
async def test_explore_one_step_records_optional_before_after_screenshots():
    adapter = ScreenshotAdapter()
    explorer = _business_explorer(adapter)

    graph = await explorer.explore_one_step()

    metadata = graph.edges[0].execution_trace.metadata
    assert adapter.captured_labels == ["before_0001", "after_0001"]
    assert metadata["before_screenshot_path"] == "outputs/before_0001.png"
    assert metadata["after_screenshot_path"] == "outputs/after_0001.png"


@pytest.mark.anyio
async def test_explore_one_step_records_visual_business_affordances_on_source_node():
    adapter = ScreenshotAdapter()
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(
            {
                "current": current_screenshot_path,
                "before": before_screenshot_path,
                "after": after_screenshot_path,
            }
        )
        if current_screenshot_path is not None:
            return (
                '{"business_affordances":['
                '{"action_name":"add_item_to_cart",'
                '"relevance_hint":"core",'
                '"target_hint":"button labeled Add to cart",'
                '"evidence":"A product card contains an Add to cart button.",'
                '"confidence":0.9}'
                "],"
                '"state_summary":"Product listing page with add-to-cart controls."}'
            )
        return (
            '{"visible_change_summary":"Cart count changed.",'
            '"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge changed"],'
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

    assert provider_calls[0]["current"] == "outputs/before_0001.png"
    source = {node.node_id: node for node in graph.nodes}[graph.edges[0].source_node_id]
    assert len(source.business_affordances) == 1
    assert source.business_affordances[0].action_name == "add_item_to_cart"
    assert source.business_affordances[0].target_hint == "button labeled Add to cart"


def test_record_source_business_affordances_skips_existing_node_frontier():
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(current_screenshot_path)
        return _business_affordance_response("sort_products")

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    explorer.manager.identify_or_add_node(
        _selection_node(
            "cart_with_items",
            business_affordances=[
                BusinessAffordance("view_cart"),
                BusinessAffordance("proceed_to_checkout"),
            ],
        )
    )

    explorer._record_source_business_affordances(
        source_id="cart_with_items",
        before=StateSnapshot(
            page_id="cart",
            url="https://example.test/cart",
            title="Cart",
            signature={"cart_has_items": True},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    assert provider_calls == []
    node = explorer.manager.node_for_id("cart_with_items")
    assert [
        affordance.action_name for affordance in node.business_affordances
    ] == ["view_cart", "proceed_to_checkout"]


def test_record_source_business_affordances_does_not_require_business_profile():
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(current_screenshot_path)
        return _business_affordance_response("search_items")

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))

    explorer._record_source_business_affordances(
        source_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert provider_calls == ["outputs/before_0001.png"]
    assert [item.action_name for item in node.business_affordances] == [
        "search_items"
    ]


def _state_label_provider(label):
    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is None:
            return '{"candidate_added_facts":[],"candidate_removed_facts":[]}'
        return json.dumps(
            {
                "state_label": label,
                "business_affordances": [
                    {
                        "action_name": "view_cart",
                        "label": "View cart",
                        "target_hint": "cart link",
                    }
                ],
            }
        )

    return provider


def test_record_source_business_affordances_accepts_vlm_state_label_without_changing_id():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=_state_label_provider("product_list_sorted"),
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))

    explorer._record_source_business_affordances(
        source_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_count": 0},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert node.node_id == "listing"
    assert node.node_label == "product_list_sorted"
    assert node.naming_provenance == {"source": "visual_affordance_vlm"}


def test_record_source_business_affordances_does_not_repeat_empty_vlm_result():
    labels = iter(["empty_results", "different_revisit_label"])
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(current_screenshot_path)
        return json.dumps(
            {
                "state_label": next(labels),
                "regions": [],
            }
        )

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))
    before = StateSnapshot(
        page_id="listing",
        url="https://example.test/listing",
        title="Listing",
        signature={"cart_count": 0},
    )

    explorer._record_source_business_affordances(
        source_id="listing",
        before=before,
        before_screenshot_path="outputs/before_0001.png",
    )
    explorer._record_source_business_affordances(
        source_id="listing",
        before=before,
        before_screenshot_path="outputs/before_0002.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert provider_calls == [
        "outputs/before_0001.png",
    ]
    assert node.node_label == "empty_results"


def test_record_source_business_affordances_does_not_repeat_empty_invalid_label_result():
    labels = iter(["!!!", "different_revisit_label"])
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        provider_calls.append(current_screenshot_path)
        return json.dumps(
            {
                "state_label": next(labels),
                "regions": [],
            }
        )

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    explorer.manager.identify_or_add_node(_selection_node("listing"))
    before = StateSnapshot(
        page_id="listing",
        url="https://example.test/listing",
        title="Listing",
        signature={"cart_count": 0},
    )

    explorer._record_source_business_affordances(
        source_id="listing",
        before=before,
        before_screenshot_path="outputs/before_0001.png",
    )
    explorer._record_source_business_affordances(
        source_id="listing",
        before=before,
        before_screenshot_path="outputs/before_0002.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert provider_calls == [
        "outputs/before_0001.png",
    ]
    assert node.node_label == "listing"


def test_record_source_business_affordances_preserves_revisit_label_and_id():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=_state_label_provider("different_revisit_label"),
    )
    explorer.manager.identify_or_add_node(
        replace(
            _selection_node(
                "listing",
                business_affordances=[BusinessAffordance("view_cart")],
            ),
            node_label="product_list",
            naming_provenance={"source": "visual_affordance_vlm"},
        )
    )

    explorer._record_source_business_affordances(
        source_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_count": 0},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert node.node_id == "listing"
    assert node.node_label == "product_list"


def test_record_source_business_affordances_falls_back_for_invalid_vlm_label():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=_state_label_provider("!!!"),
    )
    explorer.manager.identify_or_add_node(
        replace(
            _selection_node("listing"),
            node_label="listing",
            naming_provenance={"source": "deterministic_fallback"},
        )
    )

    explorer._record_source_business_affordances(
        source_id="listing",
        before=StateSnapshot(
            page_id="listing",
            url="https://example.test/listing",
            title="Listing",
            signature={"cart_count": 0},
        ),
        before_screenshot_path="outputs/before_0001.png",
    )

    node = explorer.manager.node_for_id("listing")
    assert node.node_id == "listing"
    assert node.node_label == "listing"
    assert node.naming_provenance == {"source": "deterministic_fallback"}


def test_web_kobe_explorer_rejects_invalid_max_candidates():
    with pytest.raises(ValueError, match="max_candidates"):
        WebKobeExplorer(
            adapter=FakeAdapter(),
            semantic_assistor=DeterministicSemanticAssistor(app="fake"),
            max_candidates=0,
        )


@pytest.mark.anyio
async def test_visual_affordance_request_uses_configured_max_candidates():
    adapter = ScreenshotAdapter()
    provider_calls = []
    default_provider = _default_visual_provider()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            provider_calls.append(json.loads(prompt))
            return _business_affordance_response()
        return default_provider(
            prompt,
            before_screenshot_path=before_screenshot_path,
            after_screenshot_path=after_screenshot_path,
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        max_candidates=2,
    )

    await explorer.explore_one_step()

    assert provider_calls[0]["max_candidates"] == 2


@pytest.mark.anyio
async def test_explore_one_step_prefers_high_ranked_current_business_affordance():
    adapter = ScreenshotAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return (
                '{"business_affordances":['
                '{"action_name":"open_cart",'
                '"relevance_hint":"core",'
                '"target_hint":"shopping cart link",'
                '"evidence":"A cart link is visible in the header.",'
                '"confidence":0.8},'
                '{"action_name":"add_item_to_cart",'
                '"relevance_hint":"core",'
                '"target_hint":"button labeled Add to cart",'
                '"evidence":"A product card contains an Add to cart button.",'
                '"confidence":0.9}'
                "],"
                '"state_summary":"Product listing page."}'
            )
        return (
            '{"visible_change_summary":"Cart count changed.",'
            '"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge changed"],'
            '"confidence":0.8}'
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )
    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()

    assert adapter.executed[1].action_kind == "business_intent"
    assert adapter.executed[1].semantic_id == "add_item_to_cart"
    assert adapter.executed[1].canonical_action_name == "add_item_to_cart"
    assert "button labeled Add to cart" in adapter.executed[1].description
    assert (
        "Execute only this selected business action"
        in adapter.executed[1].description
    )
    assert (
        "Do not continue to the next business goal"
        in adapter.executed[1].description
    )
    assert [edge.action.semantic_id for edge in graph.edges] == [
        "add_item_to_cart",
        "add_item_to_cart",
    ]


def test_business_affordance_selection_does_not_downrank_action_completed_elsewhere():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )
    explorer._start_node_id = "product_list"
    explorer.manager.identify_or_add_node(_selection_node("product_list"))
    explorer.manager.identify_or_add_node(_selection_node("cart"))
    explorer.manager.identify_or_add_node(
        _selection_node(
            "product_detail",
            business_affordances=[
                BusinessAffordance(
                    action_name="sort_products",
                    relevance_hint="low_value",
                    confidence=0.8,
                ),
                BusinessAffordance(
                    action_name="add_item_to_cart",
                    relevance_hint="core",
                    confidence=0.9,
                ),
            ],
        )
    )
    explorer.manager.add_edge(
        _selection_edge("product_list", "cart", "add_item_to_cart")
    )

    selected = explorer._select_business_affordance_action(
        exploration_context=ExplorationContext(
            current_node_id="product_detail",
            reference_node_id="product_detail",
            is_revisit=False,
            tried_action_ids=(),
            avoid_action_ids=(),
        )
    )

    assert selected is not None
    assert selected.semantic_id == "add_item_to_cart"


def test_business_action_snapshots_supporting_facts_without_expected_effect_text():
    action = _business_action_from_affordance(
        BusinessAffordance(
            action_name="search_items",
            label="Search",
            target_hint="search input",
            supporting_facts=["search_input_visible"],
        )
    )

    assert action.supporting_facts == ["search_input_visible"]
    assert "search input" in action.description
    assert "Expected visible change:" not in action.description


def test_business_affordance_selection_returns_none_when_local_frontier_exhausted():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )
    explorer.manager.identify_or_add_node(
        _selection_node(
            "product_detail",
            business_affordances=[
                BusinessAffordance(
                    action_name="view_product_details",
                    relevance_hint="core",
                    confidence=0.9,
                ),
                BusinessAffordance(
                    action_name="add_item_to_cart",
                    relevance_hint="core",
                    confidence=0.8,
                ),
            ],
        )
    )

    selected = explorer._select_business_affordance_action(
        exploration_context=ExplorationContext(
            current_node_id="product_detail",
            reference_node_id="product_detail",
            is_revisit=False,
            tried_action_ids=("view_product_details", "add_item_to_cart"),
            avoid_action_ids=(),
        )
    )

    assert selected is None


def test_business_affordance_selection_avoids_semantically_repeated_local_action():
    vectors = {
        "order_items_alphabetically": (1.0, 0.0),
        "sort_by_name": (0.98, 0.12),
        "filter_by_price": (0.0, 1.0),
    }

    def embedding_provider(text: str):
        return vectors[text]

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        action_embedding_provider=embedding_provider,
    )
    explorer.manager.identify_or_add_node(
        _selection_node(
            "product_detail",
            business_affordances=[
                BusinessAffordance(
                    action_name="order_items_alphabetically",
                    relevance_hint="core",
                    confidence=0.9,
                ),
                BusinessAffordance(
                    action_name="filter_by_price",
                    relevance_hint="core",
                    confidence=0.8,
                ),
            ],
        )
    )

    selected = explorer._select_business_affordance_action(
        exploration_context=ExplorationContext(
            current_node_id="product_detail",
            reference_node_id="product_detail",
            is_revisit=False,
            tried_action_ids=("sort_by_name",),
            avoid_action_ids=(),
        )
    )

    assert selected is not None
    assert selected.semantic_id == "filter_by_price"


def test_state_embedding_provider_does_not_drive_action_deduplication():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        state_embedding_provider=lambda text: [1.0, 0.0],
    )
    explorer.manager.identify_or_add_node(
        _selection_node(
            "product_detail",
            business_affordances=[BusinessAffordance("clear_search_query")],
        )
    )

    selected = explorer._select_business_affordance_action(
        exploration_context=ExplorationContext(
            current_node_id="product_detail",
            reference_node_id="product_detail",
            is_revisit=False,
            tried_action_ids=("prior_visit",),
            avoid_action_ids=(),
        )
    )

    assert selected is not None
    assert selected.semantic_id == "clear_search_query"


@pytest.mark.anyio
async def test_explore_one_step_uses_signature_change_for_same_page_target():
    adapter = SamePageLowValueChangeAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("sort_products", relevance="low_value")
        return (
            '{"visible_change_summary":"The product list sort order changed.",'
            '"business_action_name":"sort_products",'
            '"business_relevance":"low_value",'
            '"meaningful_change":false,'
            '"candidate_added_facts":[],"candidate_removed_facts":[],'
            '"evidence":["sort dropdown changed"],"confidence":0.8}'
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )

    graph = await explorer.explore_one_step()

    assert len(graph.nodes) == 2
    edge = graph.edges[0]
    assert edge.source_node_id != edge.target_node_id
    assert not hasattr(edge, "business_transition")


@pytest.mark.anyio
async def test_explore_one_step_materializes_same_page_business_change(monkeypatch):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SamePageBusinessChangeAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("add_item_to_cart")
        return (
            '{"visible_change_summary":"The cart badge now shows one item.",'
            '"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge shows 1"],'
            '"confidence":0.85}'
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
    )

    graph = await explorer.explore_one_step()

    assert len(graph.nodes) == 2
    edge = graph.edges[0]
    assert edge.source_node_id != edge.target_node_id
    assert edge.status == "succeeded_with_observed_change"
    target = {node.node_id: node for node in graph.nodes}[edge.target_node_id]
    assert "__observation_" in target.node_id
    assert target.node_label == "listing"
    assert target.planning_state is not None
    assert target.planning_state.active_facts == []


@pytest.mark.anyio
async def test_explore_one_step_uses_embedding_match_as_current_business_node(
    monkeypatch,
):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SameUrlBusinessRevisitAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            if adapter.executed:
                return _business_affordance_response("open_checkout")
            return _business_affordance_response("add_to_cart")
        return (
            '{"visible_change_summary":"The cart badge now shows one item.",'
            '"business_action_name":"add_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge shows 1"],'
            '"confidence":0.85}'
        )

    def embed(text):
        if "Open checkout" in text or "cart badge now shows one item" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )

    first_graph = await explorer.explore_one_step()
    first_target_id = first_graph.edges[0].target_node_id
    second_graph = await explorer.explore_one_step()

    assert second_graph.edges[1].source_node_id == first_target_id
    assert second_graph.edges[1].planning_transition is not None
    assert second_graph.edges[1].planning_transition.pre_facts == []


@pytest.mark.anyio
async def test_explore_one_step_uses_near_threshold_embedding_match_as_source(
    monkeypatch,
):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SameUrlBusinessRevisitAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("sort_products", relevance="low_value")
        return (
            '{"visible_change_summary":"The cart badge now shows one item.",'
            '"business_action_name":"add_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge shows 1"],'
            '"confidence":0.85}'
        )

    def embed(text):
        if "cart badge now shows one item" in text:
            return [1.0, 0.0]
        if "Open checkout" in text:
            return [0.89, 0.455961]
        return [0.0, 1.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )

    first_graph = await explorer.explore_one_step()
    first_target_id = first_graph.edges[0].target_node_id
    second_graph = await explorer.explore_one_step()

    assert second_graph.edges[1].source_node_id == first_target_id


@pytest.mark.anyio
async def test_explore_one_step_does_not_pollute_existing_page_node_with_incompatible_planning_state(
    monkeypatch,
):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SameUrlBusinessRevisitAdapter()
    visual_responses = iter(
        [
            (
                '{"visible_change_summary":"The cart badge now shows one item.",'
                '"business_action_name":"add_to_cart",'
                '"business_relevance":"core",'
                '"meaningful_change":true,'
                '"candidate_added_facts":["cart_has_items"],'
                '"candidate_removed_facts":[],"evidence":["cart badge shows 1"],'
                '"confidence":0.85}'
            ),
            (
                '{"visible_change_summary":"The page shell is still the product list.",'
                '"business_action_name":"view_cart",'
                '"business_relevance":"unknown",'
                '"meaningful_change":false,'
                '"candidate_added_facts":[],"candidate_removed_facts":[],'
                '"evidence":["no cart modal is visible"],"confidence":0.6}'
            ),
        ]
    )

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            if adapter.executed:
                return _business_affordance_response("view_cart")
            return _business_affordance_response("add_to_cart")
        return next(visual_responses)

    def embed(text):
        if "cart badge now shows one item" in text:
            return [1.0, 0.0]
        if "Open checkout" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )

    first_graph = await explorer.explore_one_step()
    root_id = first_graph.start_node_id
    second_graph = await explorer.explore_one_step()

    nodes_by_id = {node.node_id: node for node in second_graph.nodes}
    root = nodes_by_id[root_id]
    assert root.planning_state is None
    assert second_graph.edges[1].target_node_id != root_id
    assert (
        nodes_by_id[second_graph.edges[1].target_node_id]
        .planning_state.active_facts
        == []
    )


@pytest.mark.anyio
async def test_explore_one_step_keeps_source_on_latest_materialized_business_node(
    monkeypatch,
):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SamePageCheckoutFlowAdapter()
    visual_responses = iter(
        [
            (
                '{"visible_change_summary":"Checkout form is now visible.",'
                '"business_action_name":"start_checkout",'
                '"business_relevance":"core",'
                '"meaningful_change":true,'
                '"candidate_added_facts":["checkout_started"],'
                '"candidate_removed_facts":[],"evidence":["checkout form visible"],'
                '"confidence":0.85}'
            ),
            (
                '{"visible_change_summary":"Contact information fields are filled.",'
                '"business_action_name":"fill_contact_information",'
                '"business_relevance":"core",'
                '"meaningful_change":true,'
                '"candidate_added_facts":["checkout_user_info_complete"],'
                '"candidate_removed_facts":[],"evidence":["contact fields filled"],'
                '"confidence":0.85}'
            ),
            (
                '{"visible_change_summary":"Payment method is selected.",'
                '"business_action_name":"choose_payment_method",'
                '"business_relevance":"core",'
                '"meaningful_change":true,'
                '"candidate_added_facts":["payment_info_complete"],'
                '"candidate_removed_facts":[],"evidence":["payment method selected"],'
                '"confidence":0.85}'
            ),
        ]
    )

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            if len(adapter.executed) == 0:
                return _business_affordance_response("start_checkout")
            if len(adapter.executed) == 1:
                return _business_affordance_response("fill_contact_information")
            return _business_affordance_response("choose_payment_method")
        return next(visual_responses)

    def embed(text):
        if "checkout_started" in text:
            return [1.0, 0.0]
        if "checkout_user_info_complete" in text:
            return [0.0, 1.0]
        if "Choose payment method" in text:
            return [1.0, 0.0]
        return [0.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )

    await explorer.explore_one_step()
    second_graph = await explorer.explore_one_step()
    checkout_user_info_id = second_graph.edges[1].target_node_id
    third_graph = await explorer.explore_one_step()

    assert third_graph.edges[2].source_node_id == checkout_user_info_id
    assert third_graph.edges[2].planning_transition is not None
    assert third_graph.edges[2].planning_transition.pre_facts == []


@pytest.mark.anyio
async def test_explore_one_step_uses_one_embedding_match_for_source_and_memory():
    class ContextAdapter(ExhaustedNodeBackAdapter):
        def __init__(self):
            super().__init__()
            self.exploration_contexts = []

        def set_exploration_context(self, prompt_block):
            self.exploration_contexts.append(prompt_block)

    adapter = ContextAdapter()
    calls = []

    def embed(text):
        calls.append(text)
        if len(calls) == 1:
            return [0.0, 1.0]
        return [1.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
        state_embedding_records=[
            StateEmbeddingRecord(
                node_id="listing__existing",
                summary_text="existing listing",
                embedding=[1.0, 0.0],
            )
        ],
    )

    await explorer.explore_one_step()

    assert len(calls) == 2
    assert adapter.exploration_contexts
    assert "This state appears to revisit node" not in adapter.exploration_contexts[0]


@pytest.mark.anyio
async def test_explore_one_step_records_target_embedding_planning_facts(monkeypatch):
    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.explorer.OBSERVATION_WAIT_TIMEOUT_MS",
        0,
    )
    adapter = SamePageBusinessChangeAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("add_item_to_cart")
        return (
            '{"visible_change_summary":"The cart badge now shows one item.",'
            '"business_action_name":"add_item_to_cart",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
            '"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"evidence":["cart badge shows 1"],'
            '"confidence":0.85}'
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=visual_provider,
        enable_exploration_memory=True,
        state_embedding_provider=lambda text: [1.0, 0.0],
    )

    graph = await explorer.explore_one_step()

    target_id = graph.edges[0].target_node_id
    target_record = next(
        record
        for record in explorer.state_embedding_records
        if record.node_id == target_id
    )
    assert target_record.planning_facts == ()


@pytest.mark.anyio
async def test_explore_one_step_accepts_stagehand_tool_choice_error_with_visual_change():
    adapter = StagehandThinkingFailureVisualChangeAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            if adapter.executed:
                return _business_affordance_response("open_checkout")
            return _business_affordance_response("add_to_cart")
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
    assert edge.source_node_id != edge.target_node_id
    assert edge.execution_trace.success is True
    assert (
        edge.execution_trace.error == "Thinking mode does not support this tool_choice"
    )
    assert edge.execution_trace.metadata["backend_reported_success"] is False
    assert edge.planning_transition is not None
    assert edge.planning_transition.added_facts == []
    assert edge.execution_trace.metadata["visual_delta_trace"][
        "candidate_added_facts"
    ] == ["cart_has_items"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "adapter_class",
    [
        StagehandThinkingFailureUrlChangeAdapter,
        StagehandThinkingFailureSignatureChangeAdapter,
    ],
)
async def test_stagehand_tool_choice_error_observes_url_or_signature_change(
    adapter_class,
):
    explorer = _business_explorer(adapter_class())

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "succeeded_with_observed_change"
    assert edge.source_node_id != edge.target_node_id
    assert edge.execution_trace.success is True
    assert edge.execution_trace.error == (
        "Thinking mode does not support this tool_choice"
    )
    assert edge.execution_trace.metadata["backend_reported_success"] is False


@pytest.mark.anyio
async def test_stagehand_tool_choice_error_without_change_is_no_observed_change_self_loop():
    adapter = StagehandThinkingFailureVisualChangeAdapter()

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("clear_search_query")
        return '{"candidate_added_facts":[],"candidate_removed_facts":[]}'

    explorer = _business_explorer(adapter, visual_delta_provider=visual_provider)

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "no_observed_change"
    assert edge.source_node_id == edge.target_node_id
    assert edge.execution_trace.success is True
    assert edge.execution_trace.error is not None
    assert edge.execution_trace.metadata["backend_reported_success"] is False


@pytest.mark.anyio
async def test_explore_one_step_records_visual_delta_candidates_without_verifying_them():
    adapter = ScreenshotAdapter()
    provider_calls = []

    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("prepare_order_confirmation")
        provider_calls.append((before_screenshot_path, after_screenshot_path))
        return (
            '{"visible_change_summary":"Final confirmation control appears.",'
            '"business_action_name":"prepare_order_confirmation",'
            '"business_relevance":"core",'
            '"meaningful_change":true,'
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
    assert edge.planning_delta.candidate_added_facts == ["cart_has_items"]
    assert edge.planning_delta.verified_added_facts == ["cart_has_items"]
    assert "visual_change_summary" not in edge.execution_trace.metadata
    assert edge.execution_trace.metadata["visual_delta_trace"]["status"] == "summarized"
    assert edge.execution_trace.metadata["visual_delta_trace"][
        "candidate_added_facts"
    ] == ["order_place_pending_sensitive"]
    assert not hasattr(edge, "business_transition")


@pytest.mark.anyio
async def test_explore_one_step_persists_semantic_observation_on_successful_edge():
    def visual_provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("add_to_cart_product")
        assert '"source_location_hint": "listing"' in prompt
        assert "Do not invent a new location on every step." in prompt
        return (
            '{"candidate_added_facts":["cart_has_items"],'
            '"candidate_removed_facts":[],"visual_change_kind":"state_indicator",'
            '"action_role":"state_mutation","source_location":"shopping",'
            '"target_location":"shopping","completion_facts":["should_not_survive"],'
            '"candidate_required_facts":[],"preserved_facts":[],'
            '"semantic_evidence":["The cart count changed."],'
            '"semantic_confidence":0.9}'
        )

    explorer = _business_explorer(
        FakeAdapter(),
        visual_delta_provider=visual_provider,
    )
    graph = await explorer.explore_one_step()

    observation = graph.edges[0].semantic_observation
    assert observation is not None
    assert observation.source_location == "shopping"
    assert observation.target_location == "shopping"
    assert observation.completion_facts == []
    assert graph.edges[0].execution_trace.metadata["visual_delta_trace"][
        "llm_response"
    ]["source_location"] == "shopping"


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
    explorer = _business_explorer(TypedFactsAdapter())

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
    explorer = _business_explorer(
        NoChangeAdapter(),
        visual_delta_provider=_default_visual_provider(
            added_facts=[],
            meaningful_change=False,
            relevance="low_value",
        ),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "no_observed_change"
    assert edge.execution_trace.success is True
    assert edge.observed_delta == []
    assert graph.meta["resume_cursor_node_id"] == edge.source_node_id


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
    explorer = _business_explorer(
        NavigationOnlyAdapter(),
        visual_delta_provider=_default_visual_provider(
            action_name="cart_open",
            added_facts=[],
            meaningful_change=False,
            relevance="supporting",
        ),
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.action.semantic_id == "cart_open"
    assert edge.source_node_id.startswith("inventory__")
    assert edge.target_node_id.startswith("cart__")
    assert edge.schema_delta is None
    assert edge.observed_delta == []
    assert edge.status == "succeeded_with_navigation"
    assert graph.meta["resume_cursor_node_id"] == edge.target_node_id


@pytest.mark.anyio
async def test_explore_one_step_uses_business_affordance_naming():
    adapter = FakeAdapter()
    explorer = _business_explorer(
        adapter,
        visual_delta_provider=_default_visual_provider(
            action_name="product_add_to_cart",
            action_label="Add product to cart",
        ),
    )

    graph = await explorer.explore_one_step()

    assert adapter.executed[0].action_kind == "business_intent"
    assert adapter.executed[0].locator is None
    assert graph.edges[0].action.semantic_id == "product_add_to_cart"
    assert graph.edges[0].action.action_label == "Add product to cart"
    assert graph.edges[0].action.canonical_action_name == "product_add_to_cart"


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


def test_target_matching_reuses_existing_business_state_node():
    def embed(text):
        if "Cart" in text or "cart_has_items" in text:
            return [1.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )
    existing_cart = WebKobeNode(
        node_id="cart__existing",
        page_description="cart page",
        page_frame=PageFrame(
            page_id="fake:cart",
            page_type="cart",
            url="https://example.test/cart",
            url_pattern="https://example.test/cart",
            title="Cart",
        ),
        state_schema={},
        last_state_snapshot={"cart_has_items": True},
        node_label="cart",
        planning_state=PlanningState(
            active_facts=["cart_has_items"],
            profile_fact_ids=["cart_has_items"],
        ),
    )
    explorer.manager.identify_or_add_node(existing_cart)
    explorer.manager.identify_or_add_node(_selection_node("source"))
    explorer.manager.add_edge(_selection_edge("source", "cart__existing", "open_cart"))
    explorer.state_embedding_records = [
        StateEmbeddingRecord(
            node_id="cart__existing",
            summary_text=(
                "url_path: /cart\n"
                "title: Cart\n"
                "planning_facts: cart_has_items"
            ),
            embedding=[1.0, 0.0, 0.0],
            planning_facts=("cart_has_items",),
            context_markers=("cart_non_empty",),
        )
    ]
    candidate_cart = WebKobeNode(
        node_id="product_details__business_new",
        page_description="product details page",
        page_frame=PageFrame(
            page_id="fake:product_details",
            page_type="product_details",
            url="https://example.test/shopping",
            url_pattern="https://example.test/shopping",
            title="Shopping",
        ),
        state_schema={},
        last_state_snapshot={"cart_has_items": True},
        node_label="product_details",
    )
    after = StateSnapshot(
        page_id="cart",
        url="https://example.test/cart",
        title="Cart",
        signature={"url_path": "/cart", "cart_has_items": True},
    )

    matched_node, match = explorer._match_existing_target_node(
        target_node=candidate_cart,
        after=after,
        after_interactables=[],
        planning_transition=PlanningTransition(post_facts=["cart_has_items"]),
        source_node_id="source",
    )

    assert match is not None
    assert match.status == "same"
    assert matched_node.node_id == "cart__existing"
    assert matched_node.node_label == "cart"


def test_target_matching_runs_without_planning_transition():
    def embed(text):
        return [1.0, 0.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )
    explorer.manager.identify_or_add_node(_selection_node("source"))
    explorer.manager.identify_or_add_node(_selection_node("known"))
    explorer.manager.add_edge(_selection_edge("source", "known", "prior_visit"))
    explorer.state_embedding_records = [
        StateEmbeddingRecord(
            node_id="known",
            summary_text="known state",
            embedding=[1.0, 0.0, 0.0],
        )
    ]

    matched_node, match = explorer._match_existing_target_node(
        target_node=_selection_node("new_candidate"),
        after=StateSnapshot(
            page_id="known",
            url="https://example.test/known",
            title="Known",
            signature={},
        ),
        after_interactables=[],
        planning_transition=None,
        source_node_id="source",
    )

    assert match is not None
    assert match.status == "same"
    assert matched_node.node_id == "known"


def test_target_matching_reuses_known_state_despite_planning_fact_conflict():
    def embed(text):
        return [1.0, 0.0, 0.0]

    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=embed,
    )
    explorer.manager.identify_or_add_node(
        replace(
            _selection_node("cart__existing"),
            planning_state=PlanningState(active_facts=["old_observation"]),
        )
    )
    explorer.manager.identify_or_add_node(_selection_node("source"))
    explorer.manager.add_edge(_selection_edge("source", "cart__existing", "open_cart"))
    explorer.state_embedding_records = [
        StateEmbeddingRecord(
            node_id="cart__existing",
            summary_text="known cart state",
            embedding=[1.0, 0.0, 0.0],
        )
    ]

    matched_node, match = explorer._match_existing_target_node(
        target_node=_selection_node("new_candidate"),
        after=StateSnapshot(
            page_id="cart",
            url="https://example.test/cart",
            title="Cart",
            signature={},
        ),
        after_interactables=[],
        planning_transition=PlanningTransition(post_facts=["new_observation"]),
        source_node_id="source",
    )

    assert match is not None
    assert match.status == "same"
    assert match.blocked_reason is None
    assert matched_node.node_id == "cart__existing"


def test_source_matching_reuses_known_state_despite_planning_fact_conflict():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=lambda text: [1.0, 0.0],
    )
    explorer.manager.identify_or_add_node(
        replace(
            _selection_node("observed"),
            planning_state=PlanningState(active_facts=["observed_fact"]),
        )
    )
    explorer.manager.add_edge(_selection_edge("observed", "known", "revisit"))
    explorer.manager.identify_or_add_node(
        replace(
            _selection_node("known"),
            planning_state=PlanningState(active_facts=["known_fact"]),
        )
    )

    source_id, accepted_match = explorer._resolve_current_source_id(
        default_source_id="observed",
        source_match=StateMatch(status="same", node_id="known", score=0.99),
    )

    assert source_id == "known"
    assert accepted_match is not None


def test_target_matching_does_not_reuse_embedding_only_unknown_state():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        enable_exploration_memory=True,
        state_embedding_provider=lambda text: [1.0, 0.0, 0.0],
    )
    explorer.manager.identify_or_add_node(_selection_node("known"))
    explorer.manager.identify_or_add_node(_selection_node("source"))
    explorer.state_embedding_records = [
        StateEmbeddingRecord(
            node_id="known",
            summary_text="known state",
            embedding=[1.0, 0.0, 0.0],
        )
    ]

    matched_node, match = explorer._match_existing_target_node(
        target_node=_selection_node("unknown_candidate"),
        after=StateSnapshot(
            page_id="known",
            url="https://example.test/known",
            title="Known",
            signature={},
        ),
        after_interactables=[],
        planning_transition=PlanningTransition(post_facts=[]),
        source_node_id="source",
    )

    assert match is not None
    assert match.status == "blocked"
    assert match.blocked_reason == "embedding_only"
    assert matched_node.node_id == "unknown_candidate"


def test_source_matching_trusts_current_node_pointer_during_normal_exploration():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )
    explorer.manager.identify_or_add_node(_selection_node("cart"))
    explorer.manager.identify_or_add_node(_selection_node("checkout"))
    explorer._current_node_id = "checkout"

    source_id, accepted_match = explorer._resolve_current_source_id(
        default_source_id="checkout",
        source_match=StateMatch(status="same", node_id="cart", score=0.96),
    )

    assert source_id == "checkout"
    assert accepted_match is None


def test_tool_choice_error_without_visible_change_is_non_fatal_noop():
    explorer = WebKobeExplorer(
        adapter=FakeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    status = explorer._edge_status(
        execution_success=False,
        execution_error="Failed to execute task: Thinking mode does not support this tool_choice",
        observed_delta=[],
    )

    assert status == "no_observed_change"


@pytest.mark.anyio
async def test_failed_action_is_a_failed_self_loop_without_visual_delta_call():
    delta_calls = []

    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if before_screenshot_path is not None:
            delta_calls.append((before_screenshot_path, after_screenshot_path))
            return '{"candidate_added_facts":["should_not_be_used"]}'
        return _business_affordance_response("add_to_cart_product")

    explorer = _business_explorer(
        FailingDiagnosticAdapter(),
        visual_delta_provider=provider,
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.status == "failed_execution"
    assert edge.source_node_id == edge.target_node_id
    assert edge.planning_delta is not None
    assert edge.planning_delta.candidate_added_facts == []
    assert delta_calls == []


@pytest.mark.anyio
async def test_visual_delta_observation_creates_stable_node_without_planning_facts():
    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("sort_products")
        return (
            '{"candidate_added_facts":["modal_visible","cart_has_items"],'
            '"candidate_removed_facts":["modal_hidden"]}'
        )

    explorer = WebKobeExplorer(
        adapter=SamePageBusinessChangeAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=provider,
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.source_node_id != edge.target_node_id
    assert edge.status == "succeeded_with_observed_change"
    assert edge.planning_transition is not None
    assert edge.planning_transition.added_facts == []
    target = next(node for node in graph.nodes if node.node_id == edge.target_node_id)
    assert target.planning_state is not None
    assert target.planning_state.active_facts == []
    trace = edge.execution_trace.metadata["visual_delta_trace"]
    assert trace["candidate_added_facts"] == ["modal_visible", "cart_has_items"]
    assert trace["candidate_removed_facts"] == ["modal_hidden"]


@pytest.mark.anyio
async def test_visual_delta_fact_order_does_not_change_observation_node_id():
    def make_provider(added):
        def provider(
            prompt,
            *,
            current_screenshot_path=None,
            before_screenshot_path=None,
            after_screenshot_path=None,
        ):
            if current_screenshot_path is not None:
                return _business_affordance_response("sort_products")
            return (
                '{"candidate_added_facts":'
                + json.dumps(added)
                + ',"candidate_removed_facts":["modal_hidden"]}'
            )

        return provider

    def make_explorer(added):
        return WebKobeExplorer(
            adapter=SamePageBusinessChangeAdapter(),
            semantic_assistor=DeterministicSemanticAssistor(app="fake"),
            business_profile=ecommerce_checkout_profile(),
            capture_screenshots=True,
            visual_delta_provider=make_provider(added),
        )

    first = await make_explorer(["modal_visible", "cart_has_items"]).explore_one_step()
    second = await make_explorer(["cart_has_items", "modal_visible"]).explore_one_step()

    assert first.edges[0].target_node_id == second.edges[0].target_node_id


@pytest.mark.anyio
async def test_explicit_visual_change_does_not_embedding_match_back_to_source():
    adapter = SamePageBusinessChangeAdapter()
    assistor = DeterministicSemanticAssistor(app="fake")
    source_id = assistor.describe_state(
        snapshot=adapter.states[0],
        interactables=[],
    ).node_id

    def provider(
        prompt,
        *,
        current_screenshot_path=None,
        before_screenshot_path=None,
        after_screenshot_path=None,
    ):
        if current_screenshot_path is not None:
            return _business_affordance_response("clear_search_query")
        return '{"candidate_added_facts":["search_results_changed"],"candidate_removed_facts":[]}'

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=assistor,
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=provider,
        enable_exploration_memory=True,
        state_embedding_provider=lambda text: [1.0, 0.0],
        state_embedding_records=[
            StateEmbeddingRecord(
                node_id=source_id,
                summary_text="source state",
                embedding=[1.0, 0.0],
            )
        ],
    )

    graph = await explorer.explore_one_step()

    edge = graph.edges[0]
    assert edge.source_node_id == source_id
    assert edge.target_node_id != source_id
    assert "__observation_" in edge.target_node_id
    assert edge.execution_trace.metadata["target_state_match"][
        "blocked_reason"
    ] == "explicit_observation_change"


@pytest.mark.anyio
async def test_explicit_visual_change_does_not_match_historical_node():
    adapter = SamePageBusinessChangeAdapter()
    assistor = DeterministicSemanticAssistor(app="fake")
    source_id = assistor.describe_state(
        snapshot=adapter.states[0],
        interactables=[],
    ).node_id
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=assistor,
        business_profile=ecommerce_checkout_profile(),
        capture_screenshots=True,
        visual_delta_provider=lambda prompt, **kwargs: (
            _business_affordance_response("clear_search_query")
            if kwargs.get("current_screenshot_path") is not None
            else '{"candidate_added_facts":["search_results_changed"],"candidate_removed_facts":[]}'
        ),
        enable_exploration_memory=True,
        state_embedding_provider=lambda text: [1.0, 0.0],
        state_embedding_records=[
            StateEmbeddingRecord(
                node_id="history",
                summary_text="reliable history",
                embedding=[1.0, 0.0],
            )
        ],
    )
    explorer.manager.identify_or_add_node(_selection_node(source_id))
    explorer.manager.identify_or_add_node(_selection_node("history"))
    explorer.manager.add_edge(_selection_edge(source_id, "history", "prior_visit"))
    explorer._current_node_id = source_id

    graph = await explorer.explore_one_step()

    edge = graph.edges[-1]
    assert edge.target_node_id != "history"
    assert "__observation_" in edge.target_node_id
    assert edge.execution_trace.metadata["target_state_match"][
        "blocked_reason"
    ] == "explicit_observation_change"
