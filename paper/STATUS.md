# 论文状态

> 最后更新：2026-09-04
>
> 维护规则：只记录当前有效结论、证据缺口和下一步；详细内容写入对应专题文件。

## 投稿目标

- 目标会议：ICLR 2027
- 暂定题目：Building Evidence-Grounded Functional Models of Web Applications through Risk-Aware Open-Ended Exploration
- 当前阶段：论文主张与方法框架已从大纲 v3 迁移，风险机制和实验协议待设计

## 当前有效结论

- 研究问题：在无预定义任务和完整功能清单的条件下，通过风险受控的开放式 GUI 交互，将探索经验转化为有真实交互证据支持、可跨任务复用的功能级环境知识。
- 核心模型统一表达 semantic location、high-level function、location constraint、observed direct action dependency、functional outcome、verification state 和 interaction evidence。
- 论文显式区分功能假设、执行器动作完成和由真实交互结果支持的功能知识。
- 三项核心贡献已确定：evidence-grounded functional modeling、execution-grounded open-ended model induction、risk-aware functional verification。
- 下游规划与行为验证用于检验模型价值；PDDL、SafeSym、VLM、浏览器执行器和 persistent frontier 均不作为独立创新。
- 尚无论文级实验结果；所有效果性陈述仍是待验证研究问题。

## 已有资产

- 项目大纲：`../大纲v3.md`
- 项目实验记录：`../docs/experiments/`
- 项目设计与实现记录：`../docs/`

## 主要缺口

- 收紧风险识别、可恢复性、commit boundary 以及 Partially Supported / Incomplete 的判定规则。
- 核实相关工作及正式引用，明确最接近方法和可比实验设定。
- 确定 Web 应用/数据、探索预算、人工标注规范、基线、指标、统计规则及实验矩阵。
- 核查论文方法与当前代码的逐模块映射。
- 冻结可复现环境、模型版本、配置、轨迹与结果工件格式。
- 建立 ICLR LaTex 主稿。

## 下一步

1. 设计并确认 risk-aware functional verification 的具体机制与可检验主张。
2. 完成相关工作检索和对比矩阵，基于最接近工作确定实验基线。
3. 在 `experiments/registry.md` 登记 RQ1–RQ3 的首轮实验协议。
4. 核查代码并填写 `04_method.md` 的实现映射。
5. 建立与 `02_outline.md` 对齐的 ICLR LaTex 主稿。
