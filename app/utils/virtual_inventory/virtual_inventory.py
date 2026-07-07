from .database import (
    get_db_connection,
    clean_business_time_data,
    clear_all_tables,
    delete_old_data,
)
from .suppliers.changsheng_inventory import start as fetch_changsheng_data
from .suppliers.wantuo_inventory import start as fetch_wantuo_data
from .suppliers.shengwen_inventory import start as fetch_shengwen_data
from .suppliers.tenglong import sql_sever_data
from .suppliers.beiermale import male_bier_start
from .suppliers.aichebeimu import gylqp_start
from .suppliers.robot import fetch_and_process_latest_data
from .suppliers.external import ggg2
from .reports import build_and_push_report
from .brands import load_crm_brand_list, clear_brand_cache
from .persistence import save_supplier_to_virtual_inventory
from .upload import start_b2b_upload_with_brand_mapping
from app.utils.logger_config import get_task_logger



logger = get_task_logger('virtual_inventory')


__all__ = ['main_process']




def main_process():
    """主处理流程"""
    # 清除品牌缓存，确保每次运行都重新加载
    clear_brand_cache()
    
    # 预加载 crm_brand_list 品牌列表到缓存
    logger.info("正在加载 crm_brand_list 品牌列表...")
    load_crm_brand_list()
    
    # 清理当前业务时间范围内的数据
    clean_business_time_data()
    
    # 清空其他表的数据（除了virtual_inventory表）
    clear_all_tables()
    
    # 删除50天前的数据
    delete_old_data()
    
    # 获取所有供应商数据
    sql_sever_data()  # 腾隆数据
    male_bier_start()  # 马勒贝尔数据
    gylqp_start()  # 爱车贝母数据
    fetch_and_process_latest_data()  # 机器人数据
    
    # 获取外部数据
    df2 = ggg2()
    
    # 获取昌盛库存数据
    try:
        logger.info("\n" + "="*60)
        logger.info("开始获取昌盛库存数据")
        logger.info("="*60)
        changsheng_df = fetch_changsheng_data()
        if changsheng_df is not None and not changsheng_df.empty:
            save_supplier_to_virtual_inventory(changsheng_df, "昌盛")
            logger.info(f"昌盛库存数据获取完成，共 {len(changsheng_df)} 条")
        else:
            logger.info("昌盛库存数据为空")
        logger.info("="*60)
    except Exception as e:
        logger.exception(f"获取昌盛库存数据失败")

    # 获取佛山万拓库存数据
    try:
        logger.info("\n" + "="*60)
        logger.info("开始获取佛山万拓库存数据")
        logger.info("="*60)
        wantuo_df = fetch_wantuo_data()
        if wantuo_df is not None and not wantuo_df.empty:
            save_supplier_to_virtual_inventory(wantuo_df, "佛山万拓")
            logger.info(f"佛山万拓库存数据获取完成，共 {len(wantuo_df)} 条")
        else:
            logger.info("佛山万拓库存数据为空")
        logger.info("="*60)
    except Exception as e:
        logger.exception(f"获取佛山万拓库存数据失败")

    # 获取盛旻库存数据
    try:
        logger.info("\n" + "="*60)
        logger.info("开始获取盛旻库存数据")
        logger.info("="*60)
        shengwen_df = fetch_shengwen_data()
        if shengwen_df is not None and not shengwen_df.empty:
            save_supplier_to_virtual_inventory(shengwen_df, "盛旻")
            logger.info(f"盛旻库存数据获取完成，共 {len(shengwen_df)} 条")
        else:
            logger.info("盛旻库存数据为空")
        logger.info("="*60)
    except Exception as e:
        logger.exception(f"获取盛旻库存数据失败")

    # 读取所有数据并整合到虚拟库存表（已通过各模块自动添加）
    db_manager = get_db_connection()
    try:
        # 统计各公司表的数据量
        tables = [
            ('virtual_inventory', '佛山'),
            ('virtual_inventory_zhbbr', '珠海'),
            ('virtual_inventory_zsbbr', '中山'),
            ('virtual_inventory_dgby', '东莞巴友'),
            ('virtual_inventory_dghf', '东莞恒发')
        ]
        for table, name in tables:
            count = db_manager.execute_query(f"SELECT COUNT(*) FROM {table}")[0]['COUNT(*)']
            logger.info(f"[{name}] 虚拟库存表处理了 {count} 条数据")
    finally:
        db_manager.close()
    
    # 上传到B2B系统（使用品牌映射版本），只上传当天数据
    start_b2b_upload_with_brand_mapping(today_only=True)
    
    # 运行CRM产品新建（数据库模式）
    logger.info("\n" + "="*60)
    logger.info("开始运行CRM产品新建（数据库模式）")
    logger.info("="*60)
    try:
        from app.utils.crm_product.crm_productAdd.main import process_database_mode_api
        process_database_mode_api()
        logger.info("="*60)
        logger.info("CRM产品新建完成")
        logger.info("="*60)
    except Exception as e:
        logger.exception(f"CRM产品新建失败")

    # ===== 保存当日统计数据到日志 =====
    logger.info("\n" + "="*60)
    logger.info("开始保存当日统计数据")
    logger.info("="*60)
    try:
        from app.services.virtual_inventory_stats_service import save_recent_statistics

        results = save_recent_statistics(days=1)
        latest_business_date = None
        latest_stats = []
        for result in results:
            if result['code'] == 0:
                data = result['data']
                logger.info(f"[统计日志] 保存成功: {data['business_date']} {data['company']}")
                if latest_business_date is None:
                    latest_business_date = data['business_date']
                if data['business_date'] == latest_business_date:
                    latest_stats.append(data)
            else:
                logger.error(f"[统计日志] 保存失败: {result['msg']}")

        if latest_stats:
            build_and_push_report(latest_business_date, latest_stats)
    except Exception as e:
        logger.exception(f"[统计日志] 保存时出错")
    logger.info("="*60)


if __name__ == '__main__':
    main_process()