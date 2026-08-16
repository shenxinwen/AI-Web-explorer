# VLM 主导的动作依赖探索与 PDDL MVP 设计

日期：2026-08-16

状态：逻辑设计已与用户对齐，作为下一阶段详细设计与实验的参考；尚未实施

## 1. 背景与问题

当前项目已经打通以下链路：

```text
开放候选发现
  -> Stagehand 执行动作
  -> 动作前后观察
  -> SemanticPlanningGraph
  -> Minimal Semantic PDDL
  -> SafeSym 安全注入
  -> Fast Downward 求解
```

Practice Shopping 的真实实验已经证明该链路可行，但当前候选 prompt 会接收 profile 中的位置、事实词表、动作示例和动作契约。这相当于提前告诉 VLM 网站可能具有哪些能力以及业务动作之间的关系，使当前方案更接近“开放候选 + profile 引导的闭集验证”，还不是真正通过探索学习网站运行规则。

本设计不追求一次恢复完整、最小且普适的网站业务模型。MVP 的目标是让 VLM 主要根据当前页面自主发现动作及其操作顺序，通过真实执行验证这些关系，并生成一份保守、合法、可供 SafeSym 消费和求解的 PDDL。

## 2. 核心假设

网站可以暂时建模为：

```text
页面位置
+ 当前页面上的明确语义动作
+ 动作之间经观察与执行支持的依赖关系
```

动作在探索中可能表现为独立动作，也可能与其他动作形成依赖。但这不是永久、互斥的动作分类。系统最终记录的是动作节点与动作之间的依赖边；同一个动作既可以独立执行，也可以成为另一个动作的前置动作。

MVP 学习的是经过验证的动作依赖图，不是完整的业务状态模型。

## 3. 设计原则

### 3.1 VLM 观察是主体，错误反馈是补充

VLM 应先整体理解当前页面，而不是机械地逐个点击可交互元素。它应主动发现：

- 当前页面上具有实际意义的语义动作；
- 哪些动作当前已经业务就绪；
- 哪些目标动作存在页面可见的前置步骤；
- 动作之间可能存在的局部操作顺序；
- 支持这些判断的页面证据，例如表单结构、必填标记、空字段、禁用状态、步骤说明和提示文字。

例如在登录页，VLM 应直接观察并提出：

```text
fill-login-credentials -> login
```

不要求先提交空表单并等待错误信息。错误反馈只用于补充 VLM 没有观察到的隐藏条件，或修正其原有判断。

### 3.2 发现、推断与验证分离

动作与依赖关系采用以下生命周期：

```text
页面观察
  -> 候选动作
  -> 候选依赖
  -> 按候选顺序执行
  -> 动作后观察
  -> 已验证动作与依赖
```

VLM 可以在执行前直接记录候选关系，但候选关系不能立即成为最终 PDDL 契约。只有当相关动作实际成功、观察结果与预期顺序一致，并且后续目标动作最终成功时，关系才升级为已验证依赖。

此处验证的是“页面观察支持这条顺序，并且该顺序实际可行”，不要求通过反向试错证明该前提在所有情况下绝对必要。

### 3.3 只有成功动作进入最终 Domain

发现不等于学会。只有至少真实成功执行过一次的动作，才能进入最终 PDDL Domain。

- 成功动作进入已验证动作集合；
- 可见但尚未就绪的动作作为待验证候选保留；
- 有明确业务阻塞的动作可以触发前置步骤发现；
- 无实际操作目标、无效果或由 VLM 误判产生的候选不进入 Domain。

Domain 保留探索中所有成功验证的动作，而不只保留某个离线 goal 所需的动作。

### 3.4 动作使用可独立验证的语义粒度

一个动作应表达一个明确、可执行且可独立观察成功与否的语义意图。

合理粒度：

```text
fill-login-credentials
login
fill-shipping-information
fill-payment-information
place-order
```

不合理的过细粒度：

```text
click-username-field
type-first-character
click-password-field
```

不合理的过粗粒度：

```text
fill-credentials-and-login
fill-checkout-and-place-order
```

填写同一语义表单所需的多个底层点击和输入可以由 Stagehand 在一个动作内部完成；填写表单与提交表单应分开，因为二者之间存在需要观察和记录的操作顺序。

### 3.5 动作与动作结果必须分开

动作必须要求系统在当前页面继续实施一次新的点击、填写、选择或其他明确操作。页面已经显示的状态、成功提示或结果不能被再次创建为动作。

正确归属：

```text
执行 place-order
  -> 页面显示 Order submitted successfully
  -> 进入 confirmation 位置

结果属于 place-order 的成功证据和 effect
```

错误归属：

```text
place-order
  -> 再生成没有真实操作的 order-submitted action
```

每次动作执行后，VLM 应先把页面变化归属于刚执行的动作，再从剩余的真实可操作项中发现新候选。

### 3.6 页面位置是所有动作的大前提

每个动作至少具有一个来源位置前提，并明确记录动作后的目标位置。

- 位置不变时，effect 仍显式重申当前位置；
- 位置改变时，删除来源位置并增加目标位置；
- 位置表示当前活跃的主要业务页面或 surface，不仅由 URL 决定。

页面位置造成的顺序和操作依赖造成的顺序必须分开：

- 只有进入某页面后动作才出现，由 `at-location` 表达；
- 即使已经位于正确页面，仍需完成某个前置动作，由 `previous-action-completed` 表达。

### 3.7 MVP 直接使用动作完成事实连接依赖

短期不引入独立的业务就绪状态。经过验证的操作依赖直接表达为：

```text
previous-action-completed -> current-action
```

例如：

```lisp
(:action login
  :parameters ()
  :precondition (and
    (at-login-page)
    (fill-login-credentials-completed)
  )
  :effect (and
    (not (at-login-page))
    (at-products-page)
    (login-completed)
  )
)
```

这种表达可能比真实业务规则更保守，也不能自动归纳多个动作共享的业务状态，但实现简单，并能优先防止规划器绕过已经观察到的必要步骤。

### 3.8 支持多步解除同一目标动作的阻塞

一个目标动作可能需要多个准备动作。例如：

```text
place-order 尚未就绪
  -> fill-shipping-information
  -> 仍缺少支付信息
  -> fill-payment-information
  -> place-order 成功
```

如果页面观察表明两个准备动作分别消除了目标动作的一部分可见阻塞，则最终可以保守记录：

```text
fill-shipping-information-completed --+
                                      +-> place-order
fill-payment-information-completed ---+
```

不能仅因为某动作在目标动作之前执行，就把它加入前提。该动作至少应由 VLM 根据页面可见要求提出，或者在执行后使对应阻塞减少、消失，或使目标动作从不可用变为可用。

### 3.9 页面首次完整发现，动作后增量更新

页面不能严格只扫描一次，因为同一位置上的动作也可能改变其他动作的可用性。

```text
首次进入页面
  -> 完整候选发现

每次动作后
  -> 必须观察前后变化
  -> 位置变化时扫描新位置
  -> 候选可用性、阻塞或操作区域变化时增量更新
  -> 没有能力变化时不重复完整扫描
```

例如筛选商品后如果只改变商品列表而没有新能力出现，则记录完成即可；填写支付信息后如果 `place-order` 变得就绪，则必须更新该候选及其依赖。

### 3.10 探索保持开放，goal 只用于离线验收

候选动作和操作顺序必须从当前页面产生，不能由 PDDL goal、SafeSym plan 或 profile 中的完整功能清单反向驱动。

探索结束后，可以从已验证结果中选择 goal，用于检查生成模型能否规划。goal 不参与候选发现、动作排序或覆盖率判断。

## 4. 统一探索逻辑链

```text
1. 进入当前页面或活跃业务 surface
2. VLM 整体理解页面并提出明确语义动作
3. VLM 根据页面证据提出候选操作顺序
4. 已业务就绪的动作可以执行
5. 尚未就绪的目标动作保留，并优先执行页面可见的准备动作
6. Stagehand 只执行一个语义动作
7. VLM 比较动作前后页面：
   - 动作是否成功
   - 位置是否变化
   - 哪些页面变化属于该动作结果
   - 原有阻塞是否减少
   - 哪些候选从不可用变为可用
   - 是否出现新的真实操作
8. 更新候选动作和候选依赖
9. 当整条顺序成功后，将对应动作和依赖升级为已验证
10. 将全部已验证动作投影为 PDDL
11. 事后选择 problem goal
12. 通过 SafeSym 解析、注入并由 Fast Downward 求解
13. 检查计划是否与真实成功轨迹一致，不允许明显规划捷径
```

## 5. PDDL MVP 形态

以下示例使用 Practice Shopping 当前已观察到的粗粒度位置：商品页面、结账 surface 和确认页面。具体动作是否进入最终 Domain，仍必须以新实验中的实际成功记录为准。

```lisp
(define (domain practice-shopping-exploration)
  (:requirements :strips)

  (:predicates
    (at-shopping)
    (at-checkout)
    (at-confirmation)

    (filter-products-completed)
    (add-to-cart-completed)
    (open-checkout-completed)
    (fill-shipping-information-completed)
    (fill-payment-information-completed)
    (place-order-completed)
  )

  (:action filter-products
    :parameters ()
    :precondition (at-shopping)
    :effect (and
      (at-shopping)
      (filter-products-completed)
    )
  )

  (:action add-to-cart
    :parameters ()
    :precondition (at-shopping)
    :effect (and
      (at-shopping)
      (add-to-cart-completed)
    )
  )

  (:action open-checkout
    :parameters ()
    :precondition (and
      (at-shopping)
      (add-to-cart-completed)
    )
    :effect (and
      (not (at-shopping))
      (at-checkout)
      (open-checkout-completed)
    )
  )

  (:action fill-shipping-information
    :parameters ()
    :precondition (at-checkout)
    :effect (and
      (at-checkout)
      (fill-shipping-information-completed)
    )
  )

  (:action fill-payment-information
    :parameters ()
    :precondition (at-checkout)
    :effect (and
      (at-checkout)
      (fill-payment-information-completed)
    )
  )

  (:action place-order
    :parameters ()
    :precondition (and
      (at-checkout)
      (add-to-cart-completed)
      (fill-shipping-information-completed)
      (fill-payment-information-completed)
    )
    :effect (and
      (not (at-checkout))
      (at-confirmation)
      (place-order-completed)
    )
  )
)
```

最小验收 Problem：

```lisp
(define (problem practice-shopping-validation)
  (:domain practice-shopping-exploration)

  (:init
    (at-shopping)
  )

  (:goal
    (place-order-completed)
  )
)
```

独立的筛选等动作仍保留在 Domain，但规划器不必为了完成下单 goal 而执行它们。

## 6. Profile 与领域知识边界

下一阶段不能再把以下内容完整注入候选发现 prompt：

- 网站的具体动作名称清单；
- 预期功能清单；
- 完整位置清单；
- 具体动作契约；
- 完整业务流程；
- 要求探索器逐项验证的事实答案。

可以保留的引导包括：

- 通用网页交互知识；
- 动作粒度和结果归属规则；
- 页面位置作为基础前提的抽象规则；
- 安全策略、敏感动作白名单与测试数据；
- 用于稳定 planner-facing 表达的后置归一化能力。

位置名称和普通完成事实应主要在探索中产生。领域词表可以在观察后帮助统一不同表达，但不能作为候选发现阶段的功能答案。MVP 暂时直接使用动作完成事实表达业务依赖，不要求先构建完整业务事实词表。

## 7. MVP 验收标准

### 7.1 探索与动作发现

- 候选 prompt 不接收 Practice Shopping 的完整动作、事实、位置和契约答案；
- VLM 能从页面自主提出明确语义动作；
- VLM 能在执行前发现登录表单、结账表单等可见操作顺序；
- 错误反馈仅补充遗漏条件；
- 动作结果不会被重复创建为新动作。

### 7.2 依赖证据

- 依赖先作为候选关系保存；
- 整条动作顺序成功后才进入最终 PDDL；
- 纯粹时间相邻但无页面依据的动作不建立依赖；
- 多个分别解除阻塞的准备动作可以同时成为目标动作前提。

### 7.3 PDDL 与 SafeSym

- 只有成功执行过的动作进入 Domain；
- Domain 保留全部已验证动作，不受离线 goal 裁剪；
- 每个动作具有来源位置和明确的动作后位置；
- 已验证操作依赖使用前置动作完成事实表达；
- SafeSym parser 能接受 domain/problem；
- SafeSym 能完成安全注入；
- Fast Downward 能为已验证 goal 找到计划；
- 计划包含真实链路中的准备步骤，不出现 `order-submitted` 等虚假动作捷径；
- 规划结果应与至少一条真实成功轨迹一致，或能够通过真实 replay 再次执行成功。

## 8. 明确接受的限制

MVP 暂不处理：

- 同一动作的多种替代解法；
- OR 前提；
- 最小或绝对必要前提证明；
- 撤销、清空、退出等反向动作；
- 动作完成事实失效后的非单调业务状态；
- 完整业务状态归一化；
- 所有网站能力的完备覆盖证明；
- 从规划目标反向指导开放探索。

由于 `action-completed` 是累计历史事实，MVP 优先适用于单向推进、没有撤销和重置的验证链路。该限制不影响当前 Practice Shopping 核心闭环实验，但后续扩展到可逆业务流程时必须引入更准确的状态事实和删除效果。

## 9. 主要风险与待验证问题

当前最大的未知不在 PDDL 语法或 SafeSym 桥接，而在去掉答案提示后 VLM 输出的稳定性：

1. 能否稳定生成合适粒度的语义动作；
2. 能否在执行前从页面观察出局部操作顺序；
3. 能否区分业务就绪与仅在 DOM 层面可点击；
4. 能否把动作结果正确归属于刚执行的动作；
5. 能否在同一位置内通过增量观察发现候选可用性的变化；
6. 能否保持动作命名稳定，并让已有动作逐步补充候选和已验证依赖。

因此下一阶段不应先大规模重构。应优先设计最小 VLM 候选与依赖输出契约，并在 Practice Shopping 上进行一次去答案提示实验。实验先验证动作发现、操作顺序、结果归属和依赖图；确认这些能力成立后，再局部接入现有 SemanticPlanningGraph 与 Minimal Semantic PDDL 编译链。

## 10. 与既有设计的关系

本设计不是删除现有三层 reference ontology，而是调整其进入探索流程的时机：

- 位置事实继续作为所有 PDDL 动作的基础约束；
- 普通能力完成事实继续保证同位置动作具有可规划效果；
- MVP 的业务依赖优先由 VLM 页面观察与执行验证产生，并直接使用动作完成事实连接；
- 业务词表和动作契约不再作为候选 prompt 中的完整网站答案；
- 现有 Location PDDL、Explored Trace PDDL 和 Minimal Semantic PDDL 可以继续作为兼容、证据与投影基础；
- 当前 profile action contracts 方案仍是已跑通链路的基线，但下一阶段目标是用观察产生的依赖逐步替代其对候选发现和最终 PDDL 的直接控制。

本设计只确定逻辑边界与 MVP 产物，不确定具体类、字段、模块接口或迁移步骤。详细实现设计应在 Practice Shopping 最小实验契约对齐后另行编写。
