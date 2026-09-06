# 研究范围与投稿定位

## 暂定题目

**中文：** 通过风险感知开放探索构建证据驱动的网页功能模型

**英文：** Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration

## 研究问题

在自动化的开放式 Web 探索中，如何通过真实交互发现并验证应用功能，同时识别系统自主生成的功能验证行为可能带来的环境风险？

## 任务定义

给定一个未知 Web 应用，系统通过当前 GUI observation 和浏览器交互接口观察并操作环境，不依赖用户预定义任务，而是根据当前环境自动提出候选功能并进行验证。系统在开放探索中反复获得如下交互轨迹：

> observation → GUI interaction → new observation

系统据此持续维护应用级的 **evidence-grounded functional model**，描述：

- 当前 semantic location；
- 该位置支持的 high-level functions；
- 功能的位置约束，以及已观察到的直接动作依赖；
- 功能执行后的 observable functional outcome；
- 功能知识的 verification state；
- 支持结论的 interaction evidence；
- 功能验证动作的二元 potential-risk 判断、主要 risk type 和 supporting evidence。

论文在概念上区分证据生产与知识准入：开放探索过程负责发现候选并产生执行轨迹和前后观察；C1 根据这些证据验证预期 functional outcome，并决定候选是否可作为功能知识进入模型。

系统在候选功能执行前进行风险识别，并将风险信息与功能证据共同记录，为探索监督、事后审查和下游风险决策提供基础。

## 目标读者与 ICLR 契合点

- 面向研究 Web/GUI Agent、自主探索、环境建模、长期记忆和安全交互的读者。
- 核心学习问题是如何从自动探索的真实交互中归纳、验证并持续维护可复用的结构化环境知识。
- 方法强调知识可靠性、证据可追溯性以及探索覆盖率与行为风险之间的权衡。
- 最终模型通过下游规划和行为验证检验应用价值；具体 ICLR 定位仍需结合实验结果与相关工作调研进一步收紧。

## 范围边界

本文主张：

- 在可观察 GUI 范围内建模功能知识，而非恢复网站完整隐藏业务逻辑；
- 显式区分候选动作发现、executor-reported success 与交互证据支持的 functional outcome；只有通过结果验证的候选才可准入功能模型；
- 表达位置约束和已观察到的直接动作依赖，而非一般性业务 precondition 或严格因果模型；
- 在每个已选功能执行前，结合截图、动作语义和预定义风险知识识别潜在副作用；
- 将功能模型保守投影给下游规划与行为验证。

本文不将下列内容作为独立创新：

- VLM、浏览器执行器、PDDL 或下游规划器本身；
- high-level action、persistent frontier 或状态图本身；
- 完整的通用自动化执行系统；
- 功能测试、回归测试和自动任务构造（当前作为未来应用方向）。

本文当前不主张风险检测已经减少实际危险行为，也不主张保证自动探索安全。人工确认、停止和拦截属于可扩展的后续执行策略。
当前方法判断的是系统即将执行的动作，不穷举截图中全部未选择动作，也不覆盖外部攻击场景。
Web 是本文的目标环境而非独立创新；本文也不主张首次研究自动探索安全。风险部分的差异化定位在于：面向无用户预定义任务的功能探索，将已选动作的风险判断与功能假设、执行轨迹和结果证据关联保存。
