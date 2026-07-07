from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Condition = dict[str, Any]
Effect = dict[str, Any]

# 用于描述页面状态
@dataclass(frozen=True)
class StateSnapshot:
    page_id: str    # 当前页面（登录页、商品页、购物车页...)
    url: str
    title: str
    signature: dict[str, Any]   # 描述状态的键值对


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


@dataclass(frozen=True)
class SafeSymAction:
    id: str
    name: str
    from_page: str
    to_page: str
    is_navigation: bool
    preconditions: list[Condition] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "from": self.from_page,
            "to": self.to_page,
            "is_navigation": self.is_navigation,
            "preconditions": self.preconditions,
            "effects": self.effects,
        }


@dataclass(frozen=True)
class SafeSymPage:
    id: str
    signature_schema: dict[str, str]
    actions: list[SafeSymAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "signature_schema": self.signature_schema,
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class SafeSymFsm:
    app: str
    initial_page_id: str
    terminal_pages: list[str]
    pages: list[SafeSymPage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "app": self.app,
                "initial_page_id": self.initial_page_id,
                "terminal_pages": self.terminal_pages,
            },
            "pages": [page.to_dict() for page in self.pages],
        }
