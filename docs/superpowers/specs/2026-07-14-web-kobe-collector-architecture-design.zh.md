# Web-KOBE Collector 架构设计

## 目的

这份文档用于修正 Web-KOBE 方向的长期架构。

原始 `ai-web-explorer` 已经有一套通用网页探索引擎。它可以打开网站，
使用 LLM 理解当前页面，生成候选动作，用 Playwright 执行动作，合并相似
状态，回到尚未充分探索的状态，并输出状态机。

因此，Web-KOBE / SafeSym 工作不应该替代这套探索引擎。我们应该复用它，
并在探索过程中收集更丰富、更适合规划的信息。

修正后的方向是：

```text
原 ai-web-explorer ExploreLoop
  -> 浏览器与 LLM 驱动的探索
  -> Web-KOBE Collector hooks
  -> WebKobeGraph / capability graph
  -> PDDL 投影
  -> SafeSym
```

## 架构决策

项目应该把原 explorer 视为“探索发动机”，把 Web-KOBE 视为“知识表示与采集层”。

换句话说：

```text
ExploreLoop 回答：
  如何持续探索未知网站？

WebKobeCollector 回答：
  探索过程中应该记录哪些规划相关信息？

WebKobeGraph 回答：
  这个网站能做什么？执行这些能力后状态如何变化？
```

这样可以避免维护两套互相竞争的探索循环。

## 应该复用的原有探索能力

原代码已经提供了很多应该复用的能力。

相关文件：

```text
src/ai_web_explorer/loop.py
src/ai_web_explorer/describer.py
src/ai_web_explorer/executor.py
src/ai_web_explorer/webstate.py
src/ai_web_explorer/html.py
src/ai_web_explorer/cookies.py
```

可复用行为：

- Playwright 浏览器启动与页面导航。
- LLM 生成页面标题。
- 使用标题 embedding 或标题文本合并相似状态。
- LLM 生成页面描述。
- LLM 生成候选动作。
- LLM 指导 Playwright 执行动作。
- 动作重试与视觉验证。
- 状态跳转记录。
- 查找还有可用动作的其他状态。
- 通过已知 transition 回放路径，回到待探索状态。
- 输出 JSON / DOT 状态机。

这些能力重建成本很高，而且它们正是未知网站探索所需要的 web-agent 工作流。

## 原 explorer 当前收集信息的不足

现有 `WebState` 图有用，但不足以支撑 SafeSym 风格的规划。

当前 `WebState` 信息：

```text
title
title_embedding
urls
description
actions
transitions
```

当前 `Action` 信息：

```text
description
part
priority
status
function_calls
```

这些信息足以回放和可视化探索，但对规划来说还不够，因为它没有显式建模：

- 稳定的语义页面类型；
- 与规划相关的状态指标；
- 抽象动作目标，例如 product、post、form、field、cart、order；
- 能力名，例如 `add_to_cart(product)` 或 `submit_login_form`；
- 执行动作前后的状态 delta；
- 执行证据；
- 前置条件和效果；
- 置信度与审计状态；
- PDDL 投影提示。

Web-KOBE 的工作应该补齐这部分。

## 之前 Web-KOBE 工作中应该保留的内容

以下内容仍然有价值：

- `WebKobeGraph`、`WebKobeNode`、`WebKobeEdge` 及相关数据结构。
- `WebKobeGraphManager`。
- Web-KOBE 到 PDDL 的投影实验。
- SauceDemo 作为受控 benchmark。
- capability-first 建模思想：关注页面能做什么，而不是页面里有什么内容。
- 代表性实体建模：商品卡、帖子、表格行、搜索结果通常应该抽象成目标类型，
  而不是大量具体图实体。
- UI-KOBE 启发：语义状态节点、动作边、schema delta、状态匹配、运行时图引导。

这些内容描述的是目标知识表示。

## 应该降级或停止扩展的内容

以下内容应该视为实验或过渡代码，而不是长期主探索路径：

- `WebKobeExplorationController`。
- `WebKobePlaywrightAdapter` 作为独立通用探索 adapter。
- `web-kobe-explore` 作为绕过原 `ExploreLoop` 的独立探索命令。

它们证明了真实浏览器动作可以产生 Web-KOBE 边，这一点有价值。但继续扩展它们
会重复原 explorer 的工作。

它们可以继续用于确定性单元测试、本地 fixture、SauceDemo smoke test，但未知网站
的主探索路径应该转向原 explorer 内部或旁路的 collector hooks。

## 新组件：WebKobeCollector

`WebKobeCollector` 是一个 hook 式采集层。它不选择动作，也不驱动浏览器。
它观察原 explorer 的执行过程，并记录更丰富的图数据。

概念接口：

```python
class WebKobeCollector:
    def on_state_observed(
        self,
        *,
        page,
        web_state,
        observation,
    ) -> None:
        ...

    def on_action_selected(
        self,
        *,
        source_state,
        action,
    ) -> None:
        ...

    def on_action_executed(
        self,
        *,
        action,
        success: bool,
        tool_calls: list,
        error: str | None,
    ) -> None:
        ...

    def on_transition(
        self,
        *,
        source_state,
        action,
        target_state,
        before_observation,
        after_observation,
    ) -> None:
        ...

    def to_web_kobe_graph(self) -> WebKobeGraph:
        ...
```

具体函数签名可以在实施时细化，但边界应该保持不变：collector 负责观察和记录，
explorer 负责探索。

## 原 ExploreLoop 中的 Hook 点

最小可用集成点在 `ExploreLoop._explore()`。

当前概念流程：

```text
1. 获取当前 WebState
2. 如果上一个动作成功，追加 StateTransition
3. 选择下一个动作
4. 执行动作
5. 标记动作成功/失败
```

加入 collector 后：

```text
1. 获取当前 WebState
2. collector.on_state_observed(...)
3. 如果上一个动作成功：
     collector.on_transition(...)
     追加 StateTransition
4. 选择下一个动作
5. collector.on_action_selected(...)
6. 执行动作
7. collector.on_action_executed(...)
8. 下一轮观察执行后的状态
```

第一版应该避免大规模重写。可以在 `LoopConfig` 或 `ExploreLoop.__init__`
里增加可选 `collector` 字段，默认使用 no-op collector。

## 应该收集的信息

Collector 应该收集面向规划的信息，而不是原始页面 dump。

### 页面与状态信息

- URL 与规范化 URL pattern。
- 浏览器 title。
- 可用时的主 heading。
- 原 explorer 的 LLM title。
- 现有 `WebState` ID。
- 已知或推断出的语义页面类型。
- 会影响能力、跳转、目标或执行验证的状态指标。
- 每个状态指标的证据。

### 可交互元素与动作信息

- 原始 LLM action description。
- action priority 与 part。
- executor 生成的 tool calls。
- tool calls 使用的具体 selector。
- 动作类型：click、fill、select、composite、unknown。
- 可推断时的抽象目标类型：product、post、result、form、field、cart、order、
  navigation item。
- 重复实体的代表性 target pattern。
- 使用过的输入值；敏感值需要脱敏。

### transition 信息

- 源语义状态。
- 目标语义状态。
- 执行动作。
- 成功或失败。
- before / after observation。
- before / after 的语义 delta。
- delta 的证据。
- transition 类型：navigation、self-loop state change、form progress、failure、
  modal/overlay、unknown。

## 数据流

```text
ExploreLoop
  观察页面并创建 WebState
    -> WebKobeCollector 记录 SemanticPageState 草稿

ExploreLoop
  选择 Action
    -> WebKobeCollector 记录 candidate capability 草稿

Executor
  生成并执行 Playwright tool calls
    -> WebKobeCollector 记录 concrete grounding 与 execution trace

ExploreLoop
  观察目标 WebState
    -> WebKobeCollector 比较 before / after observation
    -> WebKobeCollector 添加 WebKobeEdge / CapabilityTransition
```

原 `WebState` 图继续保留。Web-KOBE 图成为同一次探索过程产生的更丰富 sidecar。

## 状态与能力抽象规则

Collector 应该遵循项目原则：

```text
建模网站能做什么，而不是保存网站里所有内容。
```

例子：

```text
很多商品卡
  -> 一个 target_type = product
  -> capability = add_to_cart(product)

很多论坛帖子
  -> 一个 target_type = post
  -> capability = open_post(post)

很多搜索结果
  -> 一个 target_type = result
  -> capability = open_result(result)
```

具体例子仍然对 grounding 和 replay 有用，但应该作为证据或代表性样本保存，而不是
长期图节点，除非该实例本身对规划有意义。

## 与 SauceDemo 的关系

SauceDemo 仍然是受控验证目标。

对于 SauceDemo，collector 可以复用已有确定性 observer 和 profile：

```text
src/ai_web_explorer/safesym_bridge/state_observer.py
src/ai_web_explorer/safesym_bridge/saucedemo_adapter.py
src/ai_web_explorer/safesym_bridge/saucedemo_catalog.py
```

这样可以比较：

```text
原 WebState 输出
确定性 WebObservedGraph 输出
collector 生成的 WebKobeGraph 输出
```

三者应该用不同抽象层级描述同一段浏览器行为。

## 与 SafeSym 的关系

SafeSym 不负责探索网站，也不负责决定 Web 图里应该有什么。SafeSym 消费由图投影出的
规划模型。

Collector 的职责是产出足够结构化的图，以便之后做 PDDL 投影：

```text
states
capabilities
preconditions
effects
execution evidence
```

SafeSym 继续负责安全策略和安全检查插入。

## 实施策略

实施应该分阶段进行。

### Phase 1：只读 collector sidecar

添加一个 no-op 兼容的 collector，让 `ExploreLoop` 可以调用它，同时不改变原有探索行为。

交付物：

```text
ExploreLoop 正常运行，同时 collector 接收 state/action/transition 事件。
```

### Phase 2：WebState 到 WebKobeGraph 转换

构建一个 converter，将已有 `WebState`、`Action`、`StateTransition` 对象映射成
基础 `WebKobeGraph`。

交付物：

```text
现有 explorer 输出可以投影成 WebKobeGraph 形状。
```

### Phase 3：hook 中的更丰富 observation

使用 DOM、截图、title、URL、executor tool calls 添加 evidence、grounding 和 delta。

交付物：

```text
WebKobeGraph 节点和边包含规划相关证据与 execution trace。
```

### Phase 4：capability normalization

把重复内容和具体动作归一化成可复用能力。

交付物：

```text
点击某一个商品卡这样的具体动作，变成 add_to_cart(product) 这样的抽象能力。
```

### Phase 5：PDDL 投影与审计

将 collector 生成的图投影到 PDDL，并增加审计检查：噪声状态、重复节点、不支持的
delta、不安全投影等。

交付物：

```text
collector 生成的图可以支撑 SafeSym 规划。
```

## 最近实验代码的迁移计划

最近新增的 Web-KOBE Playwright adapter 和 controller 不应该马上删除。它们应该被重新分类。

建议处理：

```text
保留：
  WebKobeGraph 数据模型
  graph manager
  PDDL projector
  有用的 SauceDemo smoke tests

降级：
  WebKobeExplorationController
  WebKobePlaywrightAdapter 作为通用探索路径
  web-kobe-explore 作为未来主 CLI

未来：
  等 collector 覆盖替代后，将这些测试改成 collector 输出测试，或者删除过渡代码。
```

这样可以避免不必要的代码震荡，同时把新工作引导到正确架构上。

## 测试策略

默认测试应该避免真实 LLM 调用。

推荐测试：

- `WebState -> WebKobeGraph` 转换单元测试。
- collector 事件顺序单元测试。
- 目标抽象单元测试，例如多个商品被归纳为一个 product target type。
- 使用现有 state observer 和 action profile 的 SauceDemo 确定性测试。
- 通过环境变量显式开启的真实浏览器测试。
- 通过 API key 和显式 opt-in 开启的 LLM 集成测试。

## 实施前需要决定的问题

实施计划需要决定：

1. collector hooks 是直接放进 `ExploreLoop`，还是通过薄 wrapper / subclass 接入。
2. 第一版 converter 消费内存中的 `WebState` 对象，还是消费 `explore -o json` 输出。
3. 当前 `WebKobeGraph` 模型有多少可以原样复用。
4. `ExecutionTrace` 中如何脱敏账号、密码和敏感表单输入。
5. `web-kobe-explore` 应该重定向到原 explorer，还是改成类似
   `explore --collector web-kobe` 的命令形式。

## 推荐下一步

下一步实施不应该继续增加独立探索逻辑。

推荐下一项实施：

```text
先构建 WebState-to-WebKobeGraph converter。
```

原因：

```text
它可以立即复用现有 explorer 输出，对原 explorer 改动最小，不需要 LLM/浏览器即可测试，
并且为项目建立从现有状态机数据到 Web-KOBE 图的桥。
```

converter 工作后，再加入 collector hooks，在真实探索过程中丰富图。
