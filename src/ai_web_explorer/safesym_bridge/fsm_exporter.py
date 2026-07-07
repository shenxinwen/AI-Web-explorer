# 将收集到的数据整理成符合 SafeSym 的 fsm 格式
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ai_web_explorer.safesym_bridge.models import (
    ObservedTransition,
    SafeSymAction,
    SafeSymFsm,
    SafeSymPage,
)

# 分析变量类型，转成SafeSym的schema类型，主要是boolean、number、string三种类型
def schema_type_for(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "string"

# 按出现顺序记录页面，提高可读性
def _remember_page(page_id: str, page_order: list[str]) -> None:
    if page_id not in page_order:
        page_order.append(page_id)


def _collect_page_schemas(
    transitions: list[ObservedTransition],
) -> tuple[list[str], dict[str, dict[str, str]]]:
    page_order: list[str] = []      #存储页面出现顺序
    schemas: dict[str, dict[str, str]] = defaultdict(dict)

    for transition in transitions:
        _remember_page(transition.source.page_id, page_order)
        _remember_page(transition.target.page_id, page_order)

        for snapshot in (transition.source, transition.target):
            for path, value in snapshot.signature.items():
                # 设置状态变量--类型键值对，即signature_schemas
                schemas[snapshot.page_id][path] = schema_type_for(value)

        for effect in transition.effects:
            path = str(effect["path"])
            value = effect.get("value")
            value_type = schema_type_for(value)
            schemas[transition.source.page_id][path] = value_type
            schemas[transition.target.page_id][path] = value_type

    return page_order, {
        page_id: dict(sorted(schema.items())) for page_id, schema in schemas.items()
    }


def build_fsm(
    app: str,
    initial_page_id: str,
    terminal_pages: list[str],
    transitions: list[ObservedTransition],
) -> SafeSymFsm:
    page_order, schemas = _collect_page_schemas(transitions)
    actions_by_page: dict[str, list[SafeSymAction]] = defaultdict(list)

    # ObservedTransition → SafeSymAction
    for transition in transitions:
        action_id = transition.action.semantic_id
        actions_by_page[transition.source.page_id].append(
            # 生成动作对象
            SafeSymAction(
                id=action_id,
                name=action_id,
                from_page=transition.source.page_id,
                to_page=transition.target.page_id,
                is_navigation=transition.source.page_id != transition.target.page_id,
                preconditions=transition.preconditions,
                effects=transition.effects,
            )
        )

    pages = [
        SafeSymPage(
            id=page_id,
            
            #从schemas、actions按照pdge_id获取对应的signature_schema和actions
            signature_schema=schemas.get(page_id, {}),
            actions=actions_by_page.get(page_id, []),
        )
        for page_id in page_order
    ]

    return SafeSymFsm(
        app=app,
        initial_page_id=initial_page_id,
        terminal_pages=terminal_pages,
        pages=pages,
    )
