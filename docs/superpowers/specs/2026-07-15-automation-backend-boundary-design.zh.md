# 自动化后端边界设计（中文审阅版）

## 1. 目标

这份设计用于明确一个重要边界：

```text
复用现成 web agent / 浏览器自动化能力；
我们自己掌控探索逻辑、状态记录、graph 构建和 SafeSym 对接。
```

项目不应该变成一个从零手搓的通用网页 agent。它真正有价值的部分，是把未知网页环境转换成 SafeSym 能理解的动作/状态知识。

## 2. 架构原则

系统拆成两层。

```text
Web-KOBE / SafeSym Explorer
  -> 控制探索策略
  -> 记录动作执行前后的 observation
  -> 推断状态变化 delta
  -> 构建 Web-KOBE / capability graph
  -> 后续导出 SafeSym / PDDL 可用产物

Automation Backend
  -> 操作真实浏览器
  -> click / fill / scroll / wait / navigate
  -> 解析 locator
  -> 处理浏览器和 session 状态
```

Explorer 决定“探索什么、如何记录、如何形成知识”；Backend 只负责“如何真实操作网页”。

## 3. 为什么要这样划分

现成 web agent 通常优化的是完成一个任务，例如购买商品、填写表单、搜索信息。

但我们的目标不是单次任务完成，而是发现并记录网页环境能做什么。

如果把整个过程交给通用 web agent，它可能成功完成任务，但不会天然输出 SafeSym 需要的关键信息：

- 使用了哪个具体可交互元素；
- 动作由哪个 locator grounding；
- 动作执行前状态是什么；
- 动作执行后状态是什么；
- 哪些字段发生变化；
- 这个迁移是否应该成为 graph edge；
- 这个迁移未来如何转换成 planning action。

因此，网页操作能力可以复用，但探索循环和数据模型必须由我们自己掌控。

## 4. 建议接口

建议引入一个稳定的后端边界。具体命名可以后续调整，但概念接口是：

```python
class AutomationBackend:
    async def observe(self) -> PageObservation:
        ...

    async def list_interactables(self) -> list[Interactable]:
        ...

    async def execute(self, action: BrowserAction) -> ActionResult:
        ...
```

未来可扩展：

```python
async def navigate(url: str) -> None:
    ...

async def reset_to(state_ref: StateRef) -> bool:
    ...

async def recover(edge_path: list[BrowserAction]) -> bool:
    ...
```

第一版应该保持小而稳定。`observe`、`list_interactables`、`execute` 已经足够支撑当前 DOM-first 探索链路。

## 5. 可接入的后端

### 5.1 PlaywrightBackend

这是当前默认路径。

它稳定、可测试，并且已经在本地 fixture 上跑通。它应该继续作为第一版 backend，因为我们能直接控制 locator、浏览器状态和 before/after observation。

### 5.2 AiWebExplorerBackend

这个 backend 用于包装原始 `ai-web-explorer` 项目里有价值的网页操作能力。

重点是复用它的浏览器操作能力，而不是把原来的 ReAct 式探索逻辑作为主控制器搬进来。

### 5.3 ThirdPartyWebAgentBackend

后续可以包装 browser-use 这类第三方 web agent。

如果它们的动作执行能力比我们的 Playwright wrapper 更强，就可以作为 backend 使用。但它们仍然必须受我们的候选动作约束，并返回足够证据用于 graph 记录。

## 6. 数据流

```text
ExplorerCore
  -> backend.observe()
  -> backend.list_interactables()
  -> 构造 grounded BrowserAction candidates
  -> 选择下一步 action
  -> backend.execute(action)
  -> backend.observe()
  -> 计算 delta
  -> 记录 Web-KOBE edge
```

selector 可以是确定性策略、BFS/DFS、LLM、VLM 或混合策略。但无论哪种策略，都应该从 grounded candidates 中选择，而不是凭空生成动作。

## 7. 当前实施方向

当前的 `web_kobe_playwright_adapter.py` 应该被视为第一个具体 backend，而不是最终探索架构本身。

近期工作建议：

1. 保持当前 Playwright-backed 路径可运行；
2. 在命名和接口上明确 backend / explorer 边界；
3. 确保 graph 记录和状态 delta 推断归 Explorer 所有；
4. 后续再评估原始 `ai-web-explorer` 的操作能力是否能包装成第二个 backend。

## 8. 非目标

这份设计暂时不做：

- 从零构建新的通用 web agent；
- 替代 Playwright；
- 让 LLM/VLM 直接自由控制浏览器；
- 完成复杂状态去重；
- 完成完整 PDDL 投影；
- 一次性解决完整状态恢复。

这些都应该等“正确操作网页并记录变化”的链路稳定之后再推进。

## 9. 验收标准

这项设计完成时，应满足：

- 文档明确说明浏览器操作能力由可复用 backend 提供；
- Web-KOBE / SafeSym 代码仍然负责探索策略和 graph 记录；
- 当前 Playwright adapter 可以被理解为一个 backend 实现；
- 未来增加其他 backend 时，不需要重写 graph 和 SafeSym 对接逻辑。

