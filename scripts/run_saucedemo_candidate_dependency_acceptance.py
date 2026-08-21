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
SCREENSHOTS = (
    ROOT
    / "outputs/experiments/saucedemo/static_semantic_input_v1/screenshots"
)
OUTPUT = (
    ROOT
    / "outputs/experiments/saucedemo/candidate_dependency_acceptance_v1_gpt4o"
)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing experiment: {OUTPUT}")
    screenshots = sorted(SCREENSHOTS.glob("*.png"), key=lambda path: int(path.stem))
    if not screenshots:
        raise FileNotFoundError(f"no PNG screenshots found in {SCREENSHOTS}")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    provider = create_openai_visual_delta_provider_from_env(
        model="gpt-4o",
        request_timeout_seconds=90,
    )
    observations: list[dict[str, object]] = []
    for screenshot in screenshots:
        result = summarize_visual_affordances(
            VisualAffordanceRequest(
                goal="Explore visible website functionality.",
                current_screenshot_path=str(screenshot),
                max_actions=8,
            ),
            provider=provider,
        )
        observations.append(
            {
                "screenshot": str(screenshot.relative_to(ROOT)),
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
        print(screenshot.name, result.trace.status, result.location_id)

    (OUTPUT / "candidate_observations.json").write_text(
        json.dumps(
            {
                "experiment_kind": "independent_screenshot_candidate_dependency",
                "sequence_assumed": False,
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
