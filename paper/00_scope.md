# 研究范围与投稿定位

## 暂定题目

**中文：** 通过风险感知开放探索构建证据驱动的网页功能模型

**英文：** Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration

## 研究问题

在没有预定义任务和完整功能清单的情况下，如何通过风险受控的开放式 GUI 交互，将未知 Web 应用中的零散探索经验持续转化为具有真实交互证据支持、可跨任务复用的功能级环境知识？

## 任务定义

给定一个未知 Web 应用，系统只能通过当前 GUI observation 和浏览器交互接口观察并操作环境，不预先获得完整功能清单，也不给定需要完成的具体任务。系统在开放探索中反复获得如下交互轨迹：

> observation → GUI interaction → new observation

系统据此持续维护应用级的 **evidence-grounded functional model**，描述：

- 当前 semantic location；
- 该位置支持的 high-level functions；
- 功能的位置约束，以及已观察到的直接动作依赖；
- 功能执行后的 observable functional outcome；
- 功能知识的 verification state；
- 支持结论的 interaction evidence。

开放探索同时受到风险约束，以减少功能验证产生的不必要高影响或不可逆副作用。

## 目标读者与 ICLR 契合点

- 面向研究 Web/GUI Agent、自主探索、环境建模、长期记忆和安全交互的读者。
- 核心学习问题是如何从任务无关的真实交互中归纳、验证并持续维护可复用的结构化环境知识。
- 方法强调知识可靠性、证据可追溯性以及探索覆盖率与行为风险之间的权衡。
- 最终模型通过下游规划和行为验证检验应用价值；具体 ICLR 定位仍需结合实验结果与相关工作调研进一步收紧。

## 范围边界

本文主张：

- 在可观察 GUI 范围内建模功能知识，而非恢复网站完整隐藏业务逻辑；
- 显式区分 VLM 提出的功能假设、执行器完成的动作以及交互证据支持的功能结论；
- 表达位置约束和已观察到的直接动作依赖，而非一般性业务 precondition 或严格因果模型；
- 通过风险与可恢复性控制功能验证深度；
- 将功能模型保守投影给下游规划与行为验证。

本文不将下列内容作为独立创新：

- VLM、浏览器执行器、PDDL 或下游规划器本身；
- high-level action、persistent frontier 或状态图本身；
- 完整的通用自动化执行系统；
- 功能测试、回归测试和自动任务构造（当前作为未来应用方向）。
