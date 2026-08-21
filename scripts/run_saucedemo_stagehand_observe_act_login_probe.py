from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from stagehand import AsyncStagehand


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/experiments/saucedemo/stagehand_observe_act_login_probe_v1"
START_URL = "https://www.saucedemo.com/"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


async def _observe_and_act(session: Any, instruction: str) -> dict[str, Any]:
    started = time.perf_counter()
    observed = await session.observe(instruction=instruction)
    observe_seconds = time.perf_counter() - started
    actions = list(observed.data.result)
    if not actions:
        raise RuntimeError(f"observe returned no actions: {instruction}")
    action = actions[0]
    action_input = _jsonable(action)
    started = time.perf_counter()
    acted = await session.act(input=action_input)
    act_seconds = time.perf_counter() - started
    return {
        "instruction": instruction,
        "candidate_count": len(actions),
        "selected_action": action_input,
        "observe_seconds": observe_seconds,
        "act_seconds": act_seconds,
        "act_success": bool(acted.success),
        "act_result": _jsonable(acted.data.result),
    }


async def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing experiment: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    load_dotenv(ROOT / ".env")
    model_name = os.environ.get("STAGEHAND_PROBE_MODEL") or os.environ["STAGEHAND_MODEL"]
    server = os.environ.get("STAGEHAND_SERVER", "local").lower()
    if server != "local":
        raise RuntimeError("this probe is intentionally restricted to local Stagehand")

    provider_name = model_name.split("/", 1)[0].lower()
    key_name = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
    }.get(provider_name)
    if key_name is None or not os.environ.get(key_name):
        raise RuntimeError(f"no configured API key for Stagehand provider: {provider_name}")
    client = AsyncStagehand(model_api_key=os.environ[key_name], server="local")
    session = await client.sessions.start(
        model_name=model_name,
        browser={"type": "local", "launch_options": {"headless": True}},
        verbose=1,
    )
    report: dict[str, Any] = {"model": model_name, "server": server, "steps": []}
    try:
        await session.navigate(url=START_URL)
        credential_response = await session.extract(
            instruction=(
                "Read the public test login information visibly printed on this "
                "page. Return the first accepted username and the password."
            ),
            schema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                },
                "required": ["username", "password"],
                "additionalProperties": False,
            },
        )
        credentials = dict(credential_response.data.result)
        username = str(credentials.get("username", "")).strip()
        password = str(credentials.get("password", "")).strip()
        if not username or not password:
            raise RuntimeError("Stagehand did not extract both public credentials")
        report["credentials_extracted"] = True
        report["credential_lengths"] = {
            "username": len(username),
            "password": len(password),
        }

        report["steps"].append(
            await _observe_and_act(
                session,
                f"Fill the Username input with {username}",
            )
        )
        report["steps"].append(
            await _observe_and_act(
                session,
                f"Fill the Password input with {password}",
            )
        )
        report["steps"].append(
            await _observe_and_act(session, "Click the Login button")
        )

        page_response = await session.extract(
            instruction=(
                "Identify the current active page after the login attempt and "
                "state whether a product inventory list is visible."
            ),
            schema={
                "type": "object",
                "properties": {
                    "page_name": {"type": "string"},
                    "product_inventory_visible": {"type": "boolean"},
                },
                "required": ["page_name", "product_inventory_visible"],
                "additionalProperties": False,
            },
        )
        report["final_observation"] = _jsonable(page_response.data.result)
        report["login_success"] = bool(
            report["final_observation"].get("product_inventory_visible")
        )
    finally:
        await session.end()
        await client.close()

    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
