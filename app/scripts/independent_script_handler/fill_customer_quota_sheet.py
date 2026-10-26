# -*- coding:utf-8 -*-
# @Time    : 2026/4/24 09:15
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : fill_customer_quota_sheet.py
# @Software: PyCharm

from app.utils.orm.session import orm_session
from app.dao.crm import partner_list_dao
from app.models.orm_models.customer_quota_model import CustomerQuota


def fill_customer_quota(batch_size=100):
    """
    从 partner_list 表读取 partner_id 和 remenber_code 字段，填充到 customer_quota 表
    
    注意：只填充 partner_id 和 remenber_code 两个字段，其他字段保持默认值
    使用分页分批插入，避免一次性处理大量数据
    
    :param batch_size: 每批处理的记录数，默认 100
    """
    print("=" * 60)
    print("开始填充 customer_quota 表")
    print("=" * 60)
    
    with orm_session() as session:
        # 1. 先统计总记录数
        total_count = partner_list_dao.count_all(session)
        print(f"[统计] partner_list 表总共有 {total_count} 条记录")
        print(f"[配置] 每批处理 {batch_size} 条记录")
        
        if total_count == 0:
            print("[警告] partner_list 表没有数据，无需处理")
            return
        
        # 2. 计算需要分多少批
        total_batches = (total_count + batch_size - 1) // batch_size
        print(f"[计划] 总共需要分 {total_batches} 批处理")
        print("-" * 60)
        
        # 3. 分页分批处理
        success_count = 0
        skip_count = 0
        for batch_num in range(total_batches):
            offset = batch_num * batch_size
            current_batch = batch_num + 1
            
            print(f"\n[批次 {current_batch}/{total_batches}] 开始处理第 {current_batch} 批")
            print(f"  - 偏移量: {offset}")
            print(f"  - 批次大小: {batch_size}")
            
            # 读取当前批次的数据
            partners = partner_list_dao.list_by_page(session, offset, batch_size)
            print(f"  - 本批读取到 {len(partners)} 条记录")
            
            # 准备要插入的数据（先检查是否已存在）
            customer_quota_data = []
            for idx, partner in enumerate(partners, 1):
                # 检查该 partner_id 是否已存在
                existing = session.query(CustomerQuota).filter_by(partner_id=partner.partner_id).first()
                if existing:
                    skip_count += 1
                else:
                    data = {
                        'partner_id': partner.partner_id,
                        'remenber_code': partner.remenber_code,
                        'fullname': partner.fullname if hasattr(partner, 'fullname') else None
                    }
                    customer_quota_data.append(data)
                
                # 每处理 20 条打印一次进度（可选，避免刷屏）
                if idx % 20 == 0:
                    print(f"  - 已处理 {idx}/{len(partners)} 条记录（跳过 {skip_count} 条已存在的）")
            
            print(f"  - 本批准备了 {len(customer_quota_data)} 条新数据（跳过 {skip_count} 条已存在的）")
            
            # 批量插入到 customer_quota 表
            if customer_quota_data:
                print(f"  - 正在执行批量插入...")
                try:
                    inserted = CustomerQuota.bulk_insert(session, customer_quota_data)
                    success_count += inserted
                    print(f"  - [成功] 本批成功插入 {inserted} 条新记录")
                except Exception as e:
                    print(f"  - [失败] 本批处理失败: {str(e)}")
                    raise
            else:
                print(f"  - 本批没有新数据需要插入")
            
            # 打印总体进度
            progress = (current_batch / total_batches) * 100
            print(f"[总体进度] {progress:.1f}% ({current_batch}/{total_batches})")
        
        # 4. 完成统计
        print("\n" + "=" * 60)
        print("填充完成！")
        print(f"  - 总记录数: {total_count}")
        print(f"  - 成功插入: {success_count}")
        print(f"  - 跳过已存在: {skip_count}")
        print(f"  - 批次数: {total_batches}")
        print("=" * 60)


if __name__ == "__main__":
    # 可以在这里修改批次大小
    BATCH_SIZE = 100
    fill_customer_quota(batch_size=BATCH_SIZE)
