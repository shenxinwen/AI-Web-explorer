import json
import pytest
from dataclasses import replace

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import (
    FrontierReplayRunner,
    ReplayStep,
    reachable_frontier_for_node,
    select_frontier,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.location_exploration import (
    LOCATION_EXPLORATION_META_KEY,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_assistor import DeterministicSemanticAssistor
from ai_web_explorer.grounded_web.risk_detection import RiskAssessment


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _node(node_id: str, *actions: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type=node_id,
            url=f"https://fixture.test/{node_id}",
            url_pattern=f"https://fixture.test/{node_id}",
            title=node_id,
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance(action) for action in actions],
    )


def _edge(
    source: str, target: str, action_id: str, *, success: bool = True
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_id,
        action=BrowserAction("click", f"#{action_id}", action_id),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click",
            f"#{action_id}",
            action_id,
            {},
            source,
            target,
            success,
        ),
        status="succeeded_with_navigation" if success else "failed_execution",
    )


def test_select_frontier_uses_shortest_reachable_path_deterministically():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start", "open_a", "open_b"),
            _node("a", "open_deep"),
            _node("b", "inspect_b"),
            _node("deep", "continue_deep"),
        ],
        edges=[
            _edge("start", "a", "open_a"),
            _edge("start", "b", "open_b"),
            _edge("a", "deep", "open_deep"),
        ],
    )

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "b"
    assert [step.edge_id for step in target.path] == [
        "start__open_b__b",
    ]
    assert target.untried_action_ids == ("inspect_b",)


def test_select_frontier_replay_path_includes_completed_same_location_requirements():
    login = replace(
        _node("login", "enter_credentials", "submit_login"),
        semantic_location_hint="login_form",
    )
    login_observation = replace(
        _node("login_observation"),
        semantic_location_hint="login_form",
    )
    product = replace(
        _node("product", "inspect_product"),
        semantic_location_hint="product_catalog",
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="login",
        total_steps_completed=2,
        nodes=[login, login_observation, product],
        edges=[
            _edge("login", "login_observation", "enter_credentials"),
            # The semantic-location anchor makes the navigation edge start at
            # the original login node, so raw BFS alone sees a false shortcut.
            _edge("login", "product", "submit_login"),
        ],
    )
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "login_form",
        [
            BusinessAffordance(
                "enter_credentials",
                label="Fill in the username and password fields.",
                target_hint="Username and Password fields",
                execution_policy="composite",
            ),
            BusinessAffordance("submit_login"),
        ],
        requires_by_action_id={"submit_login": ["enter_credentials"]},
    )
    memory.pool_for("login_form").candidates["enter_credentials"].status = "success"
    memory.pool_for("login_form").candidates["submit_login"].status = "success"
    memory.merge_scan(
        "product_catalog",
        [BusinessAffordance("inspect_product")],
    )
    memory.sync_graph_meta(graph)

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "product"
    assert [step.edge.action.semantic_id for step in target.path] == [
        "enter_credentials",
        "submit_login",
    ]
    assert target.path[0].edge.action.description == (
        "Fill in the username and password fields. "
        "Target: Username and Password fields."
    )
    assert target.path[0].edge.action.execution_policy == "composite"


def test_select_frontier_replay_path_omits_same_location_non_requirement():
    login = replace(_node("login"), semantic_location_hint="login_form")
    product = replace(_node("product"), semantic_location_hint="product_catalog")
    product_after_add = replace(
        _node("product_after_add"), semantic_location_hint="product_catalog"
    )
    cart = replace(
        _node("cart", "continue_shopping"), semantic_location_hint="cart_page"
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="login",
        total_steps_completed=3,
        nodes=[login, product, product_after_add, cart],
        edges=[
            _edge("login", "product", "submit_login"),
            _edge("product", "product_after_add", "add_to_cart"),
            _edge("product_after_add", "cart", "view_cart"),
        ],
    )
    memory = LocationExplorationMemory()
    memory.merge_scan("login_form", [BusinessAffordance("submit_login")])
    memory.pool_for("login_form").candidates["submit_login"].status = "success"
    memory.merge_scan(
        "product_catalog",
        [BusinessAffordance("add_to_cart"), BusinessAffordance("view_cart")],
    )
    memory.pool_for("product_catalog").candidates["add_to_cart"].status = "success"
    memory.pool_for("product_catalog").candidates["view_cart"].status = "success"
    memory.merge_scan("cart_page", [BusinessAffordance("continue_shopping")])
    memory.sync_graph_meta(graph)

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "cart"
    assert [step.edge.action.semantic_id for step in target.path] == [
        "submit_login",
        "view_cart",
    ]


def test_select_frontier_required_facts_use_verified_target_planning_state_only():
    target_node = replace(
        _node("target", "inspect_target"),
        business_affordances=[
            BusinessAffordance(
                "inspect_target",
                supporting_facts=["products_sorted", "invented_fact"],
            )
        ],
        planning_state=PlanningState(
            active_facts=["cart_has_items", "products_sorted"],
            profile_fact_ids=["cart_has_items"],
        ),
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_target"), target_node],
        edges=[_edge("start", "target", "open_target")],
    )

    target = select_frontier(graph)

    assert target is not None
    assert target.required_business_facts == ("cart_has_items",)


def test_select_frontier_does_not_use_failed_paths_or_blocked_frontiers():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=2,
        nodes=[
            _node("start", "open_bad"),
            _node("bad", "unsafe_action"),
            _node("good", "inspect_good"),
        ],
        edges=[
            _edge("start", "bad", "open_bad", success=False),
        ],
    )

    assert select_frontier(graph) is None

    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_good"), _node("good", "inspect_good")],
        edges=[_edge("start", "good", "open_good")],
    )
    assert select_frontier(graph, blocked_node_ids={"good"}) is None


def test_select_frontier_returns_none_when_all_candidates_are_exhausted():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_good"), _node("good", "inspect_good")],
        edges=[
            _edge("start", "good", "open_good"),
            _edge("good", "good", "inspect_good"),
        ],
    )

    assert select_frontier(graph) is None


def test_reachable_resume_frontier_respects_terminal_location_candidate_pool():
    target = replace(
        _node("product", "sort_products"),
        semantic_location_hint="product_catalog",
    )
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[_node("start", "open_product"), target],
        edges=[_edge("start", "product", "open_product")],
    )
    memory = LocationExplorationMemory()
    memory.merge_scan(
        "product_catalog",
        [BusinessAffordance("sort_products")],
    )
    record = memory.pool_for("product_catalog").candidates["sort_products"]
    record.status = "failed_retry_exhausted"
    record.attempts = memory.limits.max_action_attempts_per_candidate
    memory.sync_graph_meta(graph)

    result = reachable_frontier_for_node(
        graph,
        "product",
        action_eligible=lambda node_id, action_id: True,
    )

    assert result is None


def test_select_frontier_does_not_select_start_by_default():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[_node("start", "start_action")],
        edges=[],
    )

    assert select_frontier(graph) is None
    assert select_frontier(graph, include_start=True).node_id == "start"


def test_select_frontier_uses_one_global_bfs_parent_per_node_in_cycles():
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start"),
            _node("left"),
            _node("right"),
            _node("deep", "continue_deep"),
        ],
        edges=[
            _edge("start", "left", "open_left"),
            _edge("start", "right", "open_right"),
            _edge("left", "right", "cycle_to_right"),
            _edge("right", "deep", "open_deep"),
        ],
    )

    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "deep"
    assert [step.edge_id for step in target.path] == [
        "start__open_right__right",
        "right__open_deep__deep",
    ]


def test_select_frontier_excludes_unstable_paths_but_uses_stable_detour():
    unstable_edge = _edge("start", "bad", "open_bad")
    unstable_edge.execution_trace.metadata["replay_validation_status"] = "unstable"
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=3,
        nodes=[
            _node("start"),
            _node("bad"),
            _node("detour"),
            _node("frontier", "inspect_frontier"),
        ],
        edges=[
            unstable_edge,
            _edge("bad", "frontier", "continue_bad"),
        ],
    )

    assert select_frontier(graph) is None

    graph.edges.extend(
        [
            _edge("start", "detour", "open_detour"),
            _edge("detour", "frontier", "continue_detour"),
        ]
    )
    target = select_frontier(graph)

    assert target is not None
    assert target.node_id == "frontier"
    assert [step.edge_id for step in target.path] == [
        "start__open_detour__detour",
        "detour__continue_detour__frontier",
    ]


class _ReplayAdapter:
    app_name = "fixture"

    def __init__(self, states, *, failing_actions=()):
        self.states = list(states)
        self.index = 0
        self.reset_calls = []
        self.executed = []
        self.failing_actions = set(failing_actions)
        self.last_execution_error = None

    async def reset_to(self, url):
        self.reset_calls.append(url)
        self.index = 0
        return True

    async def observe_state(self):
        return self.states[self.index]

    async def list_interactables(self, state):
        return []

    async def capture_screenshot(self, label):
        return f"/tmp/{label}.png"

    async def execute(self, action):
        self.executed.append(action.semantic_id)
        if action.semantic_id in self.failing_actions:
            self.last_execution_error = "replay_failed"
            return False
        self.index = min(self.index + 1, len(self.states) - 1)
        return True


def _replay_node(node_id: str, state: str) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=state,
            page_type=state,
            url="https://fixture.test/shop",
            url_pattern="https://fixture.test/shop",
            title=state,
        ),
        state_schema={},
        last_state_snapshot={"surface": state},
    )


def _replay_step(source: str, target: str, action_id: str) -> ReplayStep:
    edge = _edge(source, target, action_id)
    return ReplayStep(
        edge_id=edge.edge_id,
        source_node_id=source,
        target_node_id=target,
        edge=edge,
    )


def _replay_explorer(adapter, *, risk_detection_provider=None):
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app="fixture"),
        business_profile=None,
        capture_screenshots=risk_detection_provider is not None,
        risk_detection_provider=risk_detection_provider,
    )
    explorer.manager.identify_or_add_node(_replay_node("start", "start"))
    explorer.manager.identify_or_add_node(_replay_node("target", "target"))
    explorer._start_node_id = "start"
    explorer._current_node_id = "start"
    return explorer


@pytest.mark.anyio
async def test_frontier_replay_runs_shadow_risk_detection_before_each_action():
    adapter = _ReplayAdapter(
        [
            StateSnapshot("start", "https://fixture.test/shop", "start", {}),
            StateSnapshot("target", "https://fixture.test/shop", "target", {}),
        ]
    )
    requests = []

    def risk_provider(request):
        assert adapter.executed == []
        requests.append(request)
        return RiskAssessment(
            True, "financial_transaction", "The action enters checkout."
        )

    explorer = _replay_explorer(adapter, risk_detection_provider=risk_provider)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_checkout"),),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target, start_url="https://fixture.test/shop"
    )

    assert result.success is True
    assert requests[0].candidate_label == "open_checkout"
    assert requests[0].screenshot_path.endswith("replay_before_0001.png")
    assert explorer.manager.meta["replay_risk_assessments"] == [
        {
            "action_id": "open_checkout",
            "candidate_label": "open_checkout",
            "screenshot_path": "/tmp/replay_before_0001.png",
            "risk_assessment": {
                "potential_risk": True,
                "risk_type": "financial_transaction",
                "evidence": "The action enters checkout.",
            },
        }
    ]


@pytest.mark.anyio
async def test_frontier_replay_risk_detection_failure_is_fail_open():
    adapter = _ReplayAdapter(
        [
            StateSnapshot("start", "https://fixture.test/shop", "start", {}),
            StateSnapshot("target", "https://fixture.test/shop", "target", {}),
        ]
    )

    def failing_provider(request):
        raise RuntimeError("risk service unavailable")

    explorer = _replay_explorer(adapter, risk_detection_provider=failing_provider)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target, start_url="https://fixture.test/shop"
    )

    assert result.success is True
    assert adapter.executed == ["open_target"]
    audit = explorer.manager.meta["replay_risk_assessments"][0]
    assert audit["risk_detection_error"] == {
        "type": "RuntimeError",
        "message": "risk service unavailable",
    }


@pytest.mark.anyio
async def test_frontier_replay_resets_executes_and_validates_without_graph_edges():
    adapter = _ReplayAdapter(
        [
            StateSnapshot(
                "start", "https://fixture.test/shop", "start", {"surface": "start"}
            ),
            StateSnapshot(
                "target", "https://fixture.test/shop", "target", {"surface": "target"}
            ),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()
    before_graph = explorer.manager.to_graph().to_dict()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is True
    assert result.reached_node_id == "target"
    assert result.completed_steps == 1
    assert adapter.reset_calls == ["https://fixture.test/shop"]
    assert adapter.executed == ["open_target"]
    assert explorer.manager.to_graph().to_dict() == before_graph


@pytest.mark.anyio
async def test_frontier_replay_does_not_mutate_edge_metadata_on_success_or_failure():
    adapter = _ReplayAdapter(
        [
            StateSnapshot(
                "start", "https://fixture.test/shop", "start", {"surface": "start"}
            ),
            StateSnapshot(
                "target", "https://fixture.test/shop", "target", {"surface": "target"}
            ),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
        },
    )()
    before = explorer.manager.to_graph().to_dict()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is True
    assert explorer.manager.to_graph().to_dict() == before


@pytest.mark.anyio
async def test_frontier_replay_does_not_require_intermediate_raw_nodes_to_match():
    adapter = _ReplayAdapter(
        [
            StateSnapshot(
                "start", "https://fixture.test/shop", "start", {"surface": "start"}
            ),
            StateSnapshot(
                "intermediate",
                "https://fixture.test/shop",
                "intermediate",
                {"surface": "intermediate"},
            ),
            StateSnapshot(
                "target", "https://fixture.test/shop", "target", {"surface": "target"}
            ),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (
                _replay_step("start", "unmodeled_intermediate", "open_intermediate"),
                _replay_step("unmodeled_intermediate", "target", "open_target"),
            ),
            "semantic_location": "target",
            "required_business_facts": (),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is True
    assert result.completed_steps == 2


@pytest.mark.anyio
async def test_frontier_replay_rejects_wrong_observed_target_state():
    adapter = _ReplayAdapter(
        [
            StateSnapshot(
                "start", "https://fixture.test/shop", "start", {"surface": "start"}
            ),
            StateSnapshot(
                "wrong", "https://fixture.test/shop", "wrong", {"surface": "wrong"}
            ),
        ]
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
            "semantic_location": "target",
            "required_business_facts": (),
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is False
    assert result.reached_node_id is None
    assert result.reason == "target_state_mismatch"


@pytest.mark.anyio
async def test_frontier_replay_stops_on_action_failure_without_observation():
    adapter = _ReplayAdapter(
        [
            StateSnapshot(
                "start", "https://fixture.test/shop", "start", {"surface": "start"}
            )
        ],
        failing_actions={"open_target"},
    )
    explorer = _replay_explorer(adapter)
    target = type(
        "Target",
        (),
        {
            "node_id": "target",
            "path": (_replay_step("start", "target", "open_target"),),
            "semantic_location": "target",
        },
    )()

    result = await FrontierReplayRunner(explorer).replay(
        target,
        start_url="https://fixture.test/shop",
    )

    assert result.success is False
    assert result.reason == "replay_action_failed"
    assert result.completed_steps == 0
    assert result.attempted_steps == 1
