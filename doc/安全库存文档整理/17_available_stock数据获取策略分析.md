# available_stock 数据获取策略分析

> 核心场景：每日凌晨生成补货报表，供早上查看后下单补货。
> 确认日期：2026-08-08

## 一、核心场景

1. **每日凌晨3:00** → 定时任务跑安全库存计算
2. **生成Excel报表** → 输出包含 available_stock、sellable_days、stock_status 的完整报表
3. **早上查看** → 采购人员根据报表决定当日补货计划
4. **前端展示** → 次要场景，偶尔查看

## 二、当前方案（纯预计算·每日快照模式）

`stock_safe` 表每天凌晨全量刷新，`available_stock` 在定时任务中从 `crmapp_beihuo` 表读取：

```sql
LEFT JOIN crmapp_beihuo b
    ON s.number = b.oe AND s.brand_name = b.品牌 AND s.frey_no = b.物料条码
    AND b.company = :company
```

### 评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 业务匹配度 | ⭐⭐⭐⭐⭐ | 完全匹配"每日快照+报表"场景 |
| 系统性能 | ⭐⭐⭐⭐⭐ | 0次额外查询 |
| 数据一致性 | ⭐⭐⭐⭐⭐ | 报表数据是完整一致的快照 |
| 实现复杂度 | ⭐⭐⭐⭐⭐ | 无需任何额外改动 |

## 三、社区实践

"每日库存快照（Daily Inventory Snapshot）"是补货报表场景的行业标准做法。Handled Commerce、Oracle Retail RMS、易仓ERP、ADempiere ERP 等主流系统均采用此模式。

## 四、结论

**保持当前方案不变**：纯预计算（每日快照）模式。

- 不需要实时查询（核心场景是日频）
- 不需要缓存+主动失效
- 不需要事件驱动架构
- 关键保证：`crmapp_beihuo` 表在 `stock_safe` 刷新之前已完成当日数据同步

[← 返回索引](README.md)