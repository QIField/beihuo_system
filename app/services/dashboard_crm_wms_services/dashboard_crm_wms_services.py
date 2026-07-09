# -*- coding:utf-8 -*-
# @Time    : 2026/06/26 14:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : dashboard_crm_wms_services.py
# @Software: trae-cn
from app.dao.crm.crm_sales_order_dao import dashboard_crm_wms_data
import datetime
def get_dashboard_crm_wms_data(start_date, end_date, keyword='', status=''):
    """
    获取CRM与WMS订单数据
    """
    on_heartbeat()
    data = dashboard_crm_wms_data(start_date, end_date, keyword, status)


    return data






# 心跳上报
def on_heartbeat():
    """
    心跳上报
    """
      # 心跳上报：更新任务最近请求时间
    try:
        from app.core.task_enhancer import load_task_config, save_task_config
        print("="*100)
        print("="*100)
        print("="*100)
        cfg = load_task_config('get_merge_order_list_by_time_tasks')
        if cfg:
            cfg['last_request_time'] = datetime.datetime.now().isoformat()
            save_task_config('get_merge_order_list_by_time_tasks', cfg)
            print("[心跳] get_merge_order_list_by_time_tasks 请求时间已更新")
        else:
            print("[心跳] get_merge_order_list_by_time_tasks 未注册看门狗配置")
        
        cfg2 = load_task_config('get_wms_picking_list_by_pages5_tasks')
        if cfg2:
            cfg2['last_request_time'] = datetime.datetime.now().isoformat()
            save_task_config('get_wms_picking_list_by_pages5_tasks', cfg2)
            print("[心跳] get_wms_picking_list_by_pages5_tasks 请求时间已更新")
        else:
            print("[心跳] get_wms_picking_list_by_pages5_tasks 未注册看门狗配置")
        
        cfg3 = load_task_config('get_wms_picking_list_by_keywd')
        if cfg3:
            cfg3['last_request_time'] = datetime.datetime.now().isoformat()
            save_task_config('get_wms_picking_list_by_keywd', cfg3)
            print("[心跳] get_wms_picking_list_by_keywd 请求时间已更新")
        else:
            print("[心跳] get_wms_picking_list_by_keywd 未注册看门狗配置")
        
    except Exception as e:
        print(f"[心跳] 更新失败: {e}")
