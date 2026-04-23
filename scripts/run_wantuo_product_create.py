"""
佛山万拓产品新建脚本
调用数据库模式，只处理 supplier_name = '佛山万拓' 的当天数据
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.utils.crm_product.crm_productAdd.main import process_database_mode_api


def main():
    """
    主函数：运行佛山万拓的产品新建任务
    """
    print("=" * 60)
    print("佛山万拓产品新建脚本")
    print("=" * 60)
    print("筛选条件：")
    print("  - 当天数据")
    print("  - 供应商：佛山万拓")
    print("  - update_msg 包含：物料所属品牌、OE号、产品数据不存在")
    print("=" * 60)
    
    try:
        # 调用数据库模式 API，传入供应商名称
        result = process_database_mode_api(supplier_name='佛山万拓')
        
        if result:
            print("\n" + "=" * 60)
            print("✅ 佛山万拓产品新建任务执行成功")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️ 佛山万拓产品新建任务执行完毕，但可能未处理数据")
            print("=" * 60)
            
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 佛山万拓产品新建任务执行失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
