"""Public API for the DOM-grounded web exploration mainline.

This package is the stable import surface for the current generic exploration
direction. It owns browser-grounded observation, action extraction, execution
adapters, exploration control, and the Web-KOBE exploration graph. SafeSym/PDDL
conversion should consume this package's graph outputs from `safesym_bridge`,
not the other way around.
"""

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
    PlanningState,
    PlanningTransition,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceProvider,
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.exploration_semantics import (
    ActionContract,
    FactEvidenceRule,
    GeneratedCheckoutData,
    SemanticExperimentProfile,
    generate_checkout_test_data,
    practice_shopping_feasibility_profile,
    resolve_semantic_experiment_profile,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeGraph,
)
from ai_web_explorer.grounded_web.openai_visual_delta import (
    DEFAULT_OPENAI_ACTION_OUTCOME_MODEL,
    DEFAULT_OPENAI_VISUAL_DELTA_MODEL,
    OpenAIVisualDeltaProvider,
    create_openai_action_outcome_provider_from_env,
    create_openai_visual_delta_provider_from_env,
)
from ai_web_explorer.grounded_web.planning_fact_verifier import (
    verify_experiment_planning_delta,
    verify_planning_delta,
)
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.visual_delta import (
    VisualDeltaProvider,
    VisualDeltaRequest,
    summarize_visual_delta,
)

__all__ = [
    "AutomationBackend",
    "ActionContract",
    "BrowserAction",
    "BusinessAffordance",
    "BusinessFlowProfile",
    "DEFAULT_OPENAI_ACTION_OUTCOME_MODEL",
    "DEFAULT_OPENAI_VISUAL_DELTA_MODEL",
    "FactEvidenceRule",
    "GeneratedCheckoutData",
    "OpenAIVisualDeltaProvider",
    "PlanningDelta",
    "PlanningState",
    "PlanningTransition",
    "SemanticExperimentProfile",
    "VisualAffordanceProvider",
    "VisualAffordanceRequest",
    "VisualDeltaProvider",
    "VisualDeltaRequest",
    "WebKobeExplorationController",
    "WebKobeExplorationResult",
    "WebKobeExplorationSummary",
    "WebKobeExplorer",
    "WebKobeGraph",
    "WebKobePlaywrightAdapter",
    "create_openai_visual_delta_provider_from_env",
    "create_openai_action_outcome_provider_from_env",
    "ecommerce_checkout_profile",
    "generate_checkout_test_data",
    "practice_shopping_feasibility_profile",
    "resolve_semantic_experiment_profile",
    "summarize_visual_affordances",
    "summarize_visual_delta",
    "verify_planning_delta",
    "verify_experiment_planning_delta",
]
