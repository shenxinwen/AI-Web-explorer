# E004 / C2 Pilot 配置 v2

> 状态：已冻结，待运行。v2 仅修复 v1 暴露的运行可靠性与记录问题；不进入论文正式结果。
>
> v1 产物保持原样。v2 使用全新目录，不续跑或替换 v1 runs。

## 实验矩阵

- 网站：SauceDemo、Practice Shopping。
- 方法：Random、Linear、Full。
- 每个网站每种方法运行 1 次，共 6 runs。
- 每个 run 最多 10 个普通候选 action attempts；frontier 自然耗尽可提前结束。
- Random seeds：SauceDemo `4101`，Practice Shopping `4201`。Linear 与 Full 不使用随机选择 seed。
- 输出根目录：`outputs/paper/pilot/E004_c2_v2/`。

## 固定实现与公共参数

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-14 |
| 实现提交 | `72727ce985d25d023fc156da3f6070e0e7c18a7a` |
| 相对 v1 的实现变化 | checkpoint 文件替换遇到瞬时 `PermissionError` 时最多尝试 3 次，间隔 50 ms |
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

除上述 checkpoint 修复外，三种方法的控制变量和唯一有意差异与 v1 相同：

| 方法 | 候选选择 | 依赖检查 | replay |
| --- | --- | --- | --- |
| Random | 固定 seed 随机选择 | 否 | 否 |
| Linear | 现有确定性顺序 | 是 | 否 |
| Full | 与 Linear 相同 | 是 | 是 |

## 预算与记录

- 普通候选 attempt 是共享的 10-step 预算单位。
- Replay GUI 动作不占普通候选预算，单独统计；`Total GUI actions = 普通候选 attempts + replay GUI action attempts`。
- 失败、无变化、uncertain、evidence-incomplete attempts 全部保留。
- Risk detection 以相同 shadow-mode 配置运行，不拦截动作。
- 每条 run 启动前写入 `run_command.txt`；退出后无论成功或失败均写入 `run_status.json`，至少包含开始/结束时间、exit code、完成状态和异常摘要。
- 最终订单/提交动作仅允许在两个受控测试网站中执行。

## 输出布局

```text
outputs/paper/pilot/E004_c2_v2/<site>/<condition>/run_01/
  graph.json
  graph_evidence.json
  stagehand_trace.json
  screenshots/
  run_command.txt
  run_status.json
```

## Pilot 验收

六次运行均保留，无选择性替换。Pilot 通过要求：

1. 方法名和 Random seed 正确写入 graph metadata；
2. 每个普通 attempt 均可导出，失败或截图缺失不会被删除；
3. 功能覆盖率、覆盖增长曲线和有效尝试率可由导出表计算；
4. Full 的 replay GUI 成本及 replay-to-follow-up-attempt 关联可计算；
5. 停止原因和实际使用的普通候选 attempts 可解析；
6. 每条 run 均有命令与退出状态记录。

若 Full 没有发生 replay，必须先确认这是两个网站在 10-attempt pilot 下自然没有 recoverable frontier，不能直接据此进入正式实验。Pilot 通过后仍需用户确认，才可冻结并启动 25-attempt 正式 runs。
