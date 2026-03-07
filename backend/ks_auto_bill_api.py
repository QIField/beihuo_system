from flask import Blueprint, request, jsonify, render_template, session
import sys
import os
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

# 导入进程管理器
from app.core.process_manager import ks_bill_process_manager

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


def run_main_function():
    """
    在子进程中运行开思自动对单主函数
    这个函数会在独立的子进程中执行
    """
    try:
        # 导入并运行main模块
        from app.ks_auto_bill.main import main
        print("✅ 开思自动开单子进程已启动")
        # 运行主函数
        main()
    except Exception as e:
        print(f"❌ 开思自动开单子进程出错: {e}")
        import traceback
        traceback.print_exc()
        # 退出子进程，返回错误码
        sys.exit(1)


def start_ks_auto_bill_process():
    """
    启动开思自动对单子进程
    
    :return: 是否成功启动
    """
    return ks_bill_process_manager.start(run_main_function)


def stop_ks_auto_bill_process():
    """
    停止开思自动对单子进程
    
    :return: 是否成功停止
    """
    return ks_bill_process_manager.stop()


def restart_ks_auto_bill_process():
    """
    重启开思自动对单子进程
    
    :return: 是否成功重启
    """
    return ks_bill_process_manager.restart(run_main_function)


def get_ks_auto_bill_status():
    """
    获取开思自动对单子进程状态
    
    :return: 状态字典
    """
    return ks_bill_process_manager.get_status()


# API路由：控制子进程
@ks_auto_bill_bp.route('/api/ks_auto_bill/control', methods=['POST'])
@login_required
@org_required(['fsbbr'])
def control_ks_auto_bill():
    """
    控制开思自动对单子进程
    
    请求参数:
        action: str - 操作类型 (start/stop/restart/status)
    
    返回:
        code: int - 0表示成功，1表示失败
        msg: str - 提示信息
        data: dict - 状态信息（当action为status时）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 1, 'msg': '请求参数不能为空'}), 400
        
        action = data.get('action')
        
        if action == 'start':
            success = start_ks_auto_bill_process()
            return jsonify({
                'code': 0 if success else 1,
                'msg': '启动成功' if success else '启动失败或进程已在运行',
                'status': get_ks_auto_bill_status()
            })
        
        elif action == 'stop':
            success = stop_ks_auto_bill_process()
            return jsonify({
                'code': 0 if success else 1,
                'msg': '停止成功' if success else '停止失败',
                'status': get_ks_auto_bill_status()
            })
        
        elif action == 'restart':
            success = restart_ks_auto_bill_process()
            return jsonify({
                'code': 0 if success else 1,
                'msg': '重启成功' if success else '重启失败',
                'status': get_ks_auto_bill_status()
            })
        
        elif action == 'status':
            return jsonify({
                'code': 0,
                'msg': '获取状态成功',
                'status': get_ks_auto_bill_status()
            })
        
        else:
            return jsonify({'code': 1, 'msg': f'未知操作: {action}'}), 400
            
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'操作失败: {str(e)}'
        }), 500


# 注意：不再在模块加载时自动启动
# 子进程将通过以下方式启动：
# 1. 手动通过API启动
# 2. 通过APScheduler监控任务自动启动（如果配置了AUTO_START_KS_BILL）
# 3. 在beihuo_system.py中应用启动后启动

print("✅ 开思自动对单API模块已加载（子进程管理模式）")
