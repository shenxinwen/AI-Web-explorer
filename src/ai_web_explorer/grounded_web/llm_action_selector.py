from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from ai_web_explorer.grounded_web.graph import BrowserAction
from ai_web_explorer.grounded_web.models import StateSnapshot

LlmSelectionProvider = Callable[[str], str]


@dataclass(frozen=True)
class LlmActionSelectionRequest:
    goal: str
    state: StateSnapshot
    candidate_actions: list[BrowserAction]


@dataclass(frozen=True)
class LlmActionSelectionTrace:
    goal: str
    state: dict[str, Any]
    candidate_actions: list[dict[str, Any]]
    prompt: str
    raw_response: str
    llm_response: dict[str, Any] | None
    status: str
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "state": dict(self.state),
            "candidate_actions": [dict(item) for item in self.candidate_actions],
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "llm_response": (
                dict(self.llm_response) if self.llm_response is not None else None
            ),
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class LlmActionSelectionResult:
    selected_action: BrowserAction | None
    trace: LlmActionSelectionTrace


def _state_payload(state: StateSnapshot) -> dict[str, Any]:
    return {
        "page_id": state.page_id,
        "url": state.url,
        "title": state.title,
        "signature": dict(state.signature),
    }


def _action_payload(action: BrowserAction) -> dict[str, Any]:
    return {
        "id": action.semantic_id,
        "kind": action.action_kind,
        "description": action.description,
        "locator": action.locator,
        "input_values": dict(action.input_values),
    }


def _prompt_for_request(request: LlmActionSelectionRequest) -> str:
    payload = {
        "instruction": (
            "Select exactly one action id from candidate_actions. "
            "Return JSON only with selected_action_id, confidence, and reason. "
            "Do not invent selectors or action ids."
        ),
        "goal": request.goal,
        "current_state": _state_payload(request.state),
        "candidate_actions": [
            _action_payload(action) for action in request.candidate_actions
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _trace(
    request: LlmActionSelectionRequest,
    *,
    prompt: str,
    raw_response: str = "",
    llm_response: dict[str, Any] | None = None,
    status: str,
    error_type: str | None = None,
    error_message: str | None = None,
) -> LlmActionSelectionTrace:
    return LlmActionSelectionTrace(
        goal=request.goal,
        state=_state_payload(request.state),
        candidate_actions=[
            _action_payload(action) for action in request.candidate_actions
        ],
        prompt=prompt,
        raw_response=raw_response,
        llm_response=llm_response,
        status=status,
        error_type=error_type,
        error_message=error_message,
    )


def select_action_with_llm(
    request: LlmActionSelectionRequest,
    *,
    provider: LlmSelectionProvider,
) -> LlmActionSelectionResult:
    prompt = _prompt_for_request(request)
    if not request.candidate_actions:
        return LlmActionSelectionResult(
            selected_action=None,
            trace=_trace(
                request,
                prompt=prompt,
                status="failed",
                error_type="no_candidates",
                error_message="No candidate actions were available.",
            ),
        )

    raw_response = provider(prompt)
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as error:
        return LlmActionSelectionResult(
            selected_action=None,
            trace=_trace(
                request,
                prompt=prompt,
                raw_response=raw_response,
                status="failed",
                error_type="parse_error",
                error_message=str(error),
            ),
        )

    if not isinstance(parsed, dict):
        return LlmActionSelectionResult(
            selected_action=None,
            trace=_trace(
                request,
                prompt=prompt,
                raw_response=raw_response,
                llm_response={"value": parsed},
                status="failed",
                error_type="parse_error",
                error_message="LLM response must be a JSON object.",
            ),
        )

    selected_action_id = str(parsed.get("selected_action_id") or "")
    actions_by_id = {action.semantic_id: action for action in request.candidate_actions}
    selected = actions_by_id.get(selected_action_id)
    if selected is None:
        return LlmActionSelectionResult(
            selected_action=None,
            trace=_trace(
                request,
                prompt=prompt,
                raw_response=raw_response,
                llm_response=parsed,
                status="failed",
                error_type="invalid_action",
                error_message=f"Action id is not a candidate: {selected_action_id}",
            ),
        )

    return LlmActionSelectionResult(
        selected_action=selected,
        trace=_trace(
            request,
            prompt=prompt,
            raw_response=raw_response,
            llm_response=parsed,
            status="selected",
        ),
    )
