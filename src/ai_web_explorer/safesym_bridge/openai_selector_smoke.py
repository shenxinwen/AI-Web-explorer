from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.llm_action_selector import (
    LlmSelectionProvider,
    LlmActionSelectionRequest,
    LlmActionSelectionResult,
    select_action_with_llm,
)
from ai_web_explorer.grounded_web.models import StateSnapshot
from ai_web_explorer.grounded_web.openai_action_selector import (
    create_openai_chat_selection_provider_from_env,
)


EXPECTED_ACTION_ID = "product_add_to_cart"


@dataclass(frozen=True)
class OpenAISelectorSmokeReport:
    expected_action_id: str
    selected_action_id: str | None
    selection_ready: bool
    failure_reason: str | None
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_action_id": self.expected_action_id,
            "selected_action_id": self.selected_action_id,
            "selection_ready": self.selection_ready,
            "failure_reason": self.failure_reason,
            "trace": dict(self.trace),
        }


@dataclass(frozen=True)
class OpenAISelectorSmokeResult:
    report: OpenAISelectorSmokeReport
    report_path: Path


def build_saucedemo_inventory_selection_request() -> LlmActionSelectionRequest:
    return LlmActionSelectionRequest(
        goal="Complete a SauceDemo checkout order.",
        state=StateSnapshot(
            page_id="inventory",
            url="https://www.saucedemo.com/inventory.html",
            title="Swag Labs",
            signature={
                "is_logged_in": True,
                "cart_count": 0,
                "order_created": False,
            },
        ),
        candidate_actions=[
            BrowserAction(
                action_kind="click",
                locator='[data-test="add-to-cart-sauce-labs-backpack"]',
                semantic_id="product_add_to_cart",
                description="Click Add to cart",
            ),
            BrowserAction(
                action_kind="click",
                locator=".shopping_cart_link",
                semantic_id="cart_open",
                description="Click the shopping cart link",
            ),
        ],
    )


def _report_from_result(
    result: LlmActionSelectionResult,
) -> OpenAISelectorSmokeReport:
    selected_action_id = (
        result.selected_action.semantic_id
        if result.selected_action is not None
        else None
    )
    selection_ready = selected_action_id == EXPECTED_ACTION_ID
    failure_reason = None
    if not selection_ready:
        failure_reason = result.trace.error_type or "wrong_action_selected"
    return OpenAISelectorSmokeReport(
        expected_action_id=EXPECTED_ACTION_ID,
        selected_action_id=selected_action_id,
        selection_ready=selection_ready,
        failure_reason=failure_reason,
        trace=result.trace.to_dict(),
    )


def write_openai_selector_smoke(
    output_path: Path,
    *,
    model: str | None = None,
    provider: LlmSelectionProvider | None = None,
) -> OpenAISelectorSmokeResult:
    output_path = output_path.resolve()
    request = build_saucedemo_inventory_selection_request()
    if provider is None:
        provider = create_openai_chat_selection_provider_from_env(model=model)
    result = select_action_with_llm(request, provider=provider)
    report = _report_from_result(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return OpenAISelectorSmokeResult(report=report, report_path=output_path)
