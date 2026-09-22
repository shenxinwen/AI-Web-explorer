# C2 Full / run_02 AI 初标人工复核表

状态说明：`covered` 为至少一条 evidence-complete、interaction-supported 的 AI 初标匹配；`proposed_only` 不计覆盖；`not proposed` 表示有效 run 中未见对应候选。

人工复核结论（2026-09-15）：复核者确认本表列举的功能存在，且全部初始标注无误；下表所有条目的“人工决定”均为 `accept`。此表不替代原始逐 attempt CSV。

## SauceDemo / Full / run_02

有效目录：`outputs/paper/formal/E004_c2_v2/saucedemo/full/run_02/`。AI 初标为 14/22；SD22 因无可见结果不计入。

| core_id | 冻结功能 | AI 初标状态 | attempt | 人工决定 | 备注 |
| --- | --- | --- | --- | --- | --- |
| SD01 | enter credentials | covered | 1 |  | 复合凭据填写 |
| SD02 | submit login | covered | 2 |  |  |
| SD03 | sort products | covered | 4, 14 |  | 14 是 replay 后重复 |
| SD04 | view product details | not proposed | — |  |  |
| SD05 | add one product to cart | covered | 3 |  |  |
| SD06 | remove one product from cart | not proposed | — |  | 仅指商品列表页 |
| SD07 | view cart | covered | 6, 9, 16 |  | 全局入口只计一次 |
| SD08 | detail add product to cart | not proposed | — |  |  |
| SD09 | detail remove product from cart | not proposed | — |  |  |
| SD10 | detail return to products | not proposed | — |  |  |
| SD11 | cart view product details | not proposed | — |  |  |
| SD12 | cart remove one item | covered | 7 |  |  |
| SD13 | cart continue shopping | covered | 8 |  |  |
| SD14 | cart start checkout | covered | 10 |  |  |
| SD15 | complete checkout information | covered | 11 |  | 复合字段填写 |
| SD16 | submit checkout information | covered | 12 |  |  |
| SD17 | cancel checkout information | covered | 17 |  |  |
| SD18 | overview view product details | not proposed | — |  |  |
| SD19 | overview complete checkout | covered | 18 |  |  |
| SD20 | overview cancel checkout | covered | 13 |  |  |
| SD21 | complete return to products | covered | 19 |  |  |
| SD22 | generate order PDF | proposed_only | 20, 21 |  | 无可见下载/结果 |

## Practice Shopping / Full / run_02

有效目录：`outputs/paper/formal/E004_c2_v2/practice_shopping/full/run_02_replacement_03/`。AI 初标为 9/16；attempt 3–4 缺失 after 截图，不计入覆盖。

| core_id | 冻结功能 | AI 初标状态 | attempt | 人工决定 | 备注 |
| --- | --- | --- | --- | --- | --- |
| PS01 | search products | not proposed | — |  |  |
| PS02 | filter products | covered | 2, 5–7 |  | attempt 1 失败；3–4 incomplete |
| PS03 | clear filters | not proposed | — |  |  |
| PS04 | sort products | covered | 8–9 |  | 排序参数不拆分 |
| PS05 | paginate products | not proposed | — |  |  |
| PS06 | view product details | not proposed | — |  |  |
| PS07 | close product details | not proposed | — |  |  |
| PS08 | result-page add product to cart | covered | 10 |  |  |
| PS09 | detail-modal add product to cart | not proposed | — |  |  |
| PS10 | global view cart or checkout | covered | 17 |  | attempt 11 失败不计 |
| PS11 | close checkout / continue shopping | covered | 18 |  |  |
| PS12 | complete billing information | covered | 12 |  |  |
| PS13 | select payment method | covered | 13 |  |  |
| PS14 | complete payment information | covered | 14 |  |  |
| PS15 | place order | covered | 15 |  | 16 为成功页已显示后的重复尝试 |
| PS16 | download invoice | not proposed | — |  |  |
