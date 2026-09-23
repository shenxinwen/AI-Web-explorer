# VERA 论文论证地图

> 状态：已获作者确认
>
> 用途：本文件规定 VERA 论文要论证什么、各章节如何共同完成论证，以及现有证据允许主张到什么强度。它不是实验记录、实现说明或正文草稿。后续章节起草与修改应以本文件为内容层约束。

## 1. 一句话中心论点

**中文**

开放式网页功能模型归纳应被视为一个在知识风险与环境交互风险下进行的证据生产过程：智能体既需要依据真实交互结果判断哪些功能主张有资格成为可复用知识，也需要在执行前识别并记录为获得这些证据所采取动作的潜在环境后果。

**English working thesis**

> Open-ended Web functional model induction is a process of evidence production under epistemic and environmental interaction risks: an agent must establish which functional claims are sufficiently supported to become reusable knowledge while making the potential consequences of its evidence-gathering actions explicit before execution.

这句话是全文最高层主张。方法、实验和结果都应服务于它，而不是与它并列。

## 2. 论文希望改变的认识

本文希望推动读者完成三次认识转变：

1. 从“开放探索的主要目标是发现更多页面或动作”，转向“开放探索的目标是生产可供未来任务复用的功能知识”。
2. 从“候选被提出或动作执行完成即可记录为功能”，转向“只有获得预先声明结果的可观察证据支持，功能主张才有资格成为持久知识”。
3. 从“探索动作只是获取知识的技术步骤”，转向“证据采集行为本身会作用于环境，因此其潜在后果也必须成为模型中可追溯的信息”。

如果读者只记住 VERA 有验证器、frontier、replay 和风险判断器，论文叙事即未成功。如果读者接受以上三次认识转变，即使不记得所有实现细节，论文的学术观点仍然成立。

## 3. 应用场景与研究对象

### 3.1 应用场景

智能体进入一个此前未知的 Web 应用。它当前没有单一、预先给定的用户目标，而是要主动认识应用能够做什么，并建立供未来多个任务复用的功能模型。

任务导向式交互适合寻找完成当前请求的路径；开放式探索则适合发现当前目标之外的功能、状态与结果。两者服务于不同目标，本文关注后者在功能模型归纳中的作用。

### 3.2 研究产物

VERA 的主要产物不是页面访问日志，也不是未经筛选的动作集合，而是一个 **evidence-grounded functional model**。其核心知识单元是位置条件下的功能主张：

```text
semantic location + high-level function + frozen expected observable outcome
```

模型还保存：

- 对该主张的 evidence judgment；
- 独立的 knowledge admission decision；
- 支撑判断的交互轨迹和前后观察；
- 与证据采集动作关联的执行前风险记录；
- 位置约束和观察到的直接动作依赖等适用性元数据。

这些内容共同回答两个问题：我们相信网站能够做什么，以及这种认识是如何获得的。

## 4. 中心矛盾：自主性同时扩大能力与风险

开放式探索的价值和困难来自同一个来源：智能体获得了更高的自主性。

为了认识未知网站，智能体必须自主：

1. 选择要探索的状态；
2. 提出待检验的功能假设；
3. 选择并执行用于验证假设的动作；
4. 判断观察结果；
5. 将结论保存为长期知识。

这种自主性产生两类相互关联的风险。

### 4.1 知识风险

候选发现只表示系统提出了一个可能的功能；executor-reported success 只表示某个交互序列被报告为完成。两者都不能单独证明预期的应用级结果已经发生。

如果这些信号被直接持久化，它们会把生成错误、执行误判或不完整观察转化为可被后续规划反复使用的虚假知识。因此，问题不只是“动作有没有执行”，而是“什么证据足以让一条主张成为知识”。

### 4.2 环境交互风险

功能知识不能仅靠被动观察获得。验证未知功能可能要求点击、输入、提交、确认或进入新的工作流。这些动作可能改变账号、数据、权限、通信或交易状态。

动作风险取决于当前页面状态和即将执行的具体交互，而不是高层功能名称脱离上下文后的固定属性。因此，问题也包括“为了获得知识，智能体准备对环境做什么”。

### 4.3 两类风险的统一关系

两类风险不是两个偶然并列的研究方向，而是同一证据生产链的两端：

```text
environmental interaction risk
            ↓
hypothesis → selected action → execution → outcome evidence → admission
                                                          ↓
                                                   epistemic risk
```

- 环境交互风险出现在证据产生之前和过程中；
- 知识风险出现在证据解释与持久化阶段；
- 可追溯 interaction record 将二者连接起来。

## 5. VERA 的研究观点

VERA 的核心观点不是“给探索器增加两个检测模块”，而是：

> 开放式功能模型归纳需要同时管理证据采集行为和知识准入结果。

这产生三个设计原则。

### Principle 1: Claims must precede evidence

系统必须在观察执行结果之前提出功能主张并冻结预期可观察结果。这样，结果证据评价的是一个事前声明的命题，而不是对事后变化的重新解释。

### Principle 2: Knowledge requires outcome evidence

候选发现、执行器完成和功能结果获得支持是三个不同层次。只有可观察证据支持冻结的预期结果时，主张才能进入可供下游使用的知识集合。

### Principle 3: Evidence acquisition is accountable interaction

用于验证功能的动作不是中性的内部计算。系统应在执行前依据当前 GUI 上下文识别潜在环境后果，并把该判断与动作、主张、轨迹及后续结果证据关联保存。

Persistent frontier、dependency-aware selection 和 replay 支持这些原则持续运行：它们恢复尚未完成的验证机会，使系统能够继续生产证据。它们是证据生产机制，而不是全文的独立理论主张。

## 6. 从观点到方法的推导

VERA 的方法应按概念必要性解释，而不是按代码调用顺序介绍。

### 6.1 可检验功能主张

系统在语义位置提出高层功能和预期可观察结果。预期结果在动作执行前冻结，为后续验证提供锚点。

### 6.2 执行前风险记录

对当前 observation 下的已选 browser action 形成风险判断，记录二元风险、主要类型和界面依据。该信息可以作为人工确认、阻断或其他干预策略的输入；本文评价的是风险信号的识别与表达。

### 6.3 真实交互与证据采集

浏览器执行具体动作，系统保存 executor status、动作轨迹、执行前后观察和证据引用。Executor status 是诊断信号，不是功能事实标签。

### 6.4 Evidence judgment 与 knowledge admission

结果判断器依据冻结主张和前后证据产生 Supported、Unsupported 或 Unresolved judgment。独立的 admission indicator 决定该主张是否进入可供下游使用的知识集合。

### 6.5 持续证据生产

未完成假设不会因状态离开、预算结束或一次执行失败而自动消失。Persistent frontier 保存这些验证机会；dependency-aware selection 和 replay 在可恢复上下文中继续验证。

### 6.6 可追溯功能模型

最终模型把 functional claim、risk record、execution trace、outcome evidence、evidence judgment 和 admission decision 连接起来。可追溯性不是额外日志功能，而是双重风险观点在模型表达上的结果。

## 7. 贡献—证据地图

### 7.1 贡献一：Evidence-grounded knowledge admission

**学术主张**

功能验证在开放式探索中不仅用于当前动作恢复，还应作为持久功能知识的准入机制。

**需要区分的对象**

- candidate discovery；
- executor-reported success；
- evidence-supported functional outcome；
- knowledge admission。

**证据角色**

C1 固定相同候选和交互轨迹，只改变知识准入规则。它检验基于证据的准入是否提高 admitted knowledge precision，同时保留 human-supported knowledge。

**主要结论强度**

在冻结的两个网站和 45 条唯一功能主张上，结果证明 candidate discovery 和 executor success 是较弱的知识代理，而 evidence-grounded admission 能够大幅减少未经支持的准入，并保留绝大多数获得支持的功能知识。

### 7.2 贡献二：Persistent evidence production

**学术主张**

可信知识准入需要持续获得真实交互证据；开放探索必须能够保存并恢复跨位置、尚未完成的验证机会。

**机制角色**

- function hypothesis proposal 产生待检验主张；
- dependency-aware selection 优先选择当前可执行的验证；
- persistent frontier 保存未完成主张；
- replay 恢复先前观察到的验证上下文。

**证据角色**

C2 在固定普通 candidate-attempt budget 下比较 Random、Linear 和 Full。其核心问题不是 VERA 是否获得通用探索 SOTA，而是加入可靠知识要求后，系统能否继续产生有用的 evidence-supported functional coverage，以及 replay 为此付出多少额外 GUI 成本。

**主要结论强度**

Full 相对 Linear 获得更高的证据支持功能覆盖，说明保存和恢复未完成验证机会能够扩展可靠知识；额外 replay GUI actions 是该增益必须共同报告的成本。

### 7.3 贡献三：Context-conditioned risk awareness

**学术主张**

证据采集动作的潜在环境后果应在执行前、结合当前 GUI 上下文进行判断，并与所得功能知识的证据链共同保存。

**证据角色**

C3 包含两条互补轨道：

- exploration-linked evaluation 检验风险记录能否覆盖 VERA 实际产生的普通探索动作；
- external context-challenge 隔离视觉上下文对二元判断和风险类型表达的影响。

**主要结论强度**

当前视觉上下文最明确地改善了风险后果类型的 grounding；二元判断表现为更高 recall、较低 precision 的权衡。风险记录为后续干预提供输入，但本文实验聚焦于识别、表达和可审查性。

### 7.4 三项贡献的依赖关系

```text
C2: produce hypotheses and interaction evidence
             ↓                         ↓
C3: characterize pre-action risk   C1: judge outcome evidence
             ↓                         ↓
       accountable acquisition     reliable admission
                     \             /
              traceable functional model
```

- 没有 C2，C1 缺少自然交互证据，C3 缺少真实探索动作；
- 没有 C1，C2 产生的候选和 executor success 可能直接污染模型；
- 没有 C3，模型只表达所得知识，不表达知识获取行为的潜在后果；
- 三者共同服务于中心 thesis，不应被写成三个松散功能模块。

## 8. 章节职责地图

### Abstract

压缩“应用需求—中心矛盾—核心观点—VERA—三项证据—意义”。只保留最有解释力的 headline results，不罗列全部指标和限制。

### Introduction

把读者带入未知网站功能建模场景；解释为什么 open-ended exploration 适合该目标；提出自主性带来的双重风险；给出 evidence production under dual risk 的中心观点；概述 VERA 和三项证据。

Introduction 不承担完整实验协议、全部统计限定或实现字段说明。

### Related Work

围绕三条差异轴组织，而不是列举论文：

1. 既有探索工作把什么作为环境知识；
2. 既有验证工作用 outcome verification 解决什么问题；
3. 既有风险工作在什么对象和目标下判断动作后果。

本节最终应说明 VERA 的差异在于这些方向在 task-free functional model induction 中的连接关系。

### Problem Formulation

定义研究对象和可判定边界：open-ended interaction、location-conditioned functional claim、evidence packet、evidence judgment、admission indicator 和 observation-conditioned action risk。

本节回答“问题是什么”，不提前描述具体模块实现。

### Method

先介绍三条设计原则，再说明 VERA 如何操作化。方法章节应解释每个设计为什么必要，以及它如何对应中心矛盾；系统执行顺序只作为辅助结构。

### Experimental Setup

将每个实验写成对一个可证伪命题的检验。优先说明固定了什么、改变了什么、为什么指标能够回答 RQ，再说明数据和协议。

### Results

按 RQ 给出“答案—主要证据—机制解释—局部边界”。不逐格复述表格，不按实验执行时间叙述。错误分析用于解释机制失效的位置，而不是堆积异常案例。

### Limitations and Ethics

集中讨论外部有效性、检测与干预之间的距离、VLM 和 executor 误差、动态网站知识失效，以及真实环境交互的伦理要求。本节负责完整边界，不要求在此前每一节重复相同免责声明。

### Conclusion

回到论文观点：可靠功能模型不仅取决于发现了什么，也取决于这些知识获得了什么证据，以及为获得证据执行了什么动作。结论不再重复完整实验数字。

## 9. 主张强度阶梯

后续写作应根据证据类型选择动词，而不是统一使用最弱或最强措辞。

### Level A：由定义或系统事实直接成立

可使用：`defines`, `separates`, `records`, `links`, `ensures by construction`。

示例：

> VERA separates executor-reported completion from evidence-based knowledge admission.

### Level B：由受控实验直接支持

可使用：`demonstrates in our controlled setting`, `shows`, `improves`, `reduces`，并在同一句或相邻位置给出评价范围。

示例：

> On the frozen C1 set, evidence-grounded admission improves knowledge precision while retaining nearly all supported claims.

### Level C：由结果模式支持的解释

可使用：`supports`, `indicates`, `is consistent with`。

示例：

> The coverage gains support persistent recovery as a mechanism for extending evidence production across locations.

### Level D：方向性或统计未明确的现象

可使用：`shows a point-estimate trend`, `exhibits a trade-off`, `suggests`。

示例：

> Context-conditioned binary detection exhibits a higher-recall, lower-precision trade-off.

不得为了显得严谨而把 Level A 或 B 全部降级为 `may` 或 `might`；也不得把 Level C 或 D 提升为普遍因果结论。

## 10. 内部 Claim Ceiling

本节只约束作者和 Codex，不应被逐条复制到正文。

### 可以正向主张

- VERA 将开放式功能模型归纳组织为可追溯的证据生产过程；
- 系统明确区分候选、执行器完成、证据判断与知识准入；
- 基于证据的准入在冻结 C1 设置中提高知识 precision，并保留绝大多数 supported knowledge；
- persistent frontier 与 replay 在冻结 C2 设置中提高 evidence-supported functional coverage，且其额外 GUI 成本得到单独核算；
- 当前视觉上下文明确改善了外部 C3 样本上的 acceptable risk-type accuracy；
- 风险记录可以作为人工确认、阻断或其他干预策略的输入；
- 功能主张、动作风险、执行轨迹和结果证据可以在同一模型中关联追溯。

### 需要限定范围的主张

- “improves reliability”应落到 admitted knowledge precision 和 retention，而不是绝对正确性；
- “retains exploration utility”应落到 evidence-supported coverage，而不是通用探索能力；
- “context improves risk awareness”最强证据是风险类型 grounding，二元结果是 recall--precision trade-off；
- “supports safer exploration”只能指为干预提供风险信号和审计基础，不能等同于已经减少实际伤害。

### 不进入当前核心论证

- 通用 Web exploration SOTA；
- 完整业务逻辑、严格因果模型或普遍 precondition 恢复；
- 已经实现并验证的风险阻断策略；
- 已经证明危险行为发生率下降；
- taxonomy、VLM、browser executor、persistent frontier、PDDL 或 SafeSym 本身的首创性；
- 在任务、动作空间、执行器和标签不同的条件下击败异构外部系统；
- 尚未完成的下游规划实验作为第四项贡献。

写作时应优先陈述“本文研究并证明了什么”。只有当读者可能把主张自然外推到上述范围时，才在最合适的位置加入一句范围说明。

## 11. 非核心机制的定位

| 内容 | 在论文中的角色 | 不应被写成 |
| --- | --- | --- |
| VLM | 可替换的候选生成器和判断器 | 新基础模型贡献 |
| Risk taxonomy | 共享的形式化输出词汇 | 独立预测方法或主要消融贡献 |
| Persistent frontier | 保存未完成验证机会 | 全新探索范式 |
| Replay | 恢复证据生产上下文 | 免费的覆盖提升 |
| Direct dependencies | 观察支持的顺序元数据 | 完整业务 precondition 或因果规则 |
| PDDL / SafeSym | 下游保守投影实例 | 第四项核心贡献 |
| External context actions | 供应给风险判断器的挑战样本 | VERA explorer 主动提出的动作 |

## 12. 全文逻辑连接句

后续写作可以围绕以下逻辑连接保持章节一致，但不要求逐字复用。

### 从场景到矛盾

> Open-ended exploration is well matched to reusable functional model induction, but the autonomy required for broad discovery weakens the constraints supplied by a concrete user goal.

### 从矛盾到观点

> The resulting challenge concerns both the evidential status of acquired knowledge and the environmental consequences of acquiring it.

### 从观点到方法

> VERA operationalizes this view by pairing pre-action risk awareness with post-action evidence-based admission in a persistent exploration loop.

### 从方法到实验

> This formulation yields three empirical questions: whether evidence improves admission reliability, whether persistent exploration preserves useful discovery under that requirement, and whether visual context improves the grounding of action risk.

### 从结果到意义

> Together, the results support treating trustworthy environment learning as more than coverage: the agent must account for both what becomes knowledge and how that knowledge was obtained.

## 13. 章节审查问题

每次起草或修改章节后，至少回答：

1. 本节推进了中心 thesis 的哪一步？
2. 本节的第一层结构是概念和论证，还是项目时间线和模块清单？
3. 每项实现细节是否服务于一个已说明的设计原则？
4. 每个实验是否对应一个可证伪命题？
5. 主要结果是否先给答案和意义，再给完整数字？
6. 是否把同一局限在多个位置重复成防御性叙事？
7. 是否把内部 claim ceiling 直接复制成了正文？
8. 是否把实现机制、评价指标或实验编号错误提升成了论文贡献？
9. 是否清楚区分了 candidate discovery、executor success、evidence-supported outcome 和 admission？
10. 是否清楚区分了风险信号、干预接口与已经验证的安全效果？

## 14. 最终论文的理想读者复述

如果论文叙事成功，一位读者应能够这样概括 VERA：

> Task-free Web exploration can build reusable functional knowledge, but autonomous evidence gathering creates two linked problems: unsupported discoveries can pollute persistent knowledge, and the actions used to test them can have environmental consequences. VERA treats exploration as a traceable evidence-production process. It records contextual risk before selected actions, verifies frozen functional claims against post-action observations, and admits only supported claims while preserving unresolved verification opportunities. Controlled studies evaluate the reliability, retained functional coverage, and contextual risk grounding of this design.

这段复述，而不是某个模块名称或单项实验数字，是全文叙事应共同促成的结果。
