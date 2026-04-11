# -*- coding:utf-8 -*-
# @Time    : 2026/4/10
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_status_orders_raw_test.py
# @Software: PyCharm

from app.models.raw_sql_models.wms_status_orders_raw import WmsStatusOrders


print("=" * 60)
print("WmsStatusOrders 测试脚本")
print("=" * 60)

print("\n--- 测试1：根据订单日期查询返回 DataFrame ---")
df = WmsStatusOrders.get_by_orderdate_to_df('2026-04-09')
print(f"查询结果数量: {len(df)}")
if not df.empty:
    print(df.head())

print("\n--- 测试2：根据日期范围查询返回 DataFrame ---")
df_range = WmsStatusOrders.get_by_orderdate_range_to_df('2026-04-01', '2026-04-10')
print(f"日期范围查询结果数量: {len(df_range)}")
if not df_range.empty:
    print(df_range.head())

print("\n--- 测试3：根据 pono 查询单条记录 ---")
pono = "CK0237726040918573761"
order = WmsStatusOrders.get_by_pono(pono)
if order:
    print(f"找到记录: {order.to_dict()}")
else:
    print(f"未找到 pono = {pono} 的记录")

print("\n--- 测试4：根据 pono 数组批量查询 ---")
pono_list = ["CK0237726040918573761"]
orders = WmsStatusOrders.get_by_ponos(pono_list)
print(f"批量查询结果数量: {len(orders)}")
for o in orders:
    print(f"  - {o.pono}: {o.l_name_zh}")

print("\n--- 测试5：批量插入测试数据 ---")
test_data = [
    {
        "type": "3",
        "is_checkupdate": "0",
        "orders_id": "2339414",
        "orders_no": "PICK-KDC9162B",
        "pono": "TEST001",
        "rid": "2339414",
        "frey_no": "860204501",
        "status": "2",
        "partner_sapno": "佛山悦之星汽车服务有限公司",
        "fullname": "佛山悦之星汽车服务有限公司",
        "orderdate": "2026-04-10",
        "name": "测试员",
        "dhdate": "",
        "jhdate": "2026-04-10 19:00:03",
        "qty": "2",
        "toqty": "2",
        "l_name_zh": "测试商品1",
        "wait_pick_num": "0",
        "already_pick_num": "2"
    },
    {
        "type": "3",
        "is_checkupdate": "0",
        "orders_id": "2339415",
        "orders_no": "PICK-KDC9162C",
        "pono": "TEST002",
        "rid": "2339415",
        "frey_no": "860204502",
        "status": "2",
        "partner_sapno": "测试公司",
        "fullname": "测试公司",
        "orderdate": "2026-04-10",
        "name": "测试员2",
        "dhdate": "",
        "jhdate": "2026-04-10 20:00:00",
        "qty": "5",
        "toqty": "5",
        "l_name_zh": "测试商品2",
        "wait_pick_num": "3",
        "already_pick_num": "2"
    }
]

try:
    inserted_count = WmsStatusOrders.batch_upsert(test_data)
    print(f"批量插入/更新成功，影响行数: {inserted_count}")
except Exception as e:
    print(f"批量插入失败: {e}")

print("\n--- 测试完成 ---")
print("=" * 60)
