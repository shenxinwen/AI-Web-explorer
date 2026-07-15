from __future__ import annotations

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
    WebKobeExplorationResult,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
    SemanticAssistor,
)


class SimpleGroundedWebAgent:
    """No-LLM baseline agent for DOM-grounded web exploration.

    The agent is intentionally a facade over the existing Web-KOBE exploration
    engine. It does not own browser automation, selector generation, graph
    recording, or SafeSym/PDDL projection.
    """

    def __init__(
        self,
        backend: AutomationBackend,
        *,
        semantic_assistor: SemanticAssistor | None = None,
    ) -> None:
        self.backend = backend
        self.semantic_assistor = semantic_assistor or DeterministicSemanticAssistor(
            app=backend.app_name
        )
        self.explorer = WebKobeExplorer(
            adapter=backend,
            semantic_assistor=self.semantic_assistor,
        )
        self.controller = WebKobeExplorationController(self.explorer)

    async def run(self, *, max_steps: int = 1) -> WebKobeExplorationResult:
        return await self.controller.run(max_steps=max_steps)
