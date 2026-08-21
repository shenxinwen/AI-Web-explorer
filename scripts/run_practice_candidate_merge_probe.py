from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.grounded_web.business_affordance import (
    VisualAffordanceRequest,
    summarize_visual_affordances,
)
from ai_web_explorer.grounded_web.openai_visual_delta import (
    create_openai_visual_delta_provider_from_env,
)


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = (
    ROOT
    / "outputs/experiments/practice_automated_testing/latest/screenshots/before_0001.png"
)
OUTPUT = (
    ROOT
    / "outputs/experiments/practice_automated_testing/candidate_merge_prompt_v5_gpt4o"
)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing experiment: {OUTPUT}")
    if not SCREENSHOT.is_file():
        raise FileNotFoundError(SCREENSHOT)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    provider = create_openai_visual_delta_provider_from_env(
        model="gpt-4o",
        request_timeout_seconds=90,
    )
    observations: list[dict[str, object]] = []
    for repetition in range(1, 4):
        result = summarize_visual_affordances(
            VisualAffordanceRequest(
                goal="Explore visible website functionality.",
                current_screenshot_path=str(SCREENSHOT),
                max_actions=8,
            ),
            provider=provider,
        )
        observations.append(
            {
                "repetition": repetition,
                "location_id": result.location_id,
                "actions": [
                    {
                        "action_id": action.action_name,
                        "description": action.label,
                        "target": action.target_hint,
                        "requires": result.requires_by_action_id.get(
                            action.action_name, []
                        ),
                    }
                    for action in result.business_affordances
                ],
                "trace": result.trace.to_dict(),
            }
        )
        print(repetition, result.trace.status, result.location_id)

    (OUTPUT / "candidate_observations.json").write_text(
        json.dumps(
            {
                "purpose": "representative-action merge prompt probe",
                "screenshot": str(SCREENSHOT.relative_to(ROOT)),
                "model": provider.model,
                "temperature": provider.temperature,
                "observations": observations,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
