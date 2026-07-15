from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.web_kobe_graph import BrowserAction

InteractableRecord = dict[str, Any]


@runtime_checkable
class AutomationBackend(Protocol):
    """Browser operation boundary used by Web-KOBE exploration.

    Implementations operate the browser. They do not own exploration strategy,
    graph recording, state-delta inference, or SafeSym/PDDL projection.
    """

    app_name: str

    async def observe_state(self) -> StateSnapshot:
        ...

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[InteractableRecord]:
        ...

    async def execute(self, action: BrowserAction) -> bool:
        ...
