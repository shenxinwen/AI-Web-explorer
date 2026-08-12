import json

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"

from ai_web_explorer.grounded_web.controller import WebKobeExplorationController
from ai_web_explorer.grounded_web.exploration_semantics import (
    practice_shopping_feasibility_profile,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import (
    FrontierReplayRunner,
    FrontierTarget,
)
from ai_web_explorer.grounded_web.graph import BusinessAffordance
from ai_web_explorer.grounded_web.location_exploration import (
    ExplorationLimits,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.grounded_web.semantic_planning import (
    build_semantic_planning_graph,
)
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
)


class _FeasibilityFixtureAdapter:
    app_name = "practice_fixture"

    def __init__(self) -> None:
        self.location = "shopping"
        self.executed: list[str] = []
        self.last_execution_error = None
        self._facts = {
            "cart_has_items": False,
            "checkout_info_complete": False,
            "payment_info_complete": False,
            "order_submitted": False,
        }

    async def observe_state(self) -> StateSnapshot:
        signature = dict(self._facts)
        signature.update(
            {
                "cart_count": 1 if self._facts["cart_has_items"] else 0,
                "products_sorted": "sort_products" in self.executed,
                "products_filtered": "filter_products" in self.executed,
            }
        )
        return StateSnapshot(
            page_id=self.location,
            url=f"https://fixture.test/{self.location}",
            title=self.location.title(),
            signature=signature,
        )

    async def list_interactables(self, state: StateSnapshot) -> list[dict[str, object]]:
        return []

    async def capture_screenshot(self, label: str) -> str:
        return f"{label}.png"

    async def execute(self, action) -> bool:
        action_id = action.canonical_action_name or action.semantic_id
        self.executed.append(action_id)
        if action_id == "add_to_cart":
            self._facts["cart_has_items"] = True
        elif action_id == "open_checkout":
            self.location = "checkout"
        elif action_id == "complete_checkout_information":
            self._facts["checkout_info_complete"] = True
        elif action_id == "complete_payment_information":
            self._facts["payment_info_complete"] = True
        elif action_id == "place_order":
            self._facts["order_submitted"] = True
            self.location = "confirmation"
        return True

    async def reset_to(self, url: str) -> bool:
        self.location = "shopping"
        self.executed.clear()
        for key in self._facts:
            self._facts[key] = False
        return True


def _affordance(action_id: str) -> BusinessAffordance:
    return BusinessAffordance(
        action_name=action_id,
        label=action_id.replace("_", " "),
        relevance_hint="core",
        confidence=0.9,
    )


def _fixture_memory() -> LocationExplorationMemory:
    memory = LocationExplorationMemory(limits=ExplorationLimits())
    memory.merge_scan(
        "shopping",
        [
            _affordance("sort_products"),
            _affordance("filter_products"),
            _affordance("add_to_cart"),
        ],
        kind="initial",
    )
    memory.merge_scan(
        "checkout",
        [
            _affordance("complete_checkout_information"),
            _affordance("complete_payment_information"),
            _affordance("place_order"),
        ],
        kind="initial",
    )
    memory.merge_scan("confirmation", [], kind="initial")
    memory.pool_for("confirmation").supplement_scan_complete = True
    for location_id in ("shopping", "checkout", "confirmation"):
        memory.pool_for(location_id).initial_scan_complete = False
    for fact_id in (
        "checkout_info_complete",
        "payment_info_complete",
        "order_submitted",
    ):
        memory.mark_targeted_scan_complete(
            "checkout",
            added=[fact_id],
            removed=[],
        )
    return memory


def _fixture_provider(scan_calls: list[tuple[str, str]]):
    def provider(prompt: str, **kwargs) -> str:
        payload = json.loads(prompt)
        if "action" in payload:
            return _visual_delta_provider(prompt, **kwargs)
        scan_kind = payload.get("scan_kind", "initial")
        location = payload.get("semantic_location", "shopping")
        scan_calls.append((scan_kind, location))
        if scan_kind == "targeted":
            return json.dumps(
                {
                    "location_id": "shopping",
                    "newly_enabled": [
                        {
                            "intent": "open_checkout",
                            "label": "Open checkout",
                            "target": "checkout control",
                            "confidence": 0.9,
                            "supporting_facts": ["cart_has_items"],
                        }
                    ],
                }
            )
        initial_actions = {
            "shopping": ["sort_products", "filter_products", "add_to_cart"],
            "checkout": [
                "complete_checkout_information",
                "complete_payment_information",
                "place_order",
            ],
            "confirmation": [],
        }[location]
        return json.dumps(
            {
                "location_id": location,
                "regions": [
                    {
                        "actions": [
                            {
                                "intent": action_id,
                                "label": action_id.replace("_", " "),
                                "confidence": 0.9,
                            }
                            for action_id in initial_actions
                        ]
                    }
                ],
            }
        )

    return provider


def _visual_delta_provider(prompt: str, **kwargs) -> str:
    payload = json.loads(prompt)
    action_id = payload["action"]["canonical_action_name"]
    presentation = action_id in {"sort_products", "filter_products"}
    navigation = action_id == "open_checkout"
    commit = action_id == "place_order"
    added = {
        "add_to_cart": ["cart_has_items"],
        "complete_checkout_information": ["checkout_info_complete"],
        "complete_payment_information": ["payment_info_complete"],
        "place_order": ["order_submitted"],
    }.get(action_id, [])
    target = "checkout" if navigation else "confirmation" if commit else payload[
        "location_context"
    ]["source_location_hint"]
    completion_fact = {
        "sort_products": "products_sorted",
        "filter_products": "products_filtered",
    }.get(action_id)
    return json.dumps(
        {
            "candidate_added_facts": added,
            "candidate_removed_facts": [],
            "visual_change_kind": "presentation"
            if presentation
            else "surface"
            if navigation or commit
            else "state_indicator",
            "action_role": "presentation_capability"
            if presentation
            else "guarded_navigation"
            if navigation
            else "commit"
            if commit
            else "form_completion"
            if action_id.startswith("complete_")
            else "state_mutation",
            "source_location": payload["location_context"]["source_location_hint"],
            "target_location": target,
            "completion_facts": [completion_fact] if completion_fact else [],
            "candidate_required_facts": ["cart_has_items"] if navigation else [],
            "preserved_facts": [],
            "semantic_evidence": [f"Visible evidence for {action_id}."] ,
            "semantic_confidence": 0.9,
            "observable_change": True,
            "business_facts_added": added,
            "business_facts_removed": [],
        }
    )


def _action(domain: str, name: str) -> str:
    marker = f"(:action {name}"
    start = domain.index(marker)
    next_action = domain.find("  (:action ", start + len(marker))
    return domain[start : next_action if next_action >= 0 else domain.index("\n)", start)]


@pytest.mark.anyio
async def test_location_scoped_pipeline_reaches_confirmation_without_ordinary_dependencies():
    adapter = _FeasibilityFixtureAdapter()
    scan_calls: list[tuple[str, str]] = []
    profile = practice_shopping_feasibility_profile()
    fixture_provider = _fixture_provider(scan_calls)
    explorer = WebKobeExplorer(
        adapter=adapter,
        semantic_assistor=DeterministicSemanticAssistor(app=adapter.app_name),
        goal="Explore the controlled shopping fixture.",
        business_profile=profile.to_business_flow_profile(),
        capture_screenshots=True,
        visual_delta_provider=fixture_provider,
        exploration_limits=ExplorationLimits(),
        semantic_profile_context=profile.to_prompt_context(),
        location_exploration_coordinator=None,
    )
    explorer.location_exploration_coordinator.memory = _fixture_memory()
    explorer.location_exploration_coordinator.semantic_profile_context = (
        profile.to_prompt_context()
    )
    # The pre-seeded pools make this test exercise the same selection path as a
    # completed deterministic scan while the targeted scan remains provider-backed.
    explorer.visual_delta_provider = fixture_provider
    # Use the real scan provider for one initial scan per location and one
    # business-fact-triggered targeted scan.

    # The initial pools above are deterministic fixture state; this provider is
    # still used by the targeted scan and records its count.
    graph = (
        await WebKobeExplorationController(
            explorer,
            limits=ExplorationLimits(),
        ).run(max_steps=20)
    ).graph

    assert adapter.executed == [
        "sort_products",
        "filter_products",
        "add_to_cart",
        "open_checkout",
        "complete_checkout_information",
        "complete_payment_information",
        "place_order",
    ]
    semantic, report = build_semantic_planning_graph(graph)
    domain = compile_minimal_semantic_domain(semantic).domain
    problem = compile_minimal_semantic_problem(
        semantic,
        goal_location="confirmation",
        goal_facts=["order_submitted"],
    ).problem

    assert "(products_sorted)" in domain
    checkout = _action(domain, "open_checkout")
    preconditions = checkout.split(":precondition", 1)[1].split(":effect", 1)[0]
    assert "(cart_has_items)" in preconditions
    assert "products_sorted" not in preconditions
    assert "(at_confirmation)" in problem
    assert "(order_submitted)" in problem
    assert report.excluded_edges == []
    assert scan_calls == [
        ("initial", "shopping"),
        ("targeted", "shopping"),
        ("initial", "checkout"),
        ("initial", "confirmation"),
    ]

    memory = LocationExplorationMemory.from_graph(graph)
    assert all(
        record.attempts == 1
        for pool in memory.locations.values()
        for record in pool.candidates.values()
    )
    assert len(graph.edges) == 7
    assert len(graph.nodes) >= 3

    before_counts = (len(graph.nodes), len(graph.edges))
    replay = FrontierReplayRunner(explorer)
    replay_result = await replay.replay(
        FrontierTarget(
            node_id=explorer.start_node_id,
            path=(),
            untried_action_ids=(),
        ),
        start_url="https://fixture.test/shopping",
    )
    assert replay_result.success is True
    assert (len(graph.nodes), len(graph.edges)) == before_counts
