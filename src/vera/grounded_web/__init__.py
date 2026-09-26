"""Core interface observation, functional verification, and exploration components."""

from vera.grounded_web.automation_backend import AutomationBackend
from vera.grounded_web.business_profile import (
    BusinessFlowProfile,
    PlanningDelta,
    PlanningState,
    PlanningTransition,
    ecommerce_checkout_profile,
)
from vera.grounded_web.business_affordance import (
    VisualAffordanceProvider,
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from vera.grounded_web.controller import (
    WebKobeExplorationController,
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from vera.grounded_web.explorer import WebKobeExplorer
from vera.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeGraph,
)
from vera.grounded_web.openai_visual_delta import (
    DEFAULT_OPENAI_ACTION_OUTCOME_MODEL,
    DEFAULT_OPENAI_VISUAL_DELTA_MODEL,
    OpenAIVisualDeltaProvider,
    create_openai_action_outcome_provider_from_env,
    create_openai_visual_delta_provider_from_env,
)
from vera.grounded_web.planning_fact_verifier import verify_planning_delta
from vera.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from vera.grounded_web.risk_detection import (
    DEFAULT_RISK_TAXONOMY_PATH,
    RISK_ASSESSMENT_SYSTEM_PROMPT,
    RiskAssessment,
    RiskCategory,
    RiskDetectionRequest,
    RiskTaxonomy,
    load_risk_taxonomy,
    render_risk_assessment_user_prompt,
    summarize_risk_assessments,
)
from vera.grounded_web.openai_risk_detection import (
    DEFAULT_OPENAI_RISK_DETECTION_MODEL,
    OpenAIRiskDetectionProvider,
    create_openai_risk_detection_provider_from_env,
)
from vera.grounded_web.visual_delta import (
    VisualDeltaProvider,
    VisualDeltaRequest,
    summarize_visual_delta,
)

__all__ = [
    "AutomationBackend",
    "BrowserAction",
    "BusinessAffordance",
    "BusinessFlowProfile",
    "DEFAULT_OPENAI_ACTION_OUTCOME_MODEL",
    "DEFAULT_OPENAI_RISK_DETECTION_MODEL",
    "DEFAULT_OPENAI_VISUAL_DELTA_MODEL",
    "OpenAIVisualDeltaProvider",
    "OpenAIRiskDetectionProvider",
    "PlanningDelta",
    "PlanningState",
    "PlanningTransition",
    "DEFAULT_RISK_TAXONOMY_PATH",
    "RISK_ASSESSMENT_SYSTEM_PROMPT",
    "RiskAssessment",
    "RiskCategory",
    "RiskDetectionRequest",
    "RiskTaxonomy",
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
    "create_openai_risk_detection_provider_from_env",
    "ecommerce_checkout_profile",
    "load_risk_taxonomy",
    "render_risk_assessment_user_prompt",
    "summarize_visual_affordances",
    "summarize_visual_delta",
    "summarize_risk_assessments",
    "verify_planning_delta",
]
