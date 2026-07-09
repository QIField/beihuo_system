# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:05
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_orders.py
# @Software: PyCharm
from flask import jsonify
import datetime

from app.api import api_bp
from app.services.dashboard_crm_wms_services import wms_orders


@api_bp.route('/test', methods=['GET'])
def api_test():
    print("api_test")



    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': "test成功"
    })

@api_bp.route('/test2', methods=['GET'])
def api_test2():
    print("api_test2")
    
    # 心跳上报：更新任务最近请求时间
    try:
        from app.core.task_enhancer import load_task_config, save_task_config
        print("="*100)
        print("="*100)
        print("="*100)
        cfg = load_task_config('test_task')
        if cfg:
            cfg['last_request_time'] = datetime.datetime.now().isoformat()
            save_task_config('test_task', cfg)
            print("[心跳] test_task 请求时间已更新")
        else:
            print("[心跳] test_task 未注册看门狗配置")
        
    except Exception as e:
        print(f"[心跳] 更新失败: {e}")
    
    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': "心跳上报成功"
    })