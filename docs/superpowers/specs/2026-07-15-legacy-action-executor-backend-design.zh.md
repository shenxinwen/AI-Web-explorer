# Legacy Action Executor / AiWebExplorerBackend v1 设计（中文审阅版）

## 1. 目标

这份设计说明如何复用原始 `ai-web-explorer` 项目里的网页操作能力，同时避免把它的 ReAct 式探索循环带入 Web-KOBE/SafeSym 架构。

我们仍然坚持这个边界：

```text
Web-KOBE / SafeSym Explorer
  -> 负责探索策略
  -> 负责状态观察和 delta 记录
  -> 负责 graph 构建
  -> 后续负责 SafeSym / PDDL 投影

Reusable automation backend
  -> 负责操作浏览器
  -> 负责执行 grounded action
  -> 返回执行成功/失败证据
```

下一步应该复用的是原项目中的“小动作执行层”，而不是整个原项目的 `ExploreLoop`。

## 2. 当前发现

原项目中已经有有价值的网页操作代码：

```text
src/ai_web_explorer/executor.py
```

最值得复用的是其中的 tool-call 执行逻辑：

```text
click_element(selector)
fill_text_input(selector, text)
select_option(selector, value)
```

这些操作和当前 Web-KOBE 的 `BrowserAction` 类型高度对应：

```text
click
fill
select
fill_then_click
```

但是，当前的 `Executor.execute(action)` 不是一个干净的 backend。它混合了很多职责：

- 让 LLM 生成 tool calls；
- 执行 tool calls；
- 对比前后截图；
- 让模型验证动作是否成功；
- 多轮 retry；
- 保存所有 tool calls；
- 依赖原项目的 `webstate.Action` 结构。

这对 Web-KOBE/SafeSym 路线来说耦合太重。

## 3. 推荐方案

建议抽出或新增一个很小的 `LegacyActionExecutor`，只负责执行已经 grounded 的浏览器动作。

概念接口：

```python
class LegacyActionExecutor:
    def __init__(self, page: playwright.sync_api.Page) -> None:
        ...

    def execute_browser_action(self, action: BrowserAction) -> bool:
        ...
```

这个 executor 不应该：

- 调用 LLM；
- 选择动作；
- 描述页面；
- 用模型验证成功；
- 构建 graph；
- 知道 SafeSym/PDDL。

它只负责把已经 grounded 的 `BrowserAction` 转换成真实 Playwright 操作。

## 4. 为什么不直接包装整个原始 Executor

直接包装 `Executor.execute()` 看起来省事，因为它已经能让 LLM 生成 tool calls 并执行。但这会重新引入我们刚刚想避免的耦合。

如果直接包装它，backend 可能会：

- 自己生成 selector；
- 自己决定如何执行抽象描述；
- 依赖 OpenAI prompt；
- 用模型生成的新动作 retry；
- 用截图让模型验证成功；
- 隐藏实际执行路径。

这些能力对通用 web agent 有用，但对面向 SafeSym 的环境建模系统有风险。

在我们的项目里，动作到达 backend 前就应该已经被 grounding。backend 只执行，不重新发明动作。

## 5. 建议数据流

```text
WebKobeExplorer
  -> 从 grounded candidates 中选择 BrowserAction
  -> 调用 AutomationBackend.execute(action)

AiWebExplorerBackend
  -> 接收 BrowserAction
  -> 委托 LegacyActionExecutor 执行真实操作

LegacyActionExecutor
  -> scroll locator into view
  -> click / fill / select
  -> briefly wait
  -> 返回 bool success

WebKobeExplorer
  -> 观察 after-state
  -> 计算 delta
  -> 记录 edge
```

## 6. 和当前 Playwright Backend 的关系

`WebKobePlaywrightAdapter` 仍然是当前默认的 async Playwright backend。

`LegacyActionExecutor` 不是立刻替代它，而是开始把原项目里可复用的操作原语拆出来。

后续可以引入：

```text
AiWebExplorerBackend
  -> 使用原项目同步 Playwright page
  -> 内部调用 LegacyActionExecutor
```

如果当前 async Playwright backend 更简单，也可以继续作为默认路径。

## 7. 动作映射

| BrowserAction 类型 | Legacy 操作 |
| --- | --- |
| `click` | 滚动到目标元素，然后点击目标 locator |
| `fill` | 用第一个 input value 填充目标 locator；没有值时使用安全默认值 |
| `select` | 选择第一个 input value |
| `fill_then_click` | 先填充每个 selector/value，再点击目标 locator |

不支持的动作应该返回 `False`，不要猜测执行。

## 8. 第一版实施范围

第一版应该保持很小：

1. 新增 `LegacyActionExecutor`；
2. 支持 `click`、`fill`、`select`、`fill_then_click`；
3. 用 fake page / fake locator 做单元测试；
4. 不改变当前 `WebKobePlaywrightAdapter` 行为；
5. 只有在 executor 足够干净后，再考虑实验性 `AiWebExplorerBackend`。

这样可以避免把两个变化混在一起：

- 抽出可复用操作能力；
- 引入第二个完整 backend。

## 9. 非目标

这一步不做：

- 接入第三方 web agent；
- 把旧 `ExploreLoop` 变成主探索器；
- 用 LLM 选择动作；
- 用 LLM 生成 selector；
- 解决状态恢复；
- 解决 graph 去重；
- 改 Web-KOBE graph schema。

## 10. 推荐推进方式

建议分两阶段：

```text
Phase 1:
  抽出 LegacyActionExecutor，并测试它。

Phase 2:
  如果 Phase 1 足够干净，再包装实验性的 AiWebExplorerBackend。
```

这能保持项目主线不偏：

```text
复用操作能力；
自己掌控探索和 SafeSym-facing 知识构建。
```

