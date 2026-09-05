# 项目决策记录

这份文档记录项目中的关键调整：改了什么、为什么改、影响范围是什么。后续每次做架构、pipeline、数据结构、实验策略或主线清理时，都应该追加一条简短记录。

记录格式：

```text
## YYYY-MM-DD - 决策标题

更改：
- ...

原因：
- ...

影响：
- ...
```

## 2026-09-05 - 以动作条件的 shadow mode 实现最小风险感知

更改：
- 普通探索与 replay 在动作执行前，使用当前截图、已选 high-level action label 和独立 JSON 风险库调用一次 VLM。
- 风险输出收敛为二元 `potential_risk`、一个主要 `risk_type` 和简短 `evidence`；不使用 unknown、严重程度或可逆性字段。
- 风险库集中维护类别、正例和明确低风险反例，prompt 不重复这些例子。
- 风险结果写入探索与 replay 审计工件；当前仅标记不拦截，检测失败时 fail-open。

原因：
- 论文贡献关注开放探索执行过程是否能感知环境和动作可能造成的潜在风险，而非实现完整安全控制框架。
- 截图提供页面语境，动作 label 提供执行意图，版本化风险库提供稳定判定边界；三者足以构成可评估的最小实现。

影响：
- 当前主张限定为“对即将执行的动作进行风险识别”，不等同于扫描页面全部风险或保证安全。
- 下一步实验应评估二元识别、风险类型、证据一致性、上下文敏感性，以及普通探索/replay 的覆盖。

## 2026-08-24 - 收敛为唯一 location-scoped / Minimal Semantic PDDL 主线

更改：
- 删除旧 Trace、Location、Surface PDDL 投影器及对应 CLI、测试和 debug graph 入口。
- 公开 CLI 收敛为 Stagehand 探索、Minimal Semantic PDDL 投影和 SafeSym smoke 三个命令。
- Explorer 默认且仅运行 location-scoped 候选池流程；active path 不再触发 targeted/supplement scan。
- replay 路径动作成功即完成上下文恢复，删除旧 VLM/raw-node checkpoint validator。
- 删除静态固定序列实验脚本，只保留当前动态 SauceDemo 探索脚本。
- 历史 checkpoint 中尚有用的数据字段可继续读取，但不再作为新的运行时分支或公开接口。

原因：
- 多套探索与 PDDL 结构同时存在会掩盖真实主线，使测试通过不能证明当前实验链路有效。
- replay 的职责只是恢复上下文；页面再识别、候选发现和图更新都应由正常 Explorer 负责。

影响：
- 当前生产流固定为 VLM 候选观察、semantic-location 候选池、本地依赖选择、Stagehand 执行、VLM outcome、WebKobeGraph、frontier replay 和 Minimal Semantic PDDL。
- 旧命令和旧投影产物不再兼容；历史设计和实验文档只用于追溯，不代表当前接口。

## 2026-08-23 - Replay 只恢复上下文，并完成 SauceDemo 验收

更改：
- 明确 replay 与正常探索的边界：replay 只把浏览器恢复到已知 frontier，不发现候选、不观察 outcome、
  不写 graph/edge/planning facts，也不修改扫描状态和候选尝试次数。
- replay path 从 raw graph 动作最短路改为 semantic-location 路径：保留位置变化动作，并补入这些动作
  已完成的显式同位置 `requires`；无关的同位置动作不会因为曾经执行过而被重放。
- 路径动作全部成功时默认认为目标位置已恢复，不再调用 VLM 或要求 raw node 匹配；旧 checkpoint
  validator 作为可选兼容开关保留，默认关闭。
- replay 成功后恢复目标 node、semantic location 和既有候选池。第一次正式探索动作后允许使用唯一
  历史 URL pattern 做一次性位置交接；该 URL 机制不进入普通探索的语义位置判断。
- frontier eligibility 以 location candidate memory 为准，避免 raw node affordance 复活位置级已经
  `completed`、`stale` 或重试耗尽的候选。compact graph 同时保留 replay 所需的 action description 和
  `execution_policy`，SauceDemo 登录 replay 继续使用实验脚本中的公开账号凭据覆盖。

原因：
- 从购物车执行 `continue_shopping` 回到已耗尽的商品页时，controller 应恢复到其他仍有 pending 候选的
  frontier，而不是以 `current_state_exhausted` 结束。
- raw graph BFS 会把无关的同位置历史动作纳入路径；replay 末端再次做 VLM 位置命名还可能把同一商品页
  命名成新的 semantic location。两者都会让“恢复上下文”意外承担探索和建模职责。

证据与影响：
- SauceDemo `resume_url_handoff_v1` 从既有 checkpoint 继续，4 次 replay 全部成功；购物车恢复路径为
  `enter_credentials -> submit_login -> view_cart`，没有重复执行无显式依赖的 `add_to_cart`。
- replay 后正常探索继续执行 `continue_shopping`、`cancel_checkout`、`complete_checkout` 和
  `navigate_home`；商品页复用了 `product_catalog` 候选池，没有生成 `product_listing_page` 别名或
  重复执行已完成的商品动作。选择器触发一次多余 replay 的问题已用位置候选状态修复并覆盖回归测试。
- 最新图投影包含 13 条成功边；以登录页到结账完成页为问题时，SafeSym 解析、安全注入、基础规划和
  安全规划均成功。当前最短计划仍可能跳过 `add_to_cart`，因为跨位置持久事实 `cart_has_items` 尚未建模；
  这是下一阶段的业务因果质量问题，不由 replay 承担。

## 2026-08-23 - 清理旧运行时设计

更改：
- 删除 `business_milestone` execution mode、旧 ecommerce smoke CLI/runner、`experiment_plan` 和 milestone prompt。
- 删除 `SemanticExperimentProfile`、`ActionContract` 及其 semantic profile 注入和运行时闭集校验。
- 保留 `BusinessFlowProfile`，仅用于本地结构化事实验证和 planner projection；保留 `targeted/supplement scan`、
  `observed_action` 与 `observe_act` 主线能力。

原因：
- 当前 active path 是 VLM 提候选、本地选择、Stagehand 执行动作并观察结果；旧路径已经不参与主链路，继续保留会造成
  重复维护和入口混淆。

影响：
- CLI 只提供 `observed_action` 和 `observe_act` 两种 Stagehand execution mode，受控 final-order URL 安全校验仍保留。
- 当前文档和测试已与运行时代码对齐；旧实验方案仅作为历史设计记录保留。

## 2026-08-23 - 执行策略、候选重试和当前实验边界对齐

更改：
- 在候选 Prompt 和 backend 之间引入 `execution_policy`：`single_instance` 只执行代表性候选的第一个
  Stagehand Action，`composite` 按顺序执行 `observe` 返回的全部 Action；高层动作只有在全部必要原子步骤
  成功后才进入后续 outcome 观察。
- 将策略字段保存在 `BrowserAction` 和图数据中，并覆盖序列化、恢复和语义投影；当前只使用单动作和组合动作，
  暂不启用 batch。
- 真实 Stagehand runner 的终止边界改为候选级最多尝试 2 次、单 frontier 最多重放 2 次、总重放最多 4 次，
  配合实验级正式动作上限；关闭全局连续无进展提前终止。
- 当前 SauceDemo 实验不启用 semantic experiment profile/action contract；`BusinessFlowProfile` 仍可作为可选的
  本地结构化事实配置。

原因：
- `observe` 可以返回一个高层动作对应的多个原子 UI Action。让 backend 只取 `actions[0]` 会导致登录、结账
  信息等组合动作只填充第一个字段；而对加购等单实例动作执行全部返回结果又会造成重复 mutation。
- VLM 候选不一定可执行，单纯用全局“没有进展”判断无法区分某个候选失败和当前页面真的没有剩余能力。
- 当前实验需要验证执行粒度和语义链路本身，旧 profile 的 `cart_has_items` 等业务事实不能作为 active open
  exploration 的隐式前提。

证据与影响：
- 最新 SauceDemo 无 profile、GPT-4o、`observe_act`、25 步实验完成 13 个正式动作，9 个语义进展，0 次重放，
  以 `current_state_exhausted` 结束；`enter_credentials` 执行 2/2 个原子 Action，`add_to_cart` 观察到 6 个
  目标但只执行 1 个，`complete_checkout_information` 执行 3/3 个原子 Action。
- 结账概览同时产生 `cancel_checkout` 和 `complete_checkout`，调度器按发现顺序先取消，Finish 仍 pending。
  这属于终止动作优先级/调度问题，不是组合动作展开失败。
- 本节记录的初始恢复实验曾有 4 次动作重放失败；该结果已由上方 `resume_url_handoff_v1` 的
  4/4 成功验收取代。当前失败记录会保留动作 ID、目标位置和原因，并继续尝试其他 frontier。
- 语义投影已成功生成包含 9 个成功动作和 5 个位置的 `domain.pddl`；失败的排序/筛选边被排除。未提供显式
  goal 时不生成 `problem.pddl`，当前图也不包含完整的 `complete_checkout`/`place_order` 计划。
- 后续优先补充跨位置业务事实和更多网站上的 replay 泛化验证，不新增站点按钮文本分支或固定流程。

## 2026-08-21 - 恢复完整候选 Prompt，执行端聚焦组合动作展开（历史对照）

更改：
- 通过提交 `fe257bc` 将完整 initial scan Prompt 接入 active path，明确 active surface、位置命名、
  动作粒度、代表性合并、可见/阻塞动作、直接依赖、结果页面和 precision-first 规则。
- 为纯截图观察加入有限的购物车图标提示：在购物、目录或商品页面中，明显的购物车图标可以提出
  `open_cart`/`view_cart` 候选；角标是支持证据但不是必要条件。该提示不规定动作依赖或业务流程。
- 当前候选扫描、动作 outcome 和 Stagehand 实验统一使用 GPT-4o；SauceDemo 动态实验显式选择
  `observe_act`，但通用 CLI 默认仍为 `observed_action`。
- 运行一轮不启用 frontier replay 的 SauceDemo 开放探索，产物保存在
  `outputs/experiments/saucedemo/open_exploration_full_prompt_gpt4o_v2`。

原因：
- Practice Shopping 三次扫描证明完整 Prompt 能稳定把重复商品、筛选和排序归并为代表性动作；
  SauceDemo 图片对照证明购物车图标提示能够恢复此前遗漏的 `view_cart` 候选。
- 最新动态实验在登录页生成正确的高层候选 `enter_credentials`，但 Stagehand `observe -> act` 一次
  只执行用户名字段，暴露出高层语义动作与原子 UI 执行粒度之间的真实接口缺口。
- 候选只是待验证假设；只有真实执行和截图 outcome 成功的动作才进入 SemanticPlanningGraph 与
  PDDL，因此有限的图标召回提示不会直接污染 planner-facing 模型。

影响：
- 下一项主线只处理“一个组合语义动作如何展开为多个原子执行动作”。语义图继续保留粗粒度动作，
  执行 trace 可以包含多个原子步骤；所有必要步骤成功后才记录高层动作 success。
- SauceDemo 公开账号和 selector 覆盖继续只存在于该网站实验脚本，不进入通用产品路径。
- 当前不启用 frontier replay；位置候选耗尽时实验直接结束。后续需要分支恢复时再显式启用
  reset-and-replay，不在本阶段同时调整调度。
- 购物车图标规则是通用视觉提示，不是 SauceDemo 固定动作表，也不为 `open_cart` 硬编码
  `requires=[add_to_cart]`。

## 2026-08-20 - 静态语义 MVP 通过，主线转向执行端验收

更改：
- 使用 Practice Shopping 和 SauceDemo 的真实截图隔离验收候选动作、同位置 `requires`、
  `outcome`、`location_change`、语义位置、`SemanticPlanningGraph`、Minimal Semantic PDDL 和
  SafeSym；截图由外部执行器或受控浏览器操作提供，不把静态结果表述为自动探索能力。
- 初始候选扫描的验收模型使用 `gpt-4o`。代表性动作 prompt 强制把重复对象、筛选维度和排序选项
  参数化合并，同时保留不同语义效果的动作。
- SauceDemo 十个成功动作全部进入语义图，投影无排除项；PDDL、SafeSym 解析、安全注入、基础
  计划和安全计划均成功。
- 静态语义 MVP 通过后，近期主线恢复到执行端验收：给定已选语义动作，验证执行器的元素定位、
  原子执行和下一页面观察获取。短期不为实验重构 `WebKobeExplorer`。
- 确认当前 initial scan 已移除站点答案提示：不接收 profile、完整动作词表、动作契约、预期流程、
  外部任务 goal 或 PDDL goal。SauceDemo 验收未增加专属候选分支。

原因：
- 严格动作前后截图已经证明，同位置依赖、结果判断和位置变化可以在不调用 Stagehand 的情况下
  正常工作；继续增加同类静态页面的边际价值低于验证真实执行稳定性。
- 当前最大的未验证风险已经从“能否形成 SafeSym 可消费的 PDDL”转为“语义动作能否稳定落到
  正确网页控件，并持续返回真实观察”。
- `open_cart` 不应错误依赖 `add_to_cart`。规划器能够跳过加购的真实原因是尚未恢复跨位置持续
  业务事实 `cart_has_items`，而不是购物车入口候选缺少前置动作。

影响：
- 当前可以表述为“语义 MVP 主链成立”，但不能表述为完整因果模型或自动网站覆盖。
- 可以表述为“候选发现中的站点答案硬编码已从 active semantic path 移除”。旧 profile、旧
  targeted/supplement scan、benchmark 参数和固定静态验收序列仍保留，但分别属于兼容代码、
  实验配置或测试夹具，不参与产品 initial scan。本条取代 2026-08-13 对 active path 的旧判断。
- `add_to_cart -> cart_has_items -> proceed_to_checkout` 记录为后续语义增强；它是已知的规划捷径，
  但不阻塞执行端最小实验。
- 下一轮执行实验优先使用现有通用候选和真实页面观察，不引入 SauceDemo 专属动作表、按钮文本
  分支或固定业务脚本。`agentExecute` 与 `observe -> act` 的切换和缓存仍需通过单独证据决定。

## 2026-08-13 - 可行性阶段完成，下一阶段从答案提示转向 reference ontology

> 本条保留上一阶段问题判断；其中关于下一阶段采用 reference ontology、业务事实和 targeted
> scan 的初步方案，已被下方 2026-08-18 的最小动作依赖设计取代。

更改：
- Practice Shopping 真实有界实验已跑通候选发现、Stagehand 执行、业务事实验证、
  SemanticPlanningGraph、Minimal Semantic PDDL、SafeSym 安全注入和 Fast Downward 求解。
- 当前阶段定位为“可行链路已成立”，不再把下一步描述为首次真实实验。
- 明确记录当前 profile 的双重作用：它既统一语义，又把位置、事实、动作示例和契约传入候选
  prompt，因而会提示预期能力。
- 下一阶段保留位置事实、普通事实和业务事实三层词表，但把词表定义为动作后使用的
  reference ontology，而不是探索器需要逐项验证的功能清单。
- 普通动作只记录完成事实；只有验证成功的业务动作才改变持续业务状态、触发 targeted scan，
  并可能影响后续业务动作。

原因：
- 真实实验已经证明系统能探索、生成合法 PDDL 并被 SafeSym 求解，但也暴露出 profile 使探索
  带有“已知网站功能后再验证”的答案提示，不能代表真正的开放发现。
- 词表仍然有价值：它可以把不同网站和 VLM 的多种表达统一成稳定 planner-facing 名称；问题
  不在词表本身，而在候选发现之前暴露具体事实、动作契约和预期流程。
- SauceDemo 无 profile 登录 smoke 能自主发现 `login_user`、读取公开测试凭据并进入商品页，
  同时把登录页和商品页都粗略命名为 `swag_labs`，说明操作泛化优于开放语义归纳。

影响：
- 当前代码仍是“开放候选 + profile 引导的闭集语义验证”，文档必须如实说明，不能把下一阶段
  原则写成已经实现。
- 下一阶段设计应优先拆分 candidate discovery 与 after-action normalization，而不是立即为
  第二个网站增加一份包含完整答案的专属 profile。
- 未观察到的词表条目不应进入 Domain，也不应被视为探索覆盖缺失；词表外普通能力应允许保留
  为生成事实，词表外业务事实仍需更严格验证。
- 当前已知实验问题包括：`place_order` 结果被重复建模为无前提 `order_submitted` 捷径，以及
  `filter_products` 明显成功但 `completion_facts` 缺失而生成无效果 action。

## 2026-08-18 - 下一阶段采用最小动作依赖闭环

实施状态（2026-08-18）：该闭环已接入 location-scoped active path，并完成离线回归。initial
响应采用严格 `actions` schema；超额、缺字段、悬空/循环依赖均 fail closed。只有 `success`
动作产生完成事实和位置转移；`failed/uncertain` 不创建新位置、候选池或语义进展。新路径的
Practice Shopping 真实 VLM、SafeSym 与 planner 联合验收仍待执行。

更改：
- 新位置首次候选扫描只返回明确动作及同位置 `requires`，不再要求候选阶段输出区域分类、
  事实词表映射或永久动作类型。
- 本地候选池根据前置动作的 `success` 状态推导动作是否可调度；前置动作终态失败时，依赖动作
  进入 `blocked_by_failed_requirement`。
- 动作后 VLM 观察收缩为 `outcome`、布尔 `location_change` 和简短 `evidence`。
- 本地根据执行成功的动作生成位置限定的完成 predicate；只有成功动作和成功依赖边进入
  SemanticPlanningGraph 与 PDDL。
- 新路径绕开 profile 驱动的 targeted scan、supplement scan 和当前十四字段 Visual Delta 响应。
- 候选 VLM、动作后结果观察与 Stagehand 执行统一默认使用 `gpt-4o`。三条调用链仍保持独立配置，
  但当前实验不再使用 `gpt-4o-mini` 或 DeepSeek 作为默认执行模型。

原因：
- 当前主要目标是生成因果关系基本正确、可被 SafeSym 消费和求解的 PDDL，不需要让一次 VLM
  调用同时完成页面分类、事实归纳、动作分类、依赖推断和规划 effect 生成。
- `actions + requires` 足以表达当前页面上的明确操作顺序；真实执行和前后观察负责验证动作，
  本地状态负责稳定记录。
- 减少返回字段可以降低格式错误和字段间矛盾，也避免旧 profile 继续向候选发现泄漏完整答案。

影响：
- 每个新语义位置当前只做一次扫描。首次观察无法看到或合理推断、且只在前置动作完成后动态
  出现的新动作，暂时允许遗漏。
- 本轮验收重精度而非召回率：可以漏动作，但识别出的动作、依赖和位置变化必须基本正确。
- Practice Shopping 作为首个验证网站，但不得按其按钮文本、固定动作 ID 或完整流程写专用分支。
- 详细设计和验收标准见
  `docs/superpowers/specs/2026-08-18-location-candidate-dependency-integration-design.zh-CN.md`。

## 2026-08-20 - 分开验收探索执行与语义提取能力

更改：
- 将当前能力划分为“探索执行链”和“语义提取与建模链”。Stagehand 负责执行已选择动作并取得
  新观察；VLM 候选/依赖提取、动作后结果判断、本地候选记忆、语义投影、PDDL 和 SafeSym
  归入后者。
- 近期暂停新的完整 Stagehand 探索轮次，优先使用 Practice Shopping 已有真实截图开展静态实验。
  截图序列作为外部执行器提供的观察，只验收语义信息质量和后续规划结构。
- 记录一次性执行层小实验结果：Stagehand `observe -> act` 能正确识别并执行 Category 下拉框
  选择 Electronics；该方向尚未接入主线，也尚未实现跨运行 Action 缓存。

原因：
- 已有真实实验已经证明端到端链路与执行能力基本可行，但 Stagehand `agentExecute` 的上下文和
  token 开销会干扰当前对 VLM 语义结构本身的判断。
- 初始候选扫描和动作后观察都以截图为主要输入；位置候选记忆、SemanticPlanningGraph、PDDL
  编译和 SafeSym 求解也不要求动作必须由 Stagehand 执行，因此可以隔离验收。
- 当前最重要的问题是确认：在没有 profile 答案提示时，系统是否能提取真实动作、正确的
  `requires`、位置变化和完成关系，而不是再次证明浏览器可以点击控件。

影响：
- 静态实验可以验收候选精度、虚假依赖、操作顺序、空候选页面、位置判断、本地依赖解锁以及
  PDDL 的合法性和可规划性；不验收元素定位、真实运行时约束、reset/replay、断点恢复和自动
  到达截图状态。
- 当前仅是能力和数据边界可分离；`WebKobeExplorer` 仍在同一循环中编排执行、观察和图写入，
  因此文档不得宣称已经形成两个完全独立的产品 pipeline。
- 短期使用薄的离线实验编排复用现有模块，不为实验目的重构主 Explorer。静态验收通过后，再
  决定是否把普通原子动作从 `agentExecute` 切换为 `observe -> act` 并加入持久缓存。

## 2026-08-13 - 当前主线收敛为 location-scoped 开放探索与 Minimal Semantic PDDL

> 若下方历史决策与本条冲突，以本条和当前 overview/structure 文档为准。

更改：
- 探索以语义位置为候选池边界，按 `(semantic location, canonical action)` 去重；普通能力事实、业务事实和位置事实分离。
- 同位置普通变化继承候选池；业务事实变化触发 targeted scan；只有明显业务 surface 变化才创建新位置。
- 当前路径耗尽后允许通过 `reset + stored actions` 重放到其他 frontier；重放只恢复断点，不修改图、候选、planning facts、扫描状态或尝试次数。
- checkpoint 持久化 location memory、正式动作预算和 replay 指标，支持在已有图上继续实验。
- 当前 planner-facing 验收路径改为 `SemanticPlanningGraph -> Minimal Semantic domain/problem PDDL -> SafeSym`；PDDL goal 不反向驱动探索。
- 有界终止采用参数化正式动作、连续无进展、候选重试、单 frontier replay 和总 replay 限制。

原因：
- 需要同时解决旧 forward-only 路径的深度不足和逐 raw-state 建模造成的线性依赖，同时保留开放探索属性。
- 位置内去重可以避免排序、筛选、加购等动作在细碎状态上反复执行；位置、能力和业务事实分离可以生成更简洁且可规划的 PDDL。
- 浏览器回退不可靠，reset 后重放已验证动作路径是当前最小可行的深层 frontier 恢复方式。

影响：
- 旧的“当前节点候选耗尽即结束”与“只生成 Phase A domain”的描述不再代表 active 主线。
- 当前实现可以离线生成同时含位置和业务事实的 `domain.pddl` / `problem.pddl`，下一步用真实 Practice Shopping 有界实验验证候选质量、深层 replay 和 SafeSym 求解结果。
- 当前仍有一定硬编码：`practice_shopping_feasibility` 词表、`cart_count/item_count -> cart_has_items` 结构化捷径、`cart_non_empty` 摘要标志、CLI profile 注册、受控下单 URL，以及独立旧 ecommerce benchmark 的固定步骤。
- profile 词表、测试数据和精确下单 URL 属于实验配置或安全边界；后续泛化优先把结构化事实映射迁入可配置 profile，并支持外部 profile 加载。

## 2026-08-10 - 对齐当前主线的观察、图和规划职责

更改：
- VLM Visual Affordance 只提出业务动作候选假设；本地逻辑选择一个候选，Stagehand 负责执行尝试，动作后观察负责验证可见结果。候选能力不等于已验证转换，只有成功且有观察证据支持的 edge 才能作为已验证转换。
- `graph.json` 是可独立加载的紧凑 Raw Graph；详细执行证据通过 `graph_evidence.json` sidecar 和 `evidence_ref` 保留，`raw_graph.json` 保留输入 JSON 的原始形状。每个完成动作后由 checkpoint 配对保存 embedding、trace、graph/evidence；可用 `--resume-graph` 显式恢复到新浏览器并重放稳定路径，failed/inflight 动作只有精确 `--resume-retry-action` 才可重试；不恢复 cookies、localStorage 或浏览器进程。
- `planning_abstraction.py` 离线把可保守合并的 presentation-equivalent raw observations 归入 Planning Graph，并聚合候选能力及精确观察 provenance；`planning_graph.json` 与 `planning_abstraction_report.json` 是离线抽象/审计产物，sidecar 不参与 PDDL。
- profile facts 是本地 verifier 确认的、强但不完整的语义锚点/状态分界和候选谓词词表，不是网页状态全集；Visual Delta 不接收 profile facts。Visual observations 只保留在 `execution_trace.metadata.visual_delta_trace`，不进入 `PlanningState`、planning transitions、target matching planning facts 或 Phase A PDDL。embedding 只用于状态记忆、相似匹配和局部动作去重，不定义 node identity，也不是 PDDL facts。
- Phase A 只从 Planning Graph 投影 canonical locations 和符合条件的、已观察成功的非自环业务转换，生成 `domain.pddl`；本阶段不生成 `problem.pddl`，Visual Delta、supporting facts、raw candidate facts 和 `PlanningState` 都不是 Phase A predicates、preconditions 或 effects。
- 当前探索器是 forward-only，只沿当前路线处理固定候选，候选耗尽或最大步数到达即可结束，不代表全站探索完成。Visual Delta 当前有 bounded 分类实现，但分类体系仍待审查；planning abstraction 已实现并有单测覆盖，但尚未通过新的真实网页实验验证。

原因：
- 需要让候选、执行尝试、观察证据、Raw Graph、Planning Graph 和 planner-facing 投影各自承担单一职责，避免把模型假设当成业务事实。
- 当前阶段优先验证可审查的局部探索和离线抽象，不把一次有界路线的结果表述为全站覆盖，也不在未做新真实网页验证前宣称 planning abstraction 已经经过生产场景验证。

影响：
- 旧 decisions 中直接把 VLM 候选当能力、把 Visual Delta facts 当规划 facts、或把 target matching 描述为独立 planning-fact compatibility gate 的表述，均由本条当前决策取代；历史背景保留，但不得作为当前行为依据。
- 旧 `BusinessTransition` 字段继续兼容读取；新探索不生成 VLM `BusinessTransition` 判断。旧 `business_state_policy.py`、`resolve_business_target_node` 和 `behavior_state_graph.py` 仅作为历史名称保留，不属于当前 active path。

## 2026-08-10 - 真实 Stagehand 实验采用有界 checkpoint

更改：
- 当前真实 Stagehand runner 以请求的最大步数作为主要终止条件。
- 当前节点没有可执行候选时仍可自然提前结束；真实 runner 暂时关闭连续无进展提前终止，通用 controller 仍保留该可选机制。
- 每个完成动作后原子更新 latest 的 embedding、Stagehand trace 和 graph/evidence；正常完成后再写一次最终结果，graph/evidence 是最后提交的配对标记。
- 正常完成后的 `graph.meta.exploration_summary` 记录 `requested_steps`、`steps_completed` 和 `stop_reason`；中途 checkpoint 不写入尚未确定的终止摘要。
- checkpoint 既保护已经完成的探索，也支持显式 resume；`--steps` 只计恢复后的新业务尝试，历史 replay 不消耗预算。恢复不继承 blocked/no-progress 等瞬态状态，目标不匹配 fail-closed，execution events 保留重复尝试供审计。

原因：
- 真实实验中的单步 Stagehand/VLM/embedding 调用可能较慢或被外部中断；必须先保留已完成步骤，避免只在整轮结束时落盘。
- 在当前 forward-only 路径中，连续无进展不应暂时抢先于用户配置的最大步数终止真实 runner。

影响：
- 中断时最近一次成功 checkpoint 仍可读取；未完成的当前动作不会被虚构成 graph edge。
- embedding 或 trace 可能在 graph 提交前包含同轮较新的内容，但 graph/evidence 配对仍是正式 checkpoint 依据。

## 2026-08-06 - 分离 VLM 观察事实与本地 profile facts

更改：
- visual delta VLM prompt 不再携带 `BusinessFlowProfile` 或探索目标，只接收动作和 before/after 观察上下文。
- VLM 返回的 `candidate_added_facts` / `candidate_removed_facts` 默认全部记录为 `generated_fact_ids`，不再因为名称与 profile fact 相同而自动归类。
- `profile_fact_ids` 只接受本地结构化 verifier 明确确认的结果；`WebKobeGraphManager` 不再根据 profile 词表和 fact 名称做隐式推断。

原因：
- profile facts 不是网页状态全集，直接交给 VLM 会让模型把预设词表当成当前页面事实或典型流程提示。
- VLM 观察到的事实可能是 profile 未覆盖的新状态，也可能只是视觉层面的局部变化；名称相同不等于已经满足本地事实定义。
- 需要把“VLM 观察到什么”和“本地系统确认了什么”分开，保留事实来源，方便 graph/PDDL 审查。

影响：
- graph 仍然可以记录更开放的 VLM generated facts，不会因为 profile 词表不完整而丢失状态信息。
- profile facts 的稳定入口变成本地 verifier；后续若要把 generated fact 晋升为 profile fact，必须增加显式规则或审查流程。
- 旧实现中的 `VisualDeltaRequest.profile` 已随 semantic profile 清理删除；`graph manager` 的
  `BusinessFlowProfile` 参数仍仅用于本地结构化规划状态处理，不作为 VLM 输入或自动匹配依据。

## 2026-08-08 - Stagehand tool_choice 异常必须继续动作后观察

更改：
- 仅对 `Thinking mode does not support this tool_choice` 启用继续观察。
- 有明确变化时记录成功转换；无变化时记录 `no_observed_change` 自环。
- 保留原始 error 和 `backend_reported_success=false`。
- Visual observations 只保留在 raw edge trace，不进入 `PlanningState` 或 Phase A PDDL。
- 有明确变化时 target matching 不得回并到 source，但可复用有可靠证据的非 source 历史节点。

原因：
- Stagehand 可能先完成输入、点击或按键，再在工具协议收尾阶段返回该错误。
- 执行器错误不能替代 Web-KOBE 的动作后页面观察。

边界：
- 未知错误仍是失败自环且不调用 Visual Delta。
- 不调整 embedding 阈值、URL/signature 粒度或 Phase A/PDDL 规则。
- 实验默认覆盖 `outputs/experiments/<site>/latest/`，除非显式归档。
- `BusinessAffordance.action_name`、`label`、`target_hint` 的语义重叠留待后续 schema review。

## 2026-08-08 - 探索 loop 收束为 forward-only frontier

更改：
- 当前节点候选耗尽时直接记录 `current_state_exhausted` 并停止，不执行 browser back 或 visit-stack recovery。
- 命中已有节点时继续使用该节点已经建立的固定候选，不重新生成候选。
- 重复已知 `(source, action, target)` transition，或连续没有新节点/新语义转换，计为无进展；最大步数仍然有效。
- runtime memory 只在当前节点或可靠匹配的历史节点上下文内避免同义动作；embedding 相似度用于局部语义去重，不做全局屏蔽。
- Phase A 不再因为 frontier 尚未覆盖全部 affordance 而拒绝节点；部分 frontier 上已经真实观察成功、目标存在的边仍可进入 planning graph，跨 planning-state 的边可进入 `domain.pddl`，失败或缺失目标的边仍排除。

原因：
- 当前阶段需要先验证单向探索和停止边界，browser back、replay 和复杂 DFS recovery 不属于本轮最小闭环。
- 已观察到的业务边即使节点仍有未尝试候选，也应成为 Phase A 的可审查事实；未完成候选不等于已观察边无效。

影响：
- 通用 controller 仍可由 `current_state_exhausted`、可选连续无进展阈值和最大步数决定停止；自 2026-08-10 起，真实 Stagehand runner 关闭连续无进展阈值，主要由最大步数和当前节点候选耗尽决定。
- raw graph 仍原样保留；planning graph/domain 只消费符合现有成功和目标存在规则的 observed edges；presentation 自环保留在 planning graph 中用于审计和能力发现，但不进入 Phase A PDDL。
- 不新增持久化 graph 字段、memory 表或 PDDL 事实来源。

## 2026-08-02 - 将探索策略收束为 frontier / DFS

更改：
- 在 current project overview 中明确 bounded exploration V1 的方向：每个节点维护一组当前可执行业务候选，优先执行未尝试候选。
- 历史计划曾要求当前节点候选耗尽时回退到仍有 frontier 的历史节点；该方案已由 2026-08-08 的 forward-only 决策取代。
- 短期继续从已有 edges 反查 tried / no-op / failed 状态，不急着新增复杂 memory 表；browser back / DFS recovery 后续再接 embedding source relocalization。
- 当时的最小实现曾包含 selector 去重和 browser back visit stack；当前代码已移除 browser back recovery，保留局部候选去重。

原因：
- 最新 Practice Automated Testing Shopping 实验在商品列表和商品详情之间反复切换，说明当前 selector 的“全部尝试后选择非 avoid 成功动作”兜底会制造循环。
- VLM 可以提出候选动作和证据，但没有稳定图记忆；动作是否做过、是否回退、是否终止应由本地 graph/controller 决定。
- 这个方向更接近 SEE / UI-KOBE 类探索图构建的 frontier 思路，同时保持第一版实现足够简单。

影响：
- 后续实验应验证 forward-only 候选耗尽停止和重复节点命中；连续无进展阈值只在通用 controller 中单独评估，真实 Stagehand runner 自 2026-08-10 起不使用该提前终止条件。
- embedding 继续服务 target merge 和当前/可信历史节点上下文内的动作记忆，不在正常探索中每步覆盖 source。
- graph/PDDL 质量评估继续关注候选耗尽、重复节点命中和观察成功边，不把 browser back 次数作为当前闭环指标。

## 2026-08-03 - 将 frontier 指标写入 graph meta（历史记录）

更改：
- `write_web_kobe_graph` 在输出 `graph.json` 时写入 `meta.frontier_metrics`。
- 指标包括每个节点的候选动作数、已尝试动作、未尝试动作、no-op 动作、失败动作、全局 frontier/exhausted 节点数和重复 target 命中数。
- `WebKobeGraphManager` 新增轻量 `meta` 字典；当时的实现还曾记录 visit-stack backtrack。

原因：
- 后续实验不能只看 node/edge 数量，需要知道每个节点的候选动作是否真的被消耗、是否仍有 frontier、重复节点是否被命中。
- 指标可以由现有 graph 派生，不需要提前引入新的 memory 表或改变 node/edge schema。
- 当时认为 backtrack 不记录为业务 edge，因此需要记录控制层回退次数；该 recovery 方案已被 forward-only 决策取代。

影响：
- 当时计划下一轮实验从 `graph.json` 判断探索是否卡在某个节点、是否因为候选耗尽触发回退、哪些动作被 no-op/failed；当前应改为观察候选耗尽停止和无进展统计。
- 本条关于完整 DFS/backtrack controller 的设计属于历史方案；当前 controller 在当前节点候选耗尽时记录 `current_state_exhausted` 并停止。
- 指标属于诊断/实验质量信息，不进入 PDDL projector。

## 2026-08-03 - controller 改为连续无进展终止（历史记录）

更改：
- `WebKobeExplorationController` 不再遇到单次 `failed_execution` 就终止。
- 新增 `max_consecutive_unproductive_steps`，默认值为 3。
- `failed_execution`、`no_observed_change` 等无进展业务 edge 会累加连续无进展计数；成功业务 edge 会清零。
- 当时将成功的 `control_backtrack` 视为有效探索控制动作；该行为已由当前 `current_state_exhausted` forward-only 边界取代。
- `graph.meta` 记录 `last_step_kind`、`last_step_status`、`consecutive_unproductive_steps` 和 `max_consecutive_unproductive_steps`。

原因：
- 开放探索中失败是正常试错信号，不应把系统重新拉回“任务必须每步成功”的执行器逻辑。
- 用户明确要求业务动作也允许失败，只有连续失败或连续无进展后才终止并记录。
- 当时认为 backtrack 属于探索控制动作；当前不执行 browser back，重复已知 transition 和无新 graph information 会计为无进展。

影响：
- 实验仍可继续越过偶发的 Stagehand 执行失败、no-op 或模型适配异常，直至连续无进展阈值或其他停止条件命中。
- stop reason 更符合探索语义：`current_state_exhausted` 表示当前节点候选耗尽，`consecutive_unproductive_steps` 表示连续无进展耗尽。
- 后续真实实验需要评估默认阈值 3 是否合适。

## 2026-08-02 - 将 Stagehand thinking/tool_choice 异常视为非致命执行异常

更改：
- `WebKobeExplorer._edge_status` 遇到 `Thinking mode does not support this tool_choice` 时，不再直接返回 `failed_execution`。
- 如果该异常伴随 observed delta 或 planning delta fact change，edge 仍记录为 `succeeded_with_observed_change`。
- 如果没有可见变化，则记录为 `no_observed_change`，让 controller 继续探索并由本地动作记忆避开该 no-op 动作。

原因：
- 该异常来自所选模型与 Stagehand thinking/tool_choice 参数的适配问题，不一定代表浏览器动作没有执行。
- 用户已明确该异常应作为非阻塞异常处理；实验不应因为这个已知适配异常提前终止。
- 将无变化情况记为 no-op，可以保留诊断信息，又能让探索继续尝试其他候选动作。

影响：
- Practice Automated Testing 这类实验后续不会因为单纯 `Thinking mode does not support this tool_choice` 停在 failed_action。
- 若页面确实没有变化，该动作会进入当前节点的 no-op/avoid 记忆，后续选择器可以尝试其他业务动作。
- 真正的未知执行错误仍保持 `failed_execution`，继续作为实验终止信号。

## 2026-08-02 - 正常探索 source 定位信任执行轨迹

更改：
- `WebKobeExplorer._resolve_current_source_id` 在当前节点指针有效时，不再接受 embedding source match 把 source 拉回其他相似节点。
- source embedding match 保留为 metadata / recovery 信号；正常探索的 source 默认由上一条成功 edge 的 target 维护。
- 更新 overview，明确 source 定位、target matching、recovery 的职责边界。

原因：
- 探索过程中系统自己知道上一条边的 target。只要浏览器没有被外部打断，当前节点指针比每步 embedding 重新定位更可靠。
- 之前实验出现过 embedding 把后续动作 source 拉回相似旧节点，导致 PDDL precondition 和 graph source 错位。
- 现有 GUI exploration 工作通常会在动作后识别/匹配 target，并在回退、恢复或离线审查时做状态匹配；不应让相似度每步覆盖执行轨迹。

影响：
- 常规探索链路变为：current node pointer 决定 source，动作后 target matching 决定是否复用旧节点或创建新节点。
- embedding 的主职责收窄为 target merge、recovery、相似节点动作记忆和后续图审查。
- 后续实现 browser back / DFS recovery 时，可以显式进入 recovery 模式再使用 source embedding relocalization。

## 2026-08-02 - 接入动作后 target matching V1（历史实现；兼容性 gate 已被 2026-08-10 当前决策取代）

更改：
- `WebKobeExplorer` 在动作执行后、写入目标节点前，新增 target matching 阶段。
- target matching 使用动作后的 state summary、planning_transition.post_facts、visual summary 和现有 state embeddings 查找相似目标节点。
- 历史实现曾要求 embedding 判断为 `same` 且 planning facts 兼容时才复用已有目标节点；该独立 planning-fact compatibility gate 已被 2026-08-10 当前决策取代。
- edge execution metadata 新增 `target_state_match`，用于实验报告审查匹配状态、分数和是否被接受。
- 同步修正无 business profile 的低层探索推进：当普通 observed delta 成功发生且没有 business/planning transition 时，也允许当前节点指针推进，避免后续边持续从起点发出并覆盖起点快照。

原因：
- 之前系统有 source matching，但缺少 target matching，导致不同路径到达同一业务状态时容易重复创建节点。
- “防污染”的 state variant 逻辑只能避免把不兼容 facts 写进旧节点，不能解决“不同 node_id 但同一业务状态”的归并问题。
- 第一版需要保守，避免误合并；该版本的 planning facts compatibility 约束属于历史实现，不描述当前 target matching。
- Playwright fixture golden path 暴露了另一个基础图质量问题：无 business profile 场景下当前节点不推进，会污染起点节点快照；这与 target matching 不同，但同属 source/target 定位基本质量。

影响：
- 首页到购物车、商品详情页到购物车等不同路径，后续有机会复用同一个业务节点。
- PDDL 中 `at_xxx_002` / `at_xxx_003` 膨胀有望减少，但需要真实网站实验验证。
- target matching 仍是 V1，不替代后续 UI-KOBE 风格的二次图优化。
- 本地 fixture 探索的 edge source 更接近真实执行轨迹，避免所有低层动作都从 start node 发散。

## 2026-08-02 - 确立 graph 质量评价原则（历史内容；单层 graph identity / merge-before-create 已被 2026-08-10 双层决策取代）

> 本条保留当时的单层 graph 质量背景；其中“节点表达业务状态唯一性”和“merge-before-create”原则已被 2026-08-10 的 Raw Graph + Planning Graph 决策取代。

更改：
- 在 `docs/current-project-overview.zh-CN.md` 和 `docs/current-project-overview.md` 中新增 graph 质量原则。
- 明确 graph 质量优先看业务状态唯一性，而不是只看是否生成了节点、边和 PDDL。
- 将“相同业务状态还没有稳定合并”提升为当前 P0 问题。

原因：
- 最新 Practice Automated Testing Shopping 8 步实验虽然完整生成了 graph 和 domain，但出现多个 planning facts 相近的节点，例如 `product_details_visible + cart_has_items` 被拆成多个 `product_details` / `cart_with_items` 变体。
- 用户确认的方向是：不同来源路径可以指向同一个业务状态节点，例如首页到购物车、商品详情页到购物车都应复用同一个购物车节点。
- 当前问题的关键不是简单降低某些动作权重，而是让 post-action target state 优先匹配并复用已有业务节点。

影响：
- 后续 graph 质量审查至少要检查：节点唯一性、merge-before-create、边表达路径而节点表达状态、PDDL location predicate 可读性、evidence 可追溯性。
- embedding 不应只作为 metadata 记录，还应参与目标节点定位和合并。
- PDDL 中大量 `at_xxx_002` / `at_xxx_003` 应被视为 graph merge 或命名策略的质量信号，而不是单纯 projector 后处理问题。
- 当前 Raw Graph 允许保留明确、稳定的观察节点；业务语义唯一性改在 Planning Graph 的 grouping 层评价，不能用本条的单层原则约束 Raw observation identity。

## 2026-08-02 - 修正通用探索实验入口与动作记忆边界（部分字段描述已被当前 schema 取代）

更改：
- `web-kobe-stagehand-explore` 的默认 Stagehand execution mode 从 `business_milestone` 改为 `observed_action`，让通用探索入口默认不再生成虚拟 milestone 动作。
- 当时曾以 `expected_change` 描述 VLM 候选预期；该历史字段表述已被当前候选的 `supporting_facts` 语义取代。
- business affordance selector 移除全局 completed action 降权；重复判断回到当前节点或 embedding 命中的相似节点上下文，通过 `tried_action_ids` / `avoid_action_ids` 控制。
- `docs/safesym-bridge.md` 明确：`observed_action` 是通用 bounded exploration 默认路径，`business_milestone` 只作为 legacy fallback 或 checkout benchmark smoke 使用。

原因：
- 通用探索的主线应该是 VLM 提候选、本地 graph/embedding memory 选择和去重、Stagehand 执行选中动作；默认 `business_milestone` 会把实验带回旧任务驱动路径。
- 同名业务动作在不同业务状态下可能合理重复，例如不同商品详情页上的 `add_item_to_cart`，不应被全局 completed action 直接降权。
- 当时认为 `expected_change` 是候选动作排序和人工审查的重要证据；当前候选证据使用 `supporting_facts`，该历史字段描述不代表当前 schema。

影响：
- 下一轮 `web-kobe-stagehand-explore` 实验更接近当前探索方向。
- embedding-assisted memory 的职责更清楚：定位当前/相似节点，并基于这些节点的 tried actions 做重复控制。
- 旧 `web-kobe-ecommerce-stagehand-smoke` 仍可保留为任务驱动 benchmark，不再代表主探索实验。

## 2026-08-02 - 收紧探索职责边界 prompt

更改：
- `business_affordance` 的 VLM 候选动作 prompt 不再要求或暗示 `create new node`、`already tried` 等 graph memory / 建图判断，只要求返回可见业务动作、证据和预期变化。
- generic Stagehand prompt 改为“执行一个已选中的业务动作并停止”；没有已选动作时才作为 fallback 选择一个明显业务动作。
- exploration memory prompt 改为只给 Stagehand 提供上下文，不再要求 Stagehand 自己选择动作。
- 从 VLM 候选动作生成的 `business_intent` 执行指令明确要求只执行该动作，完成或失败后停止，不继续下一个业务目标。

原因：
- VLM 没有稳定 graph 记忆，不应判断动作是否做过、状态是否新、是否应该建节点。
- Stagehand 属于操作层，不应同时承担探索规划职责，否则会和本地 graph / embedding memory 的选择逻辑冲突。
- embedding-assisted memory 才是重复识别、revisit 定位和动作降权的主机制；prompt 只能提供证据和执行约束。

影响：
- 探索链路职责更清楚：VLM 看，Web-KOBE 选，Stagehand 做。
- graph / PDDL 语义更不容易被 prompt 自由规划污染。
- 下一步需要通过真实网站实验验证：VLM 候选动作是否足够好、本地选择是否真正避开重复、Stagehand 是否仍会越界执行多个业务目标。

## 2026-08-02 - 结构化优化电商 profile facts

更改：
- 在 `ecommerce_checkout_profile()` 中补充更通用的电商状态事实：`product_details_visible`、`checkout_user_info_required`、`payment_info_required`、`cart_total_visible`、`invoice_available`、`out_of_stock_visible`。
- 将 checkout 的“需要填写/选择”和“已经完成”拆开描述，降低 VLM 把表单出现误判为信息完成的概率。
- 将 `product_details_visible` 从 generated fact 候选提升为 ecommerce profile fact；VLM 仍可提出未声明的新 generated facts，但默认不进入 PDDL。

原因：
- 最近实验中商品详情、发票、支付方式等状态反复出现，但 profile 词表覆盖不足，导致 VLM 生成临时 facts 或回落到弱节点命名。
- `checkout_user_info_complete` / `payment_info_complete` 语义过重，如果缺少 required 层，VLM 容易过早打上 complete facts。
- 优化 profile facts 可以提升观察质量、节点命名、planning_transition 和 domain PDDL 的稳定性。

影响：
- 电商 profile 的通用性增强，但 graph policy / PDDL projector 仍只通过 profile 接口读取 facts，没有写入电商专有逻辑。
- `product_details_visible` 现在会被归类为 profile fact，而不是 generated fact；相关 visual delta 测试已同步。
- 后续仍需要通过真实实验验证这些 facts 是否减少误判和 `at_product_list_00x` 膨胀。

## 2026-08-01 - 用执行轨迹约束 source matching，并清理 embedding 摘要（历史 compatibility 描述已被当前决策取代）

更改：
- `WebKobeExplorer` 增加轻量级当前节点指针：成功产生有效业务状态转移后，下一步默认从上一条 edge 的 target 节点继续。
- 历史实现曾把 planning facts 不兼容作为 source match 的拒绝条件；当前不把它描述为独立 compatibility gate，source protection 以明确 URL/signature/visual change 为边界。
- `build_state_summary` 对 Stagehand business intent / policy prompt 做摘要清理，embedding 文本优先使用业务动作 label，而不是整段 Stagehand action policy / memory policy。

原因：
- 实验中已经能识别 `checkout_user_info_complete`、`payment_info_complete` 等状态，但后续动作会被 embedding 拉回较早的 `checkout` 节点，导致 PDDL precondition 过宽。
- source edge 表示“动作实际从哪里发生”，不应只由页面相似度决定；页面相似度只能辅助纠偏。
- embedding 应比较页面/业务状态，而不是比较重复的 Stagehand prompt 模板。

影响：
- 业务链路更接近真实执行轨迹，例如 `checkout -> checkout_user_info -> payment_info`，而不是多条边都从 `checkout` 发散。
- PDDL 更有机会生成正确前提，后续 `submit_order` 不应只依赖 `at_checkout`。
- 当前仍未做完整回放/DFS 栈；browser back 后的定位恢复后续还需要单独设计。

## 2026-08-01 - 探索阶段先稳定 domain，并避免同页面状态污染

更改：
- 新增 `compile_web_kobe_graph_to_domain` 和 CLI 命令 `web-kobe-domain-from-graph`，允许从 `WebKobeGraph` 只生成 `domain.pddl`，不要求指定 `goal_node`。
- `WebKobeExplorer` 在目标节点已经存在但 `planning_transition.post_facts` 与该节点已有 `PlanningState` 不兼容时，会生成状态变体节点，而不是把新的 facts 写回旧节点。
- 保留 `web-kobe-pddl-from-graph` 和 `web-kobe-pddl-smoke` 的 problem 生成能力，用作明确 start/goal 后的诊断和 SafeSym smoke。

原因：
- 当前项目仍处于探索建模阶段，主目标是收集网站业务状态、动作和 effects；`problem.pddl` 属于后续规划查询阶段，不应该强行绑定一次探索的临时目标。
- 实验中出现过同 URL/同页面壳被复用后，旧 `shopping` 节点被写入 `cart_has_items` 的污染。页面壳相同不代表业务状态相同。
- domain 可以先作为稳定的、可复用的 planner-facing 模型；problem 应该在用户任务、测试目标或 SafeSym 场景明确后再生成。

影响：
- 探索主产物更清晰：`graph.json`、`state_embeddings.json`、`domain.pddl` 优先；`problem.pddl` 只作为查询/smoke 产物。
- 同页面不同业务 facts 会拆成不同状态节点，降低 PDDL 初始态混入后续 facts 的风险。
- 后续扩大实验步数时，graph 状态边界会更干净，但仍需要继续观察节点数量是否膨胀。

## 2026-07-31 - 将业务节点命名 hint 放回 profile

状态命名方案已由 2026-08-09 的 VLM state label 设计替代：新探索由 Visual Affordance 可选提供 state label，本地仅做技术清洗；profile facts 不再派生节点 label。旧方案的字段和调用链已移除，历史 graph 仍按兼容规则读取。

原因：

- profile facts 会根据网站类型变化，通用 graph policy 不应该认识 `cart_page_visible`、`checkout_started` 等具体业务事实。
- 节点是否 materialize 属于 graph policy；具体 fact 应该怎么命名属于 profile 语义。
- 这样后续新增非电商 profile 时，不需要修改通用 graph policy。

影响：

- PDDL 可读性仍可通过 `node_label` 改善，但命名知识从通用层移回 profile 层。
- 不同网站类型可以定义自己的 state label hints。
- 没有 hint 的 generated/profile facts 仍使用通用后缀规则或 business action fallback。

## 2026-07-31 - 业务节点命名前移到 graph policy

更改：

- 该历史实现后来已被 VLM 自由状态命名和离线 `planning_abstraction.py` 取代；`business_state_policy.resolve_business_target_node` 不属于当前 active path，历史 `BusinessTransition` 记录仅按兼容规则读取。
- 业务节点的 `node_id` 前缀同步使用该语义 label，例如 `cart_with_items__business_*`，而不是退回 `shopping__business_*`。
- PDDL projector 仍只读取 graph 中已有的 `node_label`，不直接调用 LLM/VLM，也不自行猜测网页含义。

原因：

- PDDL 可读性问题主要来自 graph 语义名不足，而不是 projector 缺少后处理。
- 如果把命名逻辑放到 PDDL projector，会让 planner-facing 投影层承担语义解释职责，增加耦合。
- 业务状态是否 materialize 本来就在 graph policy 中判断，因此在这里补充业务节点 label 更自然。

影响：

- 同页业务变化生成的新节点更容易读，PDDL location predicate 也会随之更清楚。
- `node_label` 继续只服务可读性和投影命名，不承担节点唯一身份；唯一身份仍由 `node_id` 负责。
- 仍需后续处理非 materialized 节点、重复 label 和 action naming 的整体可读性。

## 2026-07-31 - 让 graph 记录 generated facts，PDDL 默认保守投影

更改：

- `PlanningState` 新增 `profile_fact_ids` 和 `generated_fact_ids`，用于记录 active facts 的来源。
- `WebKobeGraphManager` 不再用 profile facts 硬过滤 `planning_transition`，而是允许 profile facts 和 generated facts 一起进入 graph 状态。
- `web_kobe_pddl_projector` 默认只投影 profile facts；generated facts 默认留在 graph 中，不进入 PDDL。
- `PddlProjectionOptions` 预留 `include_generated_planning_facts` 开关，供后续实验或晋升策略使用。

原因：

- 开放网页探索会遇到 profile 未覆盖的新业务状态，如果 graph 层丢弃这些状态，会损害探索记忆和人工分析。
- SafeSym 消费的是 planner-facing PDDL，不能让未审核的 VLM-generated facts 默认进入谓词集合。
- 因此需要把“记录事实”和“投影事实”分开：graph 可以更开放，PDDL 默认更保守。

影响：

- 实验 graph JSON 会更完整地保存 profile/generated 两类 facts。
- PDDL 默认输出更稳定，不会因为 VLM 新造 fact 直接漂移。
- 后续仍需要设计 generated facts 的晋升、验证和显式投影策略。

## 2026-07-31 - 建立项目决策记录和项目结构文档

更改：

- 新增 `docs/project-decisions.zh-CN.md`，作为长期维护的项目决策记录。
- 新增 `docs/project-structure.zh-CN.md`，记录中文项目结构、pipeline、模块职责和主要函数。
- 重写 `docs/project-structure.md`，让英文版与当前 Web-KOBE/SafeSym 主线同步。

原因：

- 当前项目方向多次调整，如果只靠对话记忆，后续容易忘记为什么做某个结构选择。
- 项目需要明确分层，避免操作层、观察层、图记忆层、探索策略层和 PDDL 映射层互相污染。
- 后续每次清理或调整数据结构时，需要留下低成本、可审查的决策痕迹。

影响：

- 后续有意义的架构或 pipeline 调整，都应追加本文件。
- `docs/project-structure.md` 和 `docs/project-structure.zh-CN.md` 应作为当前结构事实来源。

## 2026-07-31 - 收窄 current-project-overview 的职责

更改：

- 将 `docs/current-project-overview.md` 和 `docs/current-project-overview.zh-CN.md` 调整为高层接力文档。
- 将详细 pipeline、模块职责和主要函数放入 `docs/project-structure.md` / `docs/project-structure.zh-CN.md`。
- 将“为什么做这个调整”记录在本决策文件中。

原因：

- overview 原本已经承担项目方向、当前问题和下一步优先级的职责。
- 如果再把完整模块结构、pipeline 和决策原因都放进 overview，会造成重复维护和信息漂移。
- 三份文档需要分工清楚：overview 讲“现在在哪”，structure 讲“系统怎么组织”，decisions 讲“为什么这么改”。

影响：

- 后续更新项目方向时优先改 overview。
- 后续更新模块边界或主函数时优先改 project structure。
- 后续做架构或数据结构调整时追加 decision record。

## 2026-07-31 - 删除旧 WebObservedGraph 探索栈

更改：

- 删除旧探索栈源码：
  - `src/ai_web_explorer/safesym_bridge/action_catalog.py`
  - `src/ai_web_explorer/safesym_bridge/effect_inferer.py`
  - `src/ai_web_explorer/safesym_bridge/graph_explorer.py`
  - `src/ai_web_explorer/safesym_bridge/observed_graph.py`
  - `src/ai_web_explorer/safesym_bridge/semantic_resolver.py`
- 删除旧测试：
  - `tests/safesym_bridge/test_semantic_resolver.py`
- 更新 `docs/safesym-bridge.md`，说明旧 `WebObservedGraph` 只作为历史设计存在，不再保留 active source。

原因：

- 当前 CLI 和实验主链路已经使用 `WebKobeGraph`、`WebKobeExplorer`、`WebKobeGraphManager`。
- 旧 `WebObservedGraph` 栈不再被主链路调用，继续留在 `safesym_bridge` 源码主目录会误导后续开发。
- 旧栈包含 SauceDemo 风格 precondition 和旧探索模型，容易让项目重新偏向历史路线。

影响：

- active code path 更清楚：探索图统一使用 `WebKobeGraph`。
- 历史设计仍可从 `docs/superpowers/` 的旧 spec/plan 中查阅。
- 验证结果：`pytest -q` 通过，`243 passed, 2 skipped`。

## 2026-07-31 - 明确 profile facts 的新定位

更改：

- 在项目 overview 和结构文档中明确：profile facts 不应再被理解为网页状态全集。
- profile facts 的定位调整为：

```text
PDDL 候选谓词词表 + 优先观察目标 + 跨网站语义对齐锚点
```

原因：

- 开放网页探索会遇到 profile 没覆盖的新状态。
- 如果 profile facts 继续作为 graph state 硬白名单，VLM 发现的 generated facts 很难进入图记忆。
- 但完全放弃 profile facts 会导致 PDDL 谓词漂移，SafeSym 难以稳定消费。

影响：

- Graph 层应允许记录 profile facts 和 generated facts。
- PDDL 层默认仍保守消费 profile facts。
- 后续需要设计 generated facts 的记录、晋升和投影策略。

## 2026-07-31 - 初次整理 current project overview

更改：

- 重写 `docs/current-project-overview.md` 和 `docs/current-project-overview.zh-CN.md`。
- 初步明确当前方向、pipeline、核心结构职责、主要问题和下一阶段优先级。

原因：

- 原文档包含较多历史实验叙述，主线和问题优先级不够聚焦。
- 项目已经从 task-guided checkout baseline 转向 bounded exploration V1。

影响：

- 该整理后来被“收窄 current-project-overview 的职责”决策修正。
- 当前分工是：overview 只保留高层项目状态；结构细节归 `docs/project-structure.md` 和 `docs/project-structure.zh-CN.md`。

## 2026-08-03 - 删除底层 selector / interactable explored 探索路径

更改：

- 删除旧动作选择模块：
  - `src/ai_web_explorer/grounded_web/llm_action_selector.py`
  - `src/ai_web_explorer/grounded_web/openai_action_selector.py`
- 删除旧 selector 相关测试和本地 fixture golden-path 测试。
- 从 `run_web_kobe_exploration` 中移除 `action_selector` / `selector_trace_path` 参数。
- 从 `WebKobeExplorer` 中移除低层 interactable fallback、`selection_traces` 和 interactable explored 标记调用。
- 从 `WebKobeGraphManager` 中删除 `mark_interactable_explored` / `interactables_for_node`。
- 更新项目结构和 overview 文档，明确低层 DOM interactables 只作为 node evidence / debug 信息，不再作为探索决策或 graph memory 单位。

原因：

- 当前架构已经明确：VLM 生成 business affordances，本地 graph / embedding memory 选择和去重，Stagehand 执行被选中的业务动作。
- 旧 selector 路径会把系统重新带回 selector/locator-driven exploration，与“底层操作交给 Stagehand”的方向冲突。
- `interactable_elements.explored` 会让 graph 层承担操作层细节，和后续业务节点/frontier 记忆模型不一致。

影响：

- 主探索链路不会在没有 business affordances 时回退去点击 DOM interactables。
- 旧 Web-KOBE Playwright selector smoke 能力被移除；如需恢复，可从 Git 历史找回。
- `interactable_elements` 不再输出到 canonical `graph.json` node；运行时 DOM interactables 如需保留，应进入 state summary、embedding matching 或 trace/debug artifacts。

## 2026-08-03 - 固定业务节点候选 frontier，停止 revisit 累积

更改：

- `WebKobeExplorer._record_source_business_affordances` 在当前业务节点已有 `business_affordances` 时直接复用旧 frontier，不再调用 VLM 重新生成候选。
- `WebKobeGraphManager` 在同一 node revisit / target merge 时不再追加新的 `business_affordances`；已有候选非空时保留第一次写入的候选，只有旧节点没有候选时才接收 incoming 候选。
- 新增回归测试，覆盖“已有节点候选不被 revisit 追加”和“已有 frontier 时不再次调用 VLM provider”两个行为。

原因：

- Practice Automated Testing Shopping 实验中，`cart_with_items` 节点因多次 revisit / target merge 从单轮候选累计到 12 个动作，导致 frontier 变成多次访问路径上的动作合集。
- business node 的 frontier 应表示首次观察到该业务状态时的稳定候选清单；后续探索应消费这张清单里的未尝试动作，而不是继续贴新动作。
- 如果同一页面壳下出现真正不同的业务能力，应由 planning facts / target matching 形成不同业务节点，而不是污染已有节点的 frontier。

影响：

- 单个业务节点的候选集合不会随 revisit 继续膨胀。
- `frontier_metrics.candidate_count` 更接近节点首次观察到的业务候选数量，后续 tried / no-op / failed 会在稳定清单上累积。
- checkout 推进排序仍需要后续单独优化；本次只修复候选累计问题，不改变排序策略。

## 2026-08-04 - 收紧 VLM 候选生成上限语义

更改：

- `business_affordance` prompt 明确 `max_actions` 是 upper bound，不是 quota；如果当前页面真实可执行业务动作少于上限，应返回更少动作。
- prompt 明确要求聚焦当前 active business surface；如果 modal、dialog、drawer、form、details view、table row、selected object 等 focused surface 打开，只返回该 surface 内动作和显式离开动作，不为了凑数加入背景页面控件。
- VLM 候选生成 prompt 不再携带 `profile` 和 `current_planning_facts`；profile facts / stages 后续只由本地 selector / policy 用于打分、去重和 planner-facing 语义对齐。
- 本地解析层对 VLM 返回的 `business_affordances` 强制按 `request.max_actions` 截断，防止模型超额返回。
- 新增测试覆盖 prompt 合同和解析层上限。

原因：

- Practice Automated Testing Shopping 实验中，商品详情 modal 状态实际强相关业务动作主要是 `add_to_cart` 和 `close_product_details`，但 VLM 仍返回满 5 个候选，把背景页的 `search_for_items`、`filter_products` 也放入该节点 frontier。
- 候选数量上限应防止候选池过大，而不是暗示 VLM 必须凑满数量。
- VLM 没有稳定 graph memory，不应消费 profile facts 或根据 profile stage 判断动作优先级；否则容易把“典型业务流程”误当成当前可见动作。
- frontier 质量应先由候选生成阶段控制；排序策略不应该承担过滤明显不属于当前业务上下文动作的全部压力。

影响：

- 新实验中商品详情等窄上下文节点可能只生成 2-3 个候选，而不是固定接近 5 个。
- 即使 VLM 超额返回，本地 graph frontier 也不会超过配置上限。
- 后续候选排序应在本地完成：如果业务动作预期变化或执行结果命中 profile facts / stages，再由本地 policy 给予更高分；同时继续加入 action family / no-op / repeated target 惩罚。
