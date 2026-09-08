# Core-function inventory 与匹配规则 v1

## 目的与边界

该 inventory 只覆盖两个实验网站中稳定、可复现、可直接执行的核心高层功能，用于计算 `core-function recall`。它不是网站全部功能的穷举，也不包含导航栏中的站外功能、主题切换、登录入口等与购物主流程无关的通用控件。

Gold inventory 在查看待评测运行结果之前冻结。系统运行中产生的候选不能反向增加 gold 项；确需修订时必须提升 inventory 版本，并对全部条件重新评分。

## 匹配单位

匹配键由两部分组成：

1. `semantic_location`：动作发生的稳定业务位置；
2. 高层功能的语义效果：以 `function_label` 为准，`accepted_aliases` 只帮助人工判断，不做严格字符串匹配。

一个系统发现最多匹配一个 gold function，一个 gold function 在单次运行中最多计为发现一次。重复执行不增加 recall。对象实例、筛选值、排序值、付款方式等参数差异不拆成多个功能。

## 匹配标签

- `matched`：位置和语义效果均一致，并至少有一个 interaction-supported attempt；
- `proposed_only`：语义可匹配，但没有足够执行证据，不计入 supported core recall；
- `wrong_location`：效果相似但位置不一致；
- `no_match`：gold inventory 中没有对应功能；
- `uncertain`：材料不足，交由人工仲裁，不自动计为 matched。

## 指标

每个网站、每次运行分别计算：

```text
supported core recall = matched gold functions / all gold functions
proposal core recall  = (matched + proposed_only) gold functions / all gold functions
```

主文报告 supported core recall；proposal core recall 用于说明“提出候选”和“获得证据支持”之间的差距。跨网站总体结果使用网站 macro-average。

Precision 仍以 action-attempt 人工标注计算，不能用 core inventory 中不存在某项就直接认定该候选错误，因为 inventory 明确不是全站穷举。

## 人工流程

1. 对每次运行导出唯一的 `semantic_location + action` 列表；
2. 初始匹配结果必须经过人工逐项复核；若使用 AI 预填，AI 不作为独立人工标注者；
3. `uncertain` 和一对多候选必须仲裁；
4. 保存原始 action/attempt ID、匹配到的 `core_id` 和最终标签。
