from ai_web_explorer.grounded_web.capability_graph import (
    AvailabilityCondition,
    Capability,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    ObservedDelta,
    PageFrame,
    StateIndicator,
)
from ai_web_explorer.grounded_web.graph import (
    ActionTarget,
    BusinessAffordance,
    BrowserAction,
    PddlActionHint,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.business_profile import PlanningTransition


def test_web_kobe_graph_serializes_node_edge_and_evidence():
    evidence = [Evidence(source="dom", selector="#login-button", confidence=1.0)]
    page_frame = PageFrame(
        page_id="example:login",
        page_type="login",
        url="https://example.test/login",
        url_pattern="https://example.test/login",
        title="Example Login",
        heading="Sign in",
        evidence=evidence,
    )
    capability = Capability(
        capability_id="submit_login_form",
        semantic_action="login_submit",
        action_kind="composite",
        target_type="form",
        target_role="login_form",
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            field_bindings={
                "username": "#user",
                "password": "#pass",
                "submit": "#login-button",
            },
        ),
        availability=AvailabilityCondition(required_page_type="login"),
        evidence=evidence,
    )
    node = WebKobeNode(
        node_id="n0_login",
        node_label="login_empty",
        state_summary="Login page before credentials are entered.",
        naming_provenance={"source": "unit_test"},
        page_description="login page",
        page_frame=page_frame,
        state_schema={"logged_in": [False]},
        last_state_snapshot={"logged_in": False},
        state_indicators=[
            StateIndicator("logged_in", False, "planning_state", evidence=evidence)
        ],
        planning_state=PlanningState(
            active_facts=["required_info_missing"],
            evidence=["unit test planning state"],
        ),
        action_targets=[
            ActionTarget(
                target_type="form",
                occurrence="single",
                role="login_form",
                structural_pattern="#login-form",
                representative_locator="#login-button",
                supported_capabilities=["submit_login_form"],
                evidence=evidence,
            )
        ],
        interactable_elements=[
            {
                "semantic_id": "login_submit",
                "description": "Login",
                "locator": "#login-button",
                "explored": False,
            }
        ],
        business_affordances=[
            BusinessAffordance(
                    action_name="submit_login_form",
                    relevance_hint="core",
                    target_hint="button labeled Login",
                    confidence=0.9,
                    supporting_facts=["login_form_visible"],
            )
        ],
        capabilities=[capability],
        reference_observation=ReferenceObservation(
            url="https://example.test/login",
            title="Example Login",
            screenshot_path=None,
            dom_summary="form#login-form",
            accessibility_summary="button Login",
        ),
        visit_count=1,
        evidence=evidence,
    )
    edge = WebKobeEdge(
        source_node_id="n0_login",
        target_node_id="n1_home",
        instruction="submit login form",
        action=BrowserAction(
            action_kind="composite",
            locator="#login-button",
            semantic_id="submit_login_form",
            action_label="Submit login form",
            canonical_action_name="login_submit",
            naming_provenance={"source": "unit_test"},
            input_values={"username": "standard_user", "password": "secret_sauce"},
            supporting_facts=["login_form_visible"],
        ),
        capability=capability,
        target_observation="home page",
        observed_delta=[
            ObservedDelta(
                "logged_in",
                False,
                True,
                "state_indicator_change",
                evidence=evidence,
            )
        ],
        schema_delta={"logged_in": {"before": False, "after": True}},
        execution_trace=ExecutionTrace(
            concrete_action_kind="composite",
            concrete_locator="#login-button",
            concrete_target_sample="form",
            input_values_used={"username": "standard_user", "password": "secret_sauce"},
            before_observation_id="n0_login",
            after_observation_id="n1_home",
            success=True,
            error=None,
        ),
        pddl_hint=PddlActionHint(
            action_name="submit_login_form",
            preconditions=["at_login"],
            add_effects=["logged_in", "at_home"],
            del_effects=["at_login"],
        ),
        planning_delta=PlanningDelta(
            candidate_added_facts=["logged_in"],
            verified_added_facts=["logged_in"],
            evidence=["login controls were replaced by shopping controls"],
            confidence=0.95,
        ),
        visual_change_kind="state_indicator",
        planning_transition=PlanningTransition(
            pre_facts=["required_info_missing"],
            added_facts=["logged_in"],
            removed_facts=["required_info_missing"],
            post_facts=["logged_in"],
            evidence=["login controls were replaced by shopping controls"],
            confidence=0.95,
        ),
        visit_count=1,
        status="verified",
        evidence=evidence,
    )
    graph = WebKobeGraph(
        app="example",
        start_node_id="n0_login",
        total_steps_completed=1,
        nodes=[node],
        edges=[edge],
        meta={"source": "unit_test"},
    )

    data = graph.to_dict()

    assert data["meta"]["schema_version"] == "web-kobe-graph-v1"
    assert data["meta"]["app"] == "example"
    assert data["nodes"][0]["node_label"] == "login_empty"
    assert (
        data["nodes"][0]["state_summary"]
        == "Login page before credentials are entered."
    )
    assert data["nodes"][0]["naming_provenance"] == {"source": "unit_test"}
    assert "interactable_elements" not in data["nodes"][0]
    assert data["nodes"][0]["planning_state"] == {
        "active_facts": ["required_info_missing"],
        "profile_fact_ids": [],
        "generated_fact_ids": [],
        "evidence": ["unit test planning state"],
    }
    assert "login_form_visible" not in data["nodes"][0]["planning_state"][
        "active_facts"
    ]
    assert data["edges"][0]["action"]["action_label"] == "Submit login form"
    assert data["edges"][0]["action"]["canonical_action_name"] == "login_submit"
    assert data["edges"][0]["action"]["supporting_facts"] == ["login_form_visible"]
    assert data["edges"][0]["action"]["naming_provenance"] == {"source": "unit_test"}
    assert data["nodes"][0]["action_targets"][0]["target_type"] == "form"
    assert data["nodes"][0]["business_affordances"] == [
        {
            "action_name": "submit_login_form",
            "label": None,
            "relevance_hint": "core",
            "target_hint": "button labeled Login",
            "source": "vlm",
            "confidence": 0.9,
            "supporting_facts": ["login_form_visible"],
        }
    ]
    assert data["nodes"][0]["capabilities"][0]["capability_id"] == "submit_login_form"
    assert data["edges"][0]["status"] == "verified"
    assert data["edges"][0]["pddl_hint"]["add_effects"] == ["logged_in", "at_home"]
    assert data["edges"][0]["planning_delta"]["verified_added_facts"] == ["logged_in"]
    assert data["edges"][0]["visual_change_kind"] == "state_indicator"
    assert data["edges"][0]["planning_transition"] == {
        "pre_facts": ["required_info_missing"],
        "added_facts": ["logged_in"],
        "removed_facts": ["required_info_missing"],
        "post_facts": ["logged_in"],
        "evidence": ["login controls were replaced by shopping controls"],
        "confidence": 0.95,
    }
    assert "business_transition" not in data["edges"][0]
