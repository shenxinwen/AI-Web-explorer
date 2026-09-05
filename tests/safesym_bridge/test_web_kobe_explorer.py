import json
import json
from dataclasses import replace

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.exploration_index import ExplorationContext
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.explorer import (
    WebKobeExplorer,
    _semantic_location_anchor,
    _business_action_from_affordance,
)
from ai_web_explorer.grounded_web.frontier_replay import FrontierReplayRunner
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
from ai_web_explorer.grounded_web.location_exploration import (
    ExplorationLimits,
    LocationExplorationCoordinator,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.resume import ResumePolicy
from ai_web_explorer.grounded_web.risk_detection import RiskAssessment
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.grounded_web.state_embedding import (
    StateEmbeddingRecord,
    StateMatch,
)
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence
from ai_web_explorer.grounded_web.semantic_planning import (
    build_semantic_planning_graph,
)
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
)


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
            scan_kind = json.loads(prompt).get("scan_kind", "initial")
            if scan_kind != "initial":
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
            return json.dumps(
                {
                    "location_id": "listing",
                    "actions": [
                        {
                            "action_id": action_name,
                            "description": action_label,
                            "target": target_hint,
                            "requires": [],
                        }
                    ],
                }
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
        '{"location_id":"listing","business_affordances":['
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
    action_outcome_provider=None,
    location_exploration_coordinator=None,
    state_embedding_provider=None,
    state_embedding_records=None,
    enable_exploration_memory: bool = False,
    goal: str = "Explore the web task.",
    attempt_checkpoint=None,
    risk_detection_provider=None,
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
        action_outcome_provider=action_outcome_provider,
        location_exploration_coordinator=location_exploration_coordinator,
        state_embedding_provider=state_embedding_provider,
        state_embedding_records=state_embedding_records,
        enable_exploration_memory=enable_exploration_memory,
        attempt_checkpoint=attempt_checkpoint,
        risk_detection_provider=risk_detection_provider,
    )


class ScreenshotAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.captured_labels = []

    async def capture_screenshot(self, label: str):
        self.captured_labels.append(label)
        return f"outputs/{label}.png"


@pytest.mark.anyio
async def test_shadow_risk_detection_records_assessment_before_execution():
    adapter = ScreenshotAdapter()
    requests = []

    def risk_provider(request):
        assert adapter.executed == []
        requests.append(request)
        return RiskAssessment(
            False, None, "The action is an ordinary interface operation."
        )

    graph = await _business_explorer(
        adapter, risk_detection_provider=risk_provider
    ).explore_one_step()

    assert len(requests) == 1
    assert requests[0].screenshot_path == "outputs/before_0001.png"
    assert requests[0].candidate_label
    assert adapter.executed
    assert graph.execution_events[-1].execution_trace.metadata["risk_assessment"] == {
        "potential_risk": False,
        "risk_type": None,
        "evidence": "The action is an ordinary interface operation.",
    }


@pytest.mark.anyio
async def test_shadow_risk_detection_failure_does_not_block_execution():
    adapter = ScreenshotAdapter()

    def failing_provider(request):
        raise RuntimeError("temporary provider failure")

    graph = await _business_explorer(
        adapter, risk_detection_provider=failing_provider
    ).explore_one_step()

    assert adapter.executed
    metadata = graph.execution_events[-1].execution_trace.metadata
    assert metadata["risk_detection_error"] == {
        "type": "RuntimeError",
        "message": "temporary provider failure",
    }


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


@pytest.mark.anyio
async def test_minimal_active_path_uses_outcome_without_targeted_or_supplement_scan():
    adapter = SamePageBusinessChangeAdapter()
    memory = LocationExplorationMemory()
    coordinator = LocationExplorationCoordinator(memory=memory)
    candidate_scan_kinds = []
    outcome_calls = []

    def candidate_provider(prompt, **kwargs):
        payload = json.loads(prompt)
        candidate_scan_kinds.append(payload.get("scan_kind", "initial"))
        return json.dumps(
            {
                "location_id": "listing",
                "actions": [
                    {
                        "action_id": "add_to_cart_product",
                        "description": "Add the visible product to the cart.",
                        "target": "Add to cart control",
                        "requires": [],
                    }
                ],
            }
        )

    def outcome_provider(prompt, **kwargs):
        outcome_calls.append(kwargs)
        return json.dumps(
            {
                "outcome": "success",
                "location_change": False,
                "evidence": ["The listing screen remains active."],
            }
        )

    explorer = _business_explorer(
        adapter,
        business_profile=None,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=outcome_provider,
        location_exploration_coordinator=coordinator,
    )

    graph = await explorer.explore_one_step()

    assert candidate_scan_kinds == ["initial"]
    assert len(outcome_calls) == 1
    assert memory.pool_for("listing").candidates["add_to_cart_product"].status == (
        "success"
    )
    assert len(graph.edges) == 1
    assert graph.edges[0].execution_trace.success is True
    assert graph.meta["last_step_semantic_progress"] is True


@pytest.mark.anyio
async def test_minimal_active_path_scans_new_location_with_initial_contract():
    class LocationSwitchAdapter(FakeAdapter):
        def __init__(self):
            super().__init__()
            self.states = [
                self.states[0],
                replace(
                    self.states[0],
                    page_id="checkout",
                    url="https://example.test/checkout",
                ),
            ]

        async def list_interactables(self, state):
            action_id = (
                "open_checkout" if state.page_id == "listing" else "fill_billing"
            )
            return [
                {
                    "semantic_id": action_id,
                    "description": action_id.replace("_", " "),
                    "locator": f"button.{action_id}",
                    "action_kind": "click",
                    "explored": False,
                }
            ]

        async def capture_screenshot(self, label):
            return f"{label}-{len(self.executed)}.png"

    adapter = LocationSwitchAdapter()
    memory = LocationExplorationMemory()
    coordinator = LocationExplorationCoordinator(memory=memory)
    candidate_locations = []

    def candidate_provider(prompt, **kwargs):
        location_id = "listing" if not candidate_locations else "checkout"
        candidate_locations.append(location_id)
        action_id = "open_checkout" if location_id == "listing" else "fill_billing"
        return json.dumps(
            {
                "location_id": location_id,
                "actions": [
                    {
                        "action_id": action_id,
                        "description": action_id.replace("_", " "),
                        "target": f"{action_id} control",
                        "requires": [],
                    }
                ],
            }
        )

    outcome_calls = []

    def outcome_provider(prompt, **kwargs):
        outcome_calls.append(kwargs)
        return json.dumps(
            {
                "outcome": "success",
                "location_change": len(outcome_calls) == 1,
                "evidence": ["The visible interface was observed."],
            }
        )

    explorer = _business_explorer(
        adapter,
        business_profile=None,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=outcome_provider,
        location_exploration_coordinator=coordinator,
    )

    await explorer.explore_one_step()
    await explorer.explore_one_step()

    assert candidate_locations == ["listing", "checkout"]
    assert "checkout" in memory.locations


class CheckoutDependencyAdapter:
    app_name = "checkout_dependency_fixture"

    def __init__(self, *, after_page_id="checkout"):
        self.state = StateSnapshot(
            page_id="checkout",
            url="https://example.test/checkout",
            title="Checkout",
            signature={"surface": "checkout"},
        )
        self.after_state = StateSnapshot(
            page_id=after_page_id,
            url="https://example.test/checkout",
            title="Checkout",
            signature={"surface": "checkout"},
        )
        self.executed = []

    async def observe_state(self):
        return self.after_state if self.executed else self.state

    async def list_interactables(self, state):
        action_id = "fill_billing" if not self.executed else "place_order"
        return [
            {
                "semantic_id": action_id,
                "description": action_id.replace("_", " "),
                "locator": f"button.{action_id}",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action):
        self.executed.append(action)
        return True

    async def capture_screenshot(self, label):
        return f"{label}-{len(self.executed)}.png"


def _checkout_dependency_candidate_provider(prompt, **kwargs):
    return json.dumps(
        {
            "location_id": "checkout",
            "actions": [
                {
                    "action_id": "fill_billing",
                    "description": "Fill the visible billing form.",
                    "target": "Billing form",
                    "requires": [],
                },
                {
                    "action_id": "place_order",
                    "description": "Submit the visible checkout form.",
                    "target": "Submit control",
                    "requires": ["fill_billing"],
                },
            ],
        }
    )


@pytest.mark.anyio
async def test_real_outcome_path_projects_dependency_actions_to_semantic_pddl():
    adapter = CheckoutDependencyAdapter()
    coordinator = LocationExplorationCoordinator(memory=LocationExplorationMemory())
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=_checkout_dependency_candidate_provider,
        action_outcome_provider=lambda prompt, **kwargs: json.dumps(
            {
                "outcome": "success",
                "location_change": False,
                "evidence": ["The checkout surface remains visible."],
            }
        ),
        location_exploration_coordinator=coordinator,
    )

    await explorer.explore_one_step()
    graph = await explorer.explore_one_step()
    semantic, report = build_semantic_planning_graph(graph)

    actions = {action.action_name: action for action in semantic.actions}
    assert report.excluded_edges == []
    assert actions["fill_billing"].added_facts == ["completed_checkout_fill_billing"]
    assert actions["place_order"].required_facts == ["completed_checkout_fill_billing"]
    domain = compile_minimal_semantic_domain(semantic).domain
    assert "(completed_checkout_fill_billing)" in domain
    assert (
        ":precondition (and (at_checkout) (completed_checkout_fill_billing))" in domain
    )


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["failed", "uncertain"])
async def test_real_failed_or_uncertain_outcome_is_not_projected(outcome):
    adapter = CheckoutDependencyAdapter()
    coordinator = LocationExplorationCoordinator(memory=LocationExplorationMemory())
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=_checkout_dependency_candidate_provider,
        action_outcome_provider=lambda prompt, **kwargs: json.dumps(
            {
                "outcome": outcome,
                "location_change": False,
                "evidence": ["The result is not a successful action."],
            }
        ),
        location_exploration_coordinator=coordinator,
    )

    graph = await explorer.explore_one_step()
    semantic, report = build_semantic_planning_graph(graph)

    assert semantic.actions == []
    assert report.excluded_edges[0]["reason"] in {
        "failed_execution",
        "non_projectable_status",
    }


@pytest.mark.anyio
async def test_real_location_change_same_page_type_uses_one_new_location_anchor():
    adapter = CheckoutDependencyAdapter(after_page_id="checkout")
    memory = LocationExplorationMemory()
    coordinator = LocationExplorationCoordinator(memory=memory)
    candidate_locations = []
    outcome_calls = []

    def candidate_provider(prompt, **kwargs):
        location = "checkout" if not candidate_locations else "order_review"
        candidate_locations.append(location)
        if location == "checkout":
            return _checkout_dependency_candidate_provider(prompt, **kwargs)
        return json.dumps(
            {
                "location_id": location,
                "actions": [
                    {
                        "action_id": "target_location_action",
                        "description": "Use the action on the new location.",
                        "target": "New location control",
                        "requires": [],
                    }
                ],
            }
        )

    def outcome_provider(prompt, **kwargs):
        outcome_calls.append(kwargs)
        return json.dumps(
            {
                "outcome": "success",
                "location_change": len(outcome_calls) == 1,
                "evidence": ["The active interface was observed."],
            }
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=outcome_provider,
        location_exploration_coordinator=coordinator,
    )

    graph = await explorer.explore_one_step()
    semantic, _ = build_semantic_planning_graph(graph)
    edge = graph.edges[0]
    target_node = next(
        node for node in graph.nodes if node.node_id == edge.target_node_id
    )
    target_location = semantic.actions[0].target_location
    anchored_location, unresolved = _semantic_location_anchor(target_node)

    assert edge.semantic_observation.target_location == target_location
    assert target_location != "checkout"
    assert target_node.semantic_location_hint == target_location
    assert unresolved is False
    assert anchored_location == target_location
    assert explorer._current_node_id == edge.target_node_id
    assert target_location in memory.locations
    assert candidate_locations == ["checkout", target_location]

    await explorer.explore_one_step()
    assert adapter.executed[1].semantic_id == "target_location_action"
    assert candidate_locations == ["checkout", target_location]


class ReplayHandoffUrlAdapter:
    app_name = "replay_handoff_fixture"

    def __init__(self):
        self.executed = []
        self.states = [
            StateSnapshot(
                page_id="cart",
                url="https://example.test/cart.html",
                title="Cart",
                signature={"surface": "cart"},
            ),
            StateSnapshot(
                page_id="listing_changed",
                url="https://example.test/inventory.html?sort=price",
                title="Products",
                signature={"surface": "filtered_listing"},
            ),
        ]

    async def reset_to(self, url):
        return True

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        return []

    async def execute(self, action):
        self.executed.append(action)
        return True

    async def capture_screenshot(self, label):
        return f"{label}.png"


@pytest.mark.anyio
async def test_replay_handoff_reuses_unique_url_location_without_rescanning():
    adapter = ReplayHandoffUrlAdapter()
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "cart_page",
        [BusinessAffordance("continue_shopping")],
    )
    memory.merge_scan(
        "product_catalog",
        [BusinessAffordance("view_cart")],
    )
    memory.pool_for("product_catalog").candidates["view_cart"].status = "success"
    coordinator = LocationExplorationCoordinator(memory=memory)
    scan_calls = []

    def candidate_provider(prompt, **kwargs):
        scan_calls.append(json.loads(prompt))
        return json.dumps(
            {
                "location_id": "product_listing_page",
                "actions": [
                    {
                        "action_id": "view_cart",
                        "description": "Open the cart.",
                        "target": "Cart button",
                        "requires": [],
                    }
                ],
            }
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=lambda prompt, **kwargs: json.dumps(
            {
                "outcome": "success",
                "location_change": True,
                "evidence": ["The cart returned to the product listing."],
            }
        ),
        location_exploration_coordinator=coordinator,
    )
    login = replace(
        _selection_node("login"),
        semantic_location_hint="login_form",
    )
    cart = replace(
        _selection_node(
            "cart",
            business_affordances=[BusinessAffordance("continue_shopping")],
        ),
        page_frame=replace(
            _selection_node("cart").page_frame,
            url="https://example.test/cart.html",
            url_pattern="https://example.test/cart.html",
        ),
        semantic_location_hint="cart_page",
    )
    product = replace(
        _selection_node(
            "product_old",
            business_affordances=[BusinessAffordance("view_cart")],
        ),
        page_frame=replace(
            _selection_node("product_old").page_frame,
            url="https://example.test/inventory.html",
            url_pattern="https://example.test/inventory.html",
        ),
        semantic_location_hint="product_catalog",
    )
    graph = WebKobeGraph(
        app=adapter.app_name,
        start_node_id="login",
        total_steps_completed=0,
        nodes=[login, cart, product],
        edges=[],
    )
    memory.sync_graph_meta(graph)
    explorer.restore_graph(graph)
    target = type(
        "Target",
        (),
        {"node_id": "cart", "path": (), "semantic_location": "cart_page"},
    )()

    replay_result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://example.test/",
    )
    result = await explorer.explore_one_step()

    assert replay_result.success is True
    assert adapter.executed[0].semantic_id == "continue_shopping"
    assert scan_calls == []
    assert "product_listing_page" not in memory.locations
    edge = result.execution_events[-1]
    assert edge.semantic_observation.target_location == "product_catalog"


class OutcomeTargetChangeAdapter:
    app_name = "outcome_target_change_fixture"

    def __init__(self):
        self.states = [
            StateSnapshot(
                page_id="listing",
                url="https://example.test/listing",
                title="Listing",
                signature={"surface": "listing"},
            ),
            StateSnapshot(
                page_id="checkout",
                url="https://example.test/checkout",
                title="Checkout",
                signature={"surface": "checkout"},
            ),
        ]
        self.executed = []

    async def observe_state(self):
        return self.states[min(len(self.executed), 1)]

    async def list_interactables(self, state):
        action_id = "open_checkout" if not self.executed else "fill_billing"
        return [
            {
                "semantic_id": action_id,
                "description": action_id.replace("_", " "),
                "locator": f"button.{action_id}",
                "action_kind": "click",
                "explored": False,
            }
        ]

    async def execute(self, action):
        self.executed.append(action)
        return True

    async def capture_screenshot(self, label):
        return f"{label}-{len(self.executed)}.png"


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["failed", "uncertain"])
async def test_failed_or_uncertain_outcome_cannot_be_promoted_to_navigation(outcome):
    adapter = OutcomeTargetChangeAdapter()
    coordinator = LocationExplorationCoordinator(memory=LocationExplorationMemory())

    scan_locations = []

    def candidate_provider(prompt, **kwargs):
        scan_locations.append("listing")
        action_id = "open_checkout"
        return json.dumps(
            {
                "location_id": "listing",
                "actions": [
                    {
                        "action_id": action_id,
                        "description": action_id.replace("_", " "),
                        "target": f"{action_id} control",
                        "requires": [],
                    }
                ],
            }
        )

    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        business_profile=None,
        capture_screenshots=True,
        visual_delta_provider=candidate_provider,
        action_outcome_provider=lambda prompt, **kwargs: json.dumps(
            {
                "outcome": outcome,
                "location_change": True,
                "evidence": ["The target state changed but outcome is not success."],
            }
        ),
        location_exploration_coordinator=coordinator,
    )

    graph = await explorer.explore_one_step()
    edge = graph.edges[0]
    semantic, report = build_semantic_planning_graph(graph)

    assert edge.status == (
        "failed_execution" if outcome == "failed" else "no_observed_change"
    )
    assert edge.status not in {
        "succeeded_with_navigation",
        "succeeded_with_observed_change",
    }
    assert semantic.actions == []
    assert report.excluded_edges
    assert set(coordinator.memory.locations) == {"listing"}
    assert scan_locations == ["listing"]
    assert explorer._current_node_id == edge.source_node_id
    source_anchor, unresolved = _semantic_location_anchor(
        explorer.manager.node_for_id(edge.source_node_id)
    )
    assert source_anchor == "listing"
    assert unresolved is False
    assert graph.meta["last_step_kind"] not in {
        "location_transition",
        "initial_location_scan",
    }
    assert graph.meta["last_step_semantic_progress"] is False


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
    embedding_node_ids = {record.node_id for record in explorer.state_embedding_records}
    assert graph_node_ids <= embedding_node_ids
