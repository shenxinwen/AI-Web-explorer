# E004 / C2 覆盖映射账本 v1

本账本将有效运行中每个计入 coverage 的 frozen `core_id` 与其首次具备交互证据的普通 attempt 绑定。`@k` 表示该运行的第 `k` 个普通 attempt；同一 core 在一次运行中只计一次。未列出的 gold 功能未获得 interaction-supported evidence，不计覆盖。

路径、失败目录和 run 有效性以 [c2_execution_status_through_run_03.md](c2_execution_status_through_run_03.md) 为准。此文件是从 `graph.json`、`graph_evidence.json` 与 before/after 截图复查得到的覆盖输入；它不把 replay GUI 动作写入普通 attempt 序列。

## Practice Shopping（16）

| condition | run_01 | run_02 | run_03 |
| --- | --- | --- | --- |
| Random | PS04@2, PS02@3, PS01@4, PS10@6, PS11@7 | PS04@1, PS02@2, PS08@4, PS12@7, PS13@8, PS14@9, PS15@11 | PS02@1, PS04@2, PS10@9, PS11@10 |
| Linear | PS02@1, PS04@9, PS08@10, PS10@11, PS12@13, PS14@15, PS15@16 | PS02@1, PS04@8, PS08@10, PS12@12, PS13@13, PS14@14, PS15@15 | PS02@5, PS04@8, PS08@10, PS10@11, PS12@12, PS13@13, PS14@14, PS15@16 |
| Full | PS02@5, PS04@9, PS08@10, PS10@11, PS12@13, PS14@15, PS15@16 | PS02@2, PS04@8, PS08@10, PS12@12, PS13@13, PS14@14, PS15@15, PS10@17, PS11@18 | PS02@7, PS04@9, PS08@10, PS10@11, PS12@12, PS13@13, PS14@14, PS15@16 |

Practice Full / run_02 的 PS10@17 和 PS11@18 是唯一 replay 后的新增 coverage：一次 replay 的总 GUI 成本为 1。Practice Full / run_01 和 run_03 没有 replay。

## SauceDemo（22）

| condition | run_01 | run_02 | run_03 |
| --- | --- | --- | --- |
| Random | SD01@3 | SD01@1, SD02@2, SD07@5, SD13@6, SD05@7, SD06@8, SD14@10, SD17@13 | SD01@1, SD02@3, SD07@6, SD14@7, SD15@8, SD17@9, SD13@10 |
| Linear | SD01@1, SD02@2, SD05@3, SD03@4, SD07@5, SD12@6, SD14@7, SD15@8, SD16@9, SD20@10 | SD02@3, SD05@4, SD03@5, SD07@6, SD12@7, SD14@8, SD15@9, SD16@10, SD20@11, SD13@14 | SD01@1, SD02@3, SD05@4, SD07@8, SD12@9, SD13@10 |
| Full | SD02@3, SD05@4, SD12@8, SD14@9, SD15@10, SD16@11, SD20@12, SD07@14, SD13@15, SD17@17, SD19@18, SD21@19 | SD01@1, SD02@2, SD05@3, SD03@4, SD07@6, SD12@7, SD13@8, SD14@10, SD15@11, SD16@12, SD20@13, SD17@17, SD19@18, SD21@19 | SD01@2, SD02@3, SD05@4, SD07@8, SD12@9, SD14@10, SD15@11, SD16@12, SD20@13, SD13@17, SD17@19, SD19@20, SD21@21 |

SauceDemo Linear / run_02 的 `checkout_form` 是页面标题为 “Checkout: Your Information” 的稳定页面，已按人工确认映射为 SD15@9 和 SD16@10；该 run 原本报告的 10/22 已包含两项，因此确认不改变 coverage。

SauceDemo Full / run_03 的前三次成功 replay 分别在普通 attempt 18、19、20 后恢复 frontier；其中 SD17@19、SD19@20 以及紧随其后的 SD21@21 共新增 3 项 coverage。三次成功 replay 的 GUI 成本为 5 + 6 + 8 = 19；第四次 replay 以 target-state mismatch 失败，额外成本为 9，因此该 run 的报告总成本为 28 GUI actions、净新增 coverage 为 3。

## 复核状态

- 两条 Full / run_02 的映射已完成既有人工复核。
- SauceDemo Linear / run_02 的 SD15、SD16 位置别名已在本轮人工确认。
- 用户于 2026-09-19 接受覆盖账本 v1；全部条目现为 C2 最终人工确认的 coverage 映射。
