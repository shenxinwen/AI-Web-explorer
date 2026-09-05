from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ai_web_explorer.grounded_web.risk_detection import (
    RISK_ASSESSMENT_SYSTEM_PROMPT,
    RiskAssessment,
    RiskDetectionRequest,
    render_risk_assessment_user_prompt,
)


DEFAULT_OPENAI_RISK_DETECTION_MODEL = "gpt-4o"


def _image_data_url(path: str | Path) -> str:
    image_path = Path(path)
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@dataclass(frozen=True)
class OpenAIRiskDetectionProvider:
    client: Any
    model: str = DEFAULT_OPENAI_RISK_DETECTION_MODEL
    temperature: float = 0
    max_tokens: int = 300

    def __call__(self, request: RiskDetectionRequest) -> RiskAssessment:
        prompt = render_risk_assessment_user_prompt(
            request.candidate_label, request.taxonomy
        )
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RISK_ASSESSMENT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _image_data_url(request.screenshot_path),
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "OpenAI risk detection provider returned an empty response."
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(
                "OpenAI risk detection provider returned invalid JSON."
            ) from error
        if not isinstance(payload, Mapping):
            raise ValueError("OpenAI risk detection response must be a JSON object.")
        return RiskAssessment.from_dict(payload, taxonomy=request.taxonomy)


def create_openai_risk_detection_provider_from_env(
    *,
    model: str | None = None,
    request_timeout_seconds: float | None = None,
    openai_factory: Callable[..., Any] | None = None,
    load_dotenv: Callable[[], Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> OpenAIRiskDetectionProvider:
    if load_dotenv is None:
        from dotenv import load_dotenv as load_dotenv

    load_dotenv()
    env = os.environ if environ is None else environ
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI risk detection.")

    if openai_factory is None:
        import openai

        openai_factory = openai.OpenAI

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": env.get("OPENAI_BASE_URL") or None,
    }
    if request_timeout_seconds is not None:
        client_kwargs["timeout"] = request_timeout_seconds
    return OpenAIRiskDetectionProvider(
        client=openai_factory(**client_kwargs),
        model=(
            model
            or env.get("OPENAI_RISK_DETECTION_MODEL")
            or env.get("OPENAI_VISION_MODEL")
            or DEFAULT_OPENAI_RISK_DETECTION_MODEL
        ),
    )


__all__ = [
    "DEFAULT_OPENAI_RISK_DETECTION_MODEL",
    "OpenAIRiskDetectionProvider",
    "create_openai_risk_detection_provider_from_env",
]
