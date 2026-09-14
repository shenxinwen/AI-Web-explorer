# E004 / C2 Pilot 配置 v1

> 状态：已冻结，待运行。Pilot 仅验证协议、日志和指标是否可执行，不进入论文正式结果。
>
> 冻结后如需修改，创建新版本；不得覆盖本版本产物。

## 实验矩阵

- 网站：SauceDemo、Practice Shopping。
- 方法：Random、Linear、Full。
- 每个网站每种方法运行 1 次，共 6 runs。
- 每个 run 最多 10 个普通候选 action attempts；frontier 自然耗尽可提前结束。
- Random seeds：SauceDemo `4101`，Practice Shopping `4201`。Linear 与 Full 不使用随机选择 seed。
- 输出根目录：`outputs/paper/pilot/E004_c2_v1/`。

## 固定实现与公共参数

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-14 |
| 实现提交 | `0c1f0c4479594eee3bb30b99ce1d00f07233df9c` |
| Stagehand / candidate / outcome / risk 模型 | `gpt-4o` |
| Stagehand execution mode | `observe_act` |
| business profile | `none` |
| max candidates per location | 12 |
| max action attempts per candidate | 2 |
| max VLM scan attempts | 2 |
| max replay attempts per frontier | 2 |
| max total replays | 4（仅 Full 可使用） |
| Candidate prompt SHA-256 | `583439613f0ce52cda8adaeb094d51aab4be6207c37b814e6ffc76b3e3b6566f` |
| Outcome prompt SHA-256 | `1cb2441d2ef6085553af70e5b3b726c0c1ca058946f939194e76c612a2d424f2` |
| Stagehand goal prompt SHA-256 | `7aafdaa0c85c4d79a1d5e22feab68fc35c1c14352e7f7a64008277f02c9406a4` |
| Location exploration SHA-256 | `7031ae07bd8680f9f89b3f5ea9f9245d4c019db6b57ca83088dec14354a96770` |
| Frontier replay SHA-256 | `d8648f10bd974ec4dbc4df8cf3a5510f2233d8e214f622c966c9eaeb50555f95` |

所有条件使用相同入口、模型、prompt、viewport、候选上限、重试规则、executor、outcome observer、风险记录和证据采集。唯一有意差异如下：

| 方法 | 候选选择 | 依赖检查 | replay |
| --- | --- | --- | --- |
| Random | 固定 seed 随机选择 | 否 | 否 |
| Linear | 现有确定性顺序 | 是 | 否 |
| Full | 与 Linear 相同 | 是 | 是 |

## 运行与成本口径

- 普通候选 attempt 是共享的 10-step 预算单位。
- Replay GUI 动作不占普通候选预算；单独报告 attempted steps、completed steps、成功/失败和恢复后的首个普通 attempt。
- Total GUI actions = 普通候选 attempts + replay GUI action attempts。
- 失败、无变化、uncertain、evidence-incomplete attempts 全部保留。
- Risk detection 以相同 shadow-mode 配置运行，不拦截动作；其输出供后续 C3 使用，不作为 C2 成功条件。
- 最终订单/提交动作仅允许在两个受控测试网站中执行。

## 输出布局

每个 run 使用独立目录：

```text
outputs/paper/pilot/E004_c2_v1/<site>/<condition>/run_01/
  graph.json
  graph_evidence.json
  stagehand_trace.json
  screenshots/
  run_command.txt
  run_status.json
```

`<site>` 为 `saucedemo` 或 `practice_shopping`；`<condition>` 为 `random`、`linear` 或 `full`。

## Pilot 验收

六次运行均保留，无选择性替换。Pilot 通过要求：

1. 方法名和 Random seed 正确写入 graph metadata；
2. 每个普通 attempt 均可导出，失败或截图缺失不会被删除；
3. 功能覆盖率、覆盖增长曲线和有效尝试率可由导出表计算；
4. Full 的 replay GUI 成本及 replay-to-follow-up-attempt 关联可计算；
5. 停止原因和实际使用的普通候选 attempts 可解析。

Pilot 通过后仍需用户确认，才可冻结并启动 25-attempt 正式 runs。
