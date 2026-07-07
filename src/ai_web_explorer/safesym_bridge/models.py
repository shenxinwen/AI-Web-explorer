from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Condition = dict[str, Any]
Effect = dict[str, Any]

# 用于描述浏览器观察到的页面状态。
@dataclass(frozen=True)
class StateSnapshot:
    page_id: str  # 当前页面，例如 login、inventory、cart。
    url: str
    title: str
    signature: dict[str, Any]  # 描述状态事实的键值对。


@dataclass(frozen=True)
class ObservedAction:
    raw_description: str
    semantic_id: str
    playwright_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ObservedTransition:
    source: StateSnapshot
    target: StateSnapshot
    action: ObservedAction
    preconditions: list[Condition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)