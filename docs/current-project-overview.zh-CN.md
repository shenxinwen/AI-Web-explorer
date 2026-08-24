# 当前项目概览

本文解释项目要解决的问题、核心思想、主要概念、当前主线和验收标准。具体模块与代码入口见 `docs/project-structure.zh-CN.md`，架构决策的演进原因见 `docs/project-decisions.zh-CN.md`。

## 一句话定位

AI Web Explorer 是一个面向网页功能理解的开放式探索系统。它通过视觉观察发现网页中的业务位置和可执行功能，通过真实操作与结果观察验证这些功能，并将探索经验组织成可恢复、可继续探索的 `WebKobeGraph`。在此基础上，系统可以进一步提取 Minimal Semantic PDDL，供 SafeSym 检查、约束和规划。

项目的首要价值是通过探索理解网页，而不是单纯为 SafeSym 生成 PDDL。SafeSym 是结构化理解的下游消费者，也是一种严格的质量检查手段：如果探索结果无法形成语义清楚、因果合理、可求解的规划模型，就说明我们对网页的理解仍然存在缺口。

```text
探索网页
  -> 发现网页具有什么功能
  -> 验证动作会产生什么结果
  -> 建立可恢复、可复用的网站功能模型
  -> 将模型投影为 PDDL
  -> 由 SafeSym 检查、约束和规划
```

## 项目要解决的问题

浏览器可以告诉我们页面上有哪些 DOM 元素，自动化工具也可以点击、输入和选择，但这些信息并不直接等于对网页功能的理解。

例如，一个购物网站上的按钮可能分别表示“将商品加入购物车”“查看购物车”“继续结账”或“取消并返回”。要理解网站，系统还需要回答：

- 当前处于什么业务上下文？
- 当前可以完成哪些有意义的业务动作？
- 哪些动作只是同一功能在不同对象上的重复实例？
- 一个动作是否依赖另一个动作已经完成？
- 动作执行后，网页发生了什么可观察变化？
- 这是同一位置内的状态变化，还是进入了新的业务位置？
- 离开某个页面后，怎样回到仍有功能尚未探索的位置？
- 哪些已验证经验足以成为规划器可以信任的动作、前提和效果？

因此，本项目不是一个只完成预设任务的网页 agent，也不是一个把 DOM 机械转换为 PDDL 的编译器。它关注的是如何通过有限、可恢复的真实交互，逐步建立网站的功能模型。

## 当前总体验收标准

项目保留以下三个阶段验收目标：

1. 能够探索网站，而不是执行一条写死的任务脚本；
2. 能生成合法、可供 SafeSym 消费和求解的 PDDL；
3. 核心探索、图和 PDDL 逻辑具备一定泛化性。

三项目标存在先后关系。第一项验证系统是否真正发现并理解网页功能；第二项验证理解结果能否形成严格的规划模型；第三项验证方法是否超越某个固定网站和固定流程。

“PDDL 可以被求解”不等于“系统已经完整理解网站”。规划链路成功只能证明当前投影在语法和部分因果结构上可用，不能证明候选功能发现充分、语义位置稳定、动作因果完全正确或跨位置业务状态完整。

## 核心设计思想

### 1. VLM 负责看，本地系统负责记和选，Stagehand 负责做

系统把三个容易混淆的职责分开：

- VLM 根据截图理解当前业务界面，提出候选业务动作及可见证据；
- 本地 Explorer 根据候选池、依赖、完成状态和尝试次数选择下一步；
- Stagehand 把已经选定的高层业务动作落实为真实浏览器操作。

VLM 不负责维护全局探索记忆，也不决定动作是否已经做过。Stagehand 不负责规划后续业务目标。去重、依赖满足、失败切换和 frontier 调度由本地结构化状态决定。

### 2. 通过执行结果理解功能，而不是只相信候选描述

截图中看起来可执行的动作不一定真的可执行，动作名称也不能证明它会产生预期结果。因此候选只是待验证假设。

一个动作只有经过实际执行和动作后观察，才能成为 WebKobeGraph 中的已验证经验，并进一步进入 planner-facing 模型。失败、无变化或证据不足的动作可以保留诊断记录，但不能冒充成功能力。

### 3. 用 semantic location 表示业务上下文

网页 URL、DOM、截图和 raw node 都是重要证据，但都不天然等同于业务位置。同一 URL 可能包含不同表单阶段，同一商品页也可能因为筛选、弹窗或购物车状态产生不同观察；反过来，多次访问同一个业务页面也可能产生不同 raw node。

系统使用 `semantic location` 表示对当前业务上下文的归纳，例如：

```text
login_form
product_catalog
shopping_cart
checkout_information
checkout_overview
checkout_complete
```

正常探索以 semantic location 为候选记忆单位。URL identity 当前只在 replay 恢复后做轻量辅助匹配，不替代正常探索中的语义判断。

### 4. 候选属于位置，完成状态也属于位置

候选动作按 semantic location 建立候选池，而不是全站维护一个动作集合。去重键可以理解为：

```text
(semantic location, canonical action)
```

因此，`submit` 在登录位置完成，不代表另一个表单位置的 `submit` 已完成；同一位置内已经成功执行的 `filter_products` 则不会因为重新访问页面而再次执行。

### 5. 探索与上下文恢复严格分离

正常 Explorer 负责发现候选、选择动作、执行、观察结果和更新图。replay 只负责把浏览器恢复到一个已经认识、但仍有候选未完成的 frontier。

如果 replay 也重新扫描页面、重新命名位置或写入 graph，它就会把恢复过程误当成新的探索，并可能污染既有候选状态。因此当前 replay 只执行保存的动作路径；路径成功后把控制权交还 Explorer。

### 6. Graph 可以丰富，PDDL 必须保守

WebKobeGraph 可以保存截图证据、raw observation、失败尝试、动作轨迹、semantic location、候选状态和运行时 checkpoint。它是探索记忆和审计记录。

Minimal Semantic PDDL 面向规划器，不能照搬所有观察信息。它只投影具有足够语义和执行证据的动作、位置、显式依赖和结果，避免把 VLM 猜测、无关完成事实或失败动作升级成规划知识。

## 主要概念

### Semantic location

对当前业务上下文的稳定称呼，是候选池、动作完成状态和 frontier 的主要索引。它强调“用户正在做什么”，而不是“浏览器当前 raw node ID 是什么”。

### 候选业务动作

VLM 从当前截图中提出的高层功能，例如 `add_to_cart`、`view_cart`、`continue_checkout`。候选应描述一个业务意图，而不是一串固定 locator 操作。

候选发现采用精度优先：页面只有少量明确功能时可以返回少量动作，不需要为了达到数量上限而填充背景控件。

### `requires`

VLM 在同一次位置扫描中观察到的直接动作依赖。例如 `submit_login` 可能依赖 `enter_credentials`。本地选择器只有在依赖动作已经成功时，才会调度被依赖动作。

`requires` 当前只表达同位置显式动作依赖，不自动承担跨位置持久业务状态。例如“购物车有商品”更适合未来表示为 `cart_has_items`，而不是简单等同于 `add_to_cart` 在某个页面完成过。

### Location candidate pool

每个 semantic location 对应一组候选记录。候选至少需要区分：

- `pending`：尚未完成，且未来可能执行；
- `completed`：已经成功执行并观察到结果；
- `failed`：达到候选尝试上限；
- `stale/disabled`：当前证据表明动作不再可用；
- `requires`：执行前必须完成的同位置动作；
- 尝试次数和最近失败原因。

候选池使系统在返回旧位置时能够继续消费未完成动作，而不是再次调用 VLM 生成一套可能名称不同的候选。

### Action outcome

高层动作执行后，VLM 根据动作前后观察回答：动作成功、失败还是不确定；位置是否变化；目标位置是什么；有哪些完成事实和可见证据。

动作 outcome 与 Stagehand API 返回成功不是一回事。Stagehand 成功表示操作调用完成，outcome 观察用于判断网页是否发生了与业务动作一致的变化。

### WebKobeGraph

系统对网站的经验模型。节点保存页面观察及 semantic location，边保存真实执行动作、执行轨迹、结果证据和语义变化。图还携带候选记忆、正式动作预算、replay 指标和断点恢复状态。

WebKobeGraph 不是预先编写的网站状态机，而是探索过程中逐步积累的、可以审计的经验图。

### Frontier

已经到达和认识、但仍有可执行候选未完成的 semantic location。当前位置耗尽时，controller 会检查是否存在其他 frontier，而不是立即结束整个探索。

### Replay path

从起始 URL 恢复到目标 frontier 的已验证语义动作路径。路径按 semantic location 收缩，主要保留位置变化动作，并补入这些路径动作明确声明的已完成 `requires`。

replay path 不是 raw graph 中所有历史动作的最短路。一个动作仅仅“曾经执行过”，不代表恢复目标位置时必须再次执行它。

### Minimal Semantic PDDL

从 WebKobeGraph 中提取的规划模型。它关注：

- 当前处于哪个 semantic location；
- 哪些真实执行成功的动作可以使用；
- 动作有哪些显式、可解释的前提；
- 动作会完成什么位置限定能力，或把系统带到什么新位置；
- 哪些业务事实经过了本地验证，可以安全进入规划模型。

“Minimal”表示只表达当前有证据支持的必要语义，不试图一次性构造完整的网站本体。

## 当前探索闭环

```text
1. 截取当前页面
2. VLM 判断或复用 semantic location
3. 新位置首次到达时，观察候选动作及同位置 requires
4. 将候选合并到该位置的候选池
5. 本地选择 pending、依赖满足且未超过尝试上限的动作
6. Stagehand 执行被选中的动作
7. 截取动作后的页面
8. VLM 观察 outcome、location change 和 evidence
9. 更新候选状态、WebKobeGraph 和当前 semantic location
10. 继续消费当前位置候选
11. 当前位置耗尽时，寻找其他 frontier
12. 必要时 replay 恢复目标 frontier，再交回正常 Explorer
13. 所有可达候选耗尽或达到预算后结束
14. 从已验证图投影 Minimal Semantic PDDL
```

候选发现不接收站点专用动作词表、固定业务流程、PDDL goal 或任务解法。SafeSym 的规划结果也不会反向控制探索顺序。

## Stagehand 执行粒度

高层业务动作和底层 UI 操作并不总是一一对应：

- `observed_action`：Stagehand 直接执行观察到的动作；
- `observe_act/single_instance`：只执行 observe 返回的第一个代表性原子 Action，避免对多个相似商品重复加购；
- `observe_act/composite`：依次执行 observe 返回的全部必要原子 Action，例如填写用户名和密码，或填写结账信息；全部成功后才观察高层动作 outcome。

候选动作的 `execution_policy` 会随图和 replay path 保存。replay 使用相同执行策略，因此组合登录动作可以继续使用实验配置中的正确公开测试账号和密码。

## Explorer 与 replay 的职责边界

### 正常 Explorer 负责

- 观察和命名新的 semantic location；
- 发现候选动作和 `requires`；
- 选择未完成且依赖满足的候选；
- 调用 Stagehand 执行动作；
- 观察 action outcome；
- 更新候选池、节点、边和规划证据；
- 消耗正式探索动作预算。

### Replay 只负责

```text
reset 到起始 URL
  -> 执行保存路径中的 semantic action
  -> 必要时先执行路径动作的显式 requires
  -> 所有路径动作成功
  -> 恢复目标 node、semantic location 和已有候选池上下文
  -> 将控制权交还 Explorer
```

Replay 不允许：

- 重新发现候选或重新扫描页面；
- 观察高层动作 outcome 并将其作为新探索经验；
- 新增或修改 graph node、edge 和 planning facts；
- 修改候选状态、扫描状态或正式尝试次数；
- 把恢复动作重复投影为新的 PDDL 经验。

当前最小策略假设路径动作全部成功就已经回到目标上下文，不在 replay 末端重新调用 VLM，也不要求 raw node ID 一致。这样做牺牲了一部分到达证明强度，但避免恢复阶段产生新的语义位置并与历史记忆冲突。

Replay 失败时记录失败动作 ID、目标位置和原因，然后遵守次数上限尝试该 frontier 或其他 frontier。当前每个 frontier 最多 replay 2 次，总 replay 最多 4 次。

## SauceDemo 示例

假设系统已经探索出：

```text
login_form
  -> enter_credentials
  -> submit_login
  -> product_catalog
       -> add_to_cart
       -> view_cart
       -> shopping_cart
            -> continue_shopping
            -> continue_checkout
```

系统在商品页完成 `add_to_cart` 和 `view_cart`，进入购物车后先执行 `continue_shopping`，于是又回到商品页。此时 `product_catalog` 候选池中的动作已经完成或耗尽，但 `shopping_cart` 中仍有 `continue_checkout` 未完成。

正确行为不是把整个探索判定为结束，也不是在商品页重新扫描一套候选，而是：

1. controller 发现当前位置候选耗尽；
2. candidate memory 表明 `shopping_cart` 仍是 frontier；
3. 系统 reset 到 SauceDemo 起始 URL；
4. replay 已保存的路径，例如 `enter_credentials -> submit_login -> view_cart`；
5. 路径动作全部成功后，恢复 `shopping_cart` 的既有候选池；
6. replay 停止，由正常 Explorer 执行未完成的 `continue_checkout`。

`add_to_cart` 不会因为历史路径中曾经出现过就自动重放。只有当 `view_cart` 明确声明 `requires: [add_to_cart]` 时，恢复路径才会补入它。这也说明当前模型的边界：空购物车和有商品购物车的差异最终应由跨位置业务事实表达，不能长期只依赖动作完成关系。

## 三层验收边界

### 1. 探索执行验收

主要检查系统是否能够：

- 在没有固定任务脚本的情况下从截图提出业务动作；
- 本地调度动作，而不是让 VLM 或 Stagehand自由规划整条流程；
- 正确执行 single-instance 和 composite 动作；
- 对失败候选有限重试并切换其他候选；
- 在当前位置耗尽后寻找其他 frontier；
- 通过 reset + replay 恢复上下文并继续正常探索；
- 在步数和 replay 上限内确定性结束。

### 2. 网页功能理解验收

主要检查系统形成的结构化理解是否合理：

- semantic location 是否区分了关键业务位置；
- 候选动作是否代表真实业务功能，而不是控件清单；
- 重复对象上的同类动作是否合并为代表性能力；
- `requires` 是否只包含直接、可观察的动作依赖；
- 只有真实成功且有结果证据的动作才被标记完成；
- 返回旧位置时是否复用原候选池，而不是重复发现和执行；
- WebKobeGraph 是否保留足够证据解释每条能力从何而来；
- 是否存在错误位置合并、位置别名膨胀或明显因果捷径。

### 3. PDDL / SafeSym 验收

主要检查下游模型是否：

- 生成合法的 `domain.pddl` 和明确目标下的 `problem.pddl`；
- 只包含实际执行成功且可投影的动作；
- 使用位置事实和位置限定完成事实；
- 只把显式 `requires` 或经过验证的业务事实作为前提；
- 不把所有历史完成动作自动加入 precondition；
- 不因失败动作、候选猜测或 raw observation 产生规划捷径；
- 能被 SafeSym 解析、注入安全约束，并在配置 planner 时完成 base/safe planning。

例如：

```lisp
(:action add_product_to_cart
  :precondition (and (at_product_catalog))
  :effect (and
    (at_product_catalog)
    (completed_product_catalog_add_product_to_cart)
  )
)

(:action view_cart
  :precondition (and
    (at_product_catalog)
    (completed_product_catalog_add_product_to_cart)
  )
  :effect (and (at_shopping_cart))
)
```

这里的完成事实只有在 `view_cart` 明确依赖 `add_product_to_cart` 时才进入前提。其他无关的已完成动作不能自动成为 `view_cart` 的前置条件。

## 有界探索与终止条件

当前运行规则是：

- 正式探索动作数量受 `max_exploration_steps` 限制；
- 每个候选动作最多尝试 2 次；
- 候选达到上限后标记失败并切换其他候选；
- 不再使用全局连续无进展作为真实 runner 的提前终止条件；
- 每个 frontier 最多 replay 2 次；
- 总 replay 最多 4 次；
- 所有可达候选耗尽时正常结束。

这些是通用实验限制，不是 SauceDemo 或电商网站的固定语义规则。

## 当前完成情况

当前已经完成：

- VLM 截图候选观察及同位置 `requires` 提取；
- semantic-location 候选池、依赖解锁、完成/失败和有限重试；
- Stagehand `observed_action`、`single_instance` 和 `composite` 执行；
- VLM action outcome、位置变化和可见证据观察；
- WebKobeGraph、compact graph、checkpoint 和累计运行状态；
- frontier 选择、semantic-location replay path、reset + replay 和失败诊断；
- replay 后复用既有位置和候选池并继续探索；
- SemanticPlanningGraph、Minimal Semantic PDDL 和 SafeSym smoke；
- Practice Shopping 与 SauceDemo 的真实探索、语义投影和规划链路验证。

最近 SauceDemo 断点恢复实验中，replay 能回到仍有候选的购物车 frontier，随后由正常 Explorer 继续执行 `continue_shopping`、`cancel_checkout`、`complete_checkout` 等未完成动作。恢复过程没有因为 raw node 不一致重新创建商品页位置，也没有把无显式依赖的 `add_to_cart` 自动加入 replay path。

最新恢复图能够生成带目标的 `domain.pddl` 和 `problem.pddl`，并通过 SafeSym 解析、安全动作注入、基础规划和安全规划。这证明当前探索—图—PDDL—SafeSym 链路可行，但不表示网站功能和业务因果已经完整建模。

## 当前不足

### 跨位置持续业务状态不足

`requires` 适合同位置直接动作依赖，但购物车是否有商品、用户是否已登录等状态可能跨多个位置持续存在。当前最明显缺口是：

```text
add_to_cart -> cart_has_items -> continue_checkout
```

如果缺少 `cart_has_items`，PDDL 可能找到跳过加购的结账计划。这是网页因果理解问题，不应由 replay 隐式修补。

### Semantic location 稳定性仍依赖 VLM

同一业务页面可能被不同观察命名为不同位置，不同业务阶段也可能被过度合并。当前通过候选池复用和有限 URL handoff 缓解，但尚未形成跨网站稳定的位置匹配方法。

### Replay 到达证明较弱

当前 replay 信任路径动作执行成功，不做页面内容级 checkpoint 匹配。这符合“恢复而不探索”的最小边界，但未来如果真实网站动作成功返回不可靠，可能需要增加不产生新语义判断的轻量证据验证。

### 候选召回和依赖质量受观察能力限制

VLM 可能漏掉无文字图标、隐藏入口或条件动作，也可能遗漏必要依赖。候选精度、召回、动作粒度和依赖正确性仍需在更多网站上验证。

### 泛化证据仍有限

当前已证明主链在 Practice Shopping 和 SauceDemo 上可行，但距离“通用网页功能理解”仍有差距。需要覆盖非电商网站、多标签或弹窗流程、动态列表、权限状态和更复杂表单。

## 下一阶段重点

1. 建立通用的跨位置持续业务事实，而不是重新引入站点固定流程；
2. 用更多不同类型网站检验 semantic location、候选粒度和 replay 泛化；
3. 评估轻量、非探索式 replay 到达证据；
4. 继续检查 SemanticPlanningGraph 和 PDDL 中的因果捷径；
5. 建立更系统的“网页功能理解质量”指标，而不只以任务完成率或 planner 求解成功率评价系统。

## 当前主线与已删除历史结构

当前唯一主线是：

```text
VLM 截图观察
  -> 候选业务动作及同位置 requires
  -> semantic-location 候选池
  -> 本地选择
  -> Stagehand 执行
  -> VLM outcome
  -> WebKobeGraph
  -> 必要时 frontier replay
  -> Minimal Semantic PDDL
  -> SafeSym
```

旧 Trace/Location/Surface PDDL、旧 graph/debug exploration CLI、Behavior State Graph phase-a、旧 ecommerce smoke runner、`SemanticExperimentProfile`、`ActionContract` 和 `business_milestone` 已从生产路径移除。历史 specs、plans 和 experiments 只用于追溯项目演进，不代表当前接口。

## 相关文档

- `docs/project-structure.zh-CN.md`：当前模块、代码职责与数据流；
- `docs/safesym-bridge.md`：语义投影和 SafeSym 使用方式；
- `docs/project-decisions.zh-CN.md`：关键决策及演进原因；
- `docs/experiments/`：历史实验与证据；
- `docs/superpowers/specs/`：历史和当前设计规格。
