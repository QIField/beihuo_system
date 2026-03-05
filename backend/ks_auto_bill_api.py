from flask import Blueprint, request, jsonify, render_template, session
import sys
import os
from threading import Thread
import subprocess
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入服务层
from app.utils.ks_auto_bill_model import (
    get_crmapp_ks_auto_bill_data, 
    get_crmapp_ks_auto_bill_count,
    format_time_only
)

# 导入权限服务
from app.utils.permission_service import org_required

# 定义main.py的路径
main_py_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'ks_auto_bill', 'main.py')

ks_auto_bill_bp = Blueprint('ks_auto_bill', __name__)

def login_required(f):
    """
    登录验证装饰器
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

@ks_auto_bill_bp.route('/ks_auto_bill')
@login_required
@org_required(['fsbbr'])  # 只允许fsbbr组织访问
def ks_auto_bill_page():
    """
    渲染开思自动对单页面
    """
    # 检查用户是否已登录
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('ks_auto_bill.html')

@ks_auto_bill_bp.route('/api/ks_auto_bill_data', methods=['GET'])
@login_required
@org_required(['fsbbr'])  # 只允许fsbbr组织访问
def get_ks_auto_bill_data():
    """
    获取开思自动开单数据API
    用于前端表格展示
    """
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 200))
        
        # 获取搜索参数
        ks_order_id = request.args.get('ks_order_id', '')
        crm_order_id = request.args.get('crm_order_id', '')
        
        # 获取日期范围参数
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # 获取排序参数
        sort_auto_billed_first = request.args.get('sort_auto_billed_first', 'false')
        
        # 如果提供了日期范围，则使用日期范围；否则使用当天日期
        if start_date and end_date:
            target_date = None  # 不使用目标日期，而是使用日期范围
        else:
            # 获取今天日期作为默认查询条件
            target_date = datetime.now().strftime('%Y-%m-%d')
        
        # 使用整合后的函数处理所有情况
        total_count = get_crmapp_ks_auto_bill_count(
            target_date_str=target_date,
            start_date=start_date if start_date and end_date else None,
            end_date=end_date if start_date and end_date else None,
            ks_order_id=ks_order_id,
            crm_order_id=crm_order_id
        )
        
        records = get_crmapp_ks_auto_bill_data(
            page=page, 
            page_size=limit,
            target_date_str=target_date,
            start_date=start_date if start_date and end_date else None,
            end_date=end_date if start_date and end_date else None,
            ks_order_id=ks_order_id,
            crm_order_id=crm_order_id
        )
        
        # 处理日期格式化 - 仅在展示时格式化
        processed_records = []
        for record in records:
            processed_record = dict(record)
            # 使用model中的format_time_only函数只获取时间部分
            from app.utils.ks_auto_bill_model import format_time_only
            processed_record['time_only'] = format_time_only(processed_record['date'])
            # 将日期字段替换为仅时间格式 HH:MM:SS
            processed_record['date'] = format_time_only(processed_record['date'])
            # 确保所有字段都被包含，包括新增字段
            processed_records.append(processed_record)
        
        # 如果需要将已自动开单的数据置顶，则进行排序
        if sort_auto_billed_first == 'true':
            # 按CRM订单状态排序，"已自动开单"优先
            processed_records.sort(key=lambda x: 0 if x.get('crm_order_status') == '已自动开单' else 1)
        
        # 返回JSON格式数据
        return jsonify({
            'code': 0,
            'msg': '',
            'count': total_count,
            'data': processed_records
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取数据失败: {str(e)}',
            'count': 0,
            'data': []
        })

# 全局变量存储主线程引用
ks_auto_bill_thread = None

def run_main_function():
    """
    直接运行main函数（在当前进程中）
    """
    try:
        # 直接导入并运行main模块，而不是使用子进程
        from app.ks_auto_bill.main import main
        print("✅ 开思自动开单系统已在当前进程中启动")
        # 运行主函数
        main()
    except Exception as e:
        print(f"运行开思自动开单系统时出错: {e}")
        import traceback
        traceback.print_exc()

def check_ks_auto_bill_status():
    """
    检查开思自动开单系统线程状态
    """
    global ks_auto_bill_thread
    if ks_auto_bill_thread is None:
        return {"running": False, "thread": None, "message": "线程未启动"}
    
    is_running = ks_auto_bill_thread.is_alive() if ks_auto_bill_thread else False
    return {
        "running": is_running,
        "thread": id(ks_auto_bill_thread) if ks_auto_bill_thread else None,
        "message": f"线程{'正在运行' if is_running else '已停止'}"
    }

# 在模块加载时自动启动开思自动开单系统
def start_ks_auto_bill_on_startup():
    """应用启动时自动启动开思自动开单系统"""
    print("🚀 正在启动开思自动开单系统...")
    # 使用daemon=False，这样线程不会随主线程退出
    global ks_auto_bill_thread
    ks_auto_bill_thread = Thread(target=run_main_function, daemon=True)  # 改为daemon线程
    ks_auto_bill_thread.start()
    print("✅ 开思自动开单系统已在后台启动")
    
    print(f"🔍 开思自动开单系统已在线程中运行")

# 应用启动时自动运行
start_ks_auto_bill_on_startup()