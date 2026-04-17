"""
安全库存任务服务
整合计算流程：读数据→计算→保存→清理
"""

from datetime import datetime
from .calculation_service import SafetyStockCalculator
from .db_service import SafetyStockDBService


def execute_daily_calculation():
    """
    执行每日安全库存计算
    
    流程：
    1. 初始化数据表
    2. 读取销量数据
    3. 读取库存数据
    4. 读取在途数据
    5. 执行计算
    6. 保存结果
    7. 清理历史数据
    
    Returns:
        int: 计算的产品数量
    """
    print(f"[{datetime.now()}] 开始执行安全库存计算...")
    
    # 1. 初始化数据表
    SafetyStockDBService.init_table()
    print("  ✓ 数据表初始化完成")
    
    # 2. 读取销量数据（近1年）
    print("  → 读取销量数据...")
    sales_data = SafetyStockDBService.get_sales_data()
    print(f"  ✓ 读取到 {len(sales_data)} 个产品的销量数据")
    
    # 3. 读取库存数据
    print("  → 读取库存数据...")
    inventory_data = SafetyStockDBService.get_inventory_data()
    print(f"  ✓ 读取到 {len(inventory_data)} 个产品的库存数据")
    
    # 4. 读取在途数据
    print("  → 读取在途数据...")
    in_transit_data = SafetyStockDBService.get_in_transit_data()
    print(f"  ✓ 读取到 {len(in_transit_data)} 个产品的在途数据")
    
    # 5. 计算安全库存
    print("  → 执行安全库存计算...")
    calculator = SafetyStockCalculator()
    calc_results = calculator.calculate_all(sales_data)
    print(f"  ✓ 完成 {len(calc_results)} 个产品的安全库存计算")
    
    # 6. 合并库存数据，判断状态
    print("  → 合并库存数据并判断状态...")
    final_results = []
    for result in calc_results:
        key = f"{result['oe']}|{result['brand']}"
        
        # 获取库存信息
        inv = inventory_data.get(key, {})
        current_stock = inv.get('stock_qty', 0)
        product_name = inv.get('product_name', '')
        inventory_amount = inv.get('inventory_amount', 0)
        
        # 获取在途数量
        in_transit_qty = in_transit_data.get(key, 0)
        
        # 计算可用库存
        available_stock = current_stock + in_transit_qty
        
        # 判断库存状态
        status_info = calculator.determine_stock_status(
            available_stock,
            result['avg_daily_sales'],
            result['reorder_point'],
            result['target_stock']
        )
        
        final_results.append({
            **result,
            'product_name': product_name,
            'current_stock': current_stock,
            'in_transit_qty': in_transit_qty,
            'available_stock': available_stock,
            'inventory_amount': inventory_amount,
            **status_info
        })
    
    # 7. 保存计算结果
    print("  → 保存计算结果...")
    saved_count = SafetyStockDBService.save_calculation_results(final_results)
    print(f"  ✓ 保存 {saved_count} 条记录")
    
    # 8. 清理30天前的历史数据
    print("  → 清理历史数据...")
    deleted_count = SafetyStockDBService.delete_old_data(keep_days=30)
    print(f"  ✓ 清理 {deleted_count} 条历史记录")
    
    print(f"[{datetime.now()}] 安全库存计算完成！")
    
    return saved_count
