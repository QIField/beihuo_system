# 退货匹配流程：Step3 与场景示例

> 本文为 [06_退货匹配流程](06_退货匹配流程.md) 的续篇，覆盖 Step3（常规订单剩余匹配）与数量分摊场景示例。
> 以程序实现为准（`app/services/stock_safe_service/stock_safe_refund_ref_service.py`）。

## 一、Step3：常规订单剩余匹配退货订单

### 1.1 处理逻辑

1. 分页获取 type=21/22 记录（常规订单有剩余，processed_quantity>0），取同一常规订单 match_count 最大者
2. 为每条记录查找匹配的 type=40 退货订单（step2 未匹配的）
3. 遍历退货订单，分摊常规订单剩余数量
4. 新记录 mode=2（一对多-常规视角），match_count = 当前 + 1

### 1.2 匹配条件（find_matching_refund_order_type3）

- `type = 40`（仅查 step2 未匹配的退货订单）
- 对同一退货订单取 match_count 最大者，且最新记录仍为 type=40
- `customer_id`、`number`、`brand_name`、`pdname`、`frey_no` 完全匹配
- **时间约束**：`refund_create_date > normal_order_create_date`（退货在常规订单之后）
- 同批次内通过 `excluded_refund_ids` 内存去重

### 1.3 分页策略（关键）

- 本页有匹配 → 被匹配记录因新插入更高 match_count 而移出结果集，**保持页码**重新扫描
- 本页无匹配 → 记录未消耗，**页码递增**跳过无法匹配的记录
- 某页返回空 → 遍历完，跳出循环

### 1.4 批后处理

- 批量插入匹配记录（`insert_matched_refund`）
- 删除已匹配退货单的 type=40 记录（`delete_type40_by_refund_ids`）
- 剩余 type=40 更新为 type=41（`batch_update_unmatched_to_type41`）
- 统一同 normal 的 type（`update_type_to_by_normal_order`）

## 二、数量分摊场景示例

**场景：一条退货单匹配多条常规单后用完（type=13）**
- 退货 quantity=-6；常规1 quantity=3，常规2 quantity=3
- 匹配常规1：processed = 3+(-6) = -3，match_count=1 → type=31
- 匹配常规2：processed = 3+(-3) = 0，match_count=2 → type=13

**场景：一条常规单被多条退货单分摊完（type=12）**
- 常规 quantity=5；退货1 quantity=-2，退货2 quantity=-3
- 退货1匹配：processed = 5+(-2) = 3，match_count=1 → type=21
- 退货2匹配：processed = 3+(-3) = 0，match_count=2 → type=12

[← 返回索引](README.md) | [← 上一页：退货匹配流程](06_退货匹配流程.md) | [→ 下一页：销量计算逻辑](08_销量计算逻辑.md)