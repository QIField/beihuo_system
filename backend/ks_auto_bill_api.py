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
    format_time_only,
    get_companies,
    get_company_name
)



# 导入统一任务管理器和简化任务
import logging

from app.core.task_manager import task_manager
from app.ks_auto_bill.task import (
    ks_auto_bill_task,
    get_ks_auto_bill_task_status,
    process_orders_once
)

logger = logging.getLogger('ks_auto_bill')

# 导入获取用户当前门店函数
try:
    from beihuo_system import get_user_store
except ImportError:
    # 如果导入失败，定义一个默认实现
    def get_user_store():
        """获取用户当前的门店（用于数据查询）"""
        return session.get('current_org', session.get('store', 'fsbbr'))

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
def ks_auto_bill_page():
    """
    渲染开思自动对单页面
    """
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('ks_auto_bill.html')


@ks_auto_bill_bp.route('/api/ks_auto_bill_data', methods=['GET'])
@login_required
def get_ks_auto_bill_data():
    """
    获取开思自动开单数据API
    用于前端表格展示
    自动根据用户当前所在门店(current_org)筛选数据
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 200))
        
        ks_order_id = request.args.get('ks_order_id', '')
        crm_order_id = request.args.get('crm_order_id', '')
        
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        sort_auto_billed_first = request.args.get('sort_auto_billed_first', 'false')
        
        if start_date and end_date:
            target_date = None
        else:
            target_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取用户当前所在门店（current_org）
        company = get_user_store()
        
        total_count = get_crmapp_ks_auto_bill_count(
            target_date_str=target_date,
            start_date=start_date if start_date and end_date else None,
            end_date=end_date if start_date and end_date else None,
            ks_order_id=ks_order_id,
            crm_order_id=crm_order_id,
            company=company
        )
        
        records = get_crmapp_ks_auto_bill_data(
            page=page, 
            page_size=limit,
            target_date_str=target_date,
            start_date=start_date if start_date and end_date else None,
            end_date=end_date if start_date and end_date else None,
            ks_order_id=ks_order_id,
            crm_order_id=crm_order_id,
            company=company
        )
        
        processed_records = []
        for record in records:
            processed_record = dict(record)
            processed_record['time_only'] = format_time_only(processed_record['date'])
            processed_record['date'] = format_time_only(processed_record['date'])
            # 添加公司名称
            processed_record['company_name'] = get_company_name(processed_record.get('company', ''))
            processed_records.append(processed_record)
        
        if sort_auto_billed_first == 'true':
            processed_records.sort(key=lambda x: 0 if x.get('crm_order_status') == '已自动开单' else 1)
        
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


@ks_auto_bill_bp.route('/api/ks_auto_bill/companies', methods=['GET'])
@login_required
def get_companies_api():
    """
    获取公司列表API
    
    返回:
        code: int - 0表示成功
        data: list - 公司列表，包含code和name
    """
    try:
        companies = get_companies()
        data = [{'code': c, 'name': get_company_name(c)} for c in companies]
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': data
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'获取公司列表失败: {str(e)}',
            'data': []
        })


def start_ks_auto_bill_process():
    """
    立即执行一次开思自动对单任务（手动触发）

    :return: 是否成功启动
    """
    try:
        # 立即提交任务到线程池
        task_manager.submit(ks_auto_bill_task)
        logger.info("[开思自动对单] 已提交手动执行任务")
        return True
    except Exception as e:
        logger.error(f"[开思自动对单] 手动执行失败: {e}")
        return False


def stop_ks_auto_bill_process():
    """
    停止开思自动对单（取消调度）

    :return: 是否成功停止
    """
    try:
        # 从调度器中移除任务（停止定时执行）
        task_manager._scheduler.remove_job('ks_auto_bill_task')
        logger.info("[开思自动对单] 已停止定时任务调度")
        return True
    except Exception as e:
        logger.error(f"[开思自动对单] 停止失败: {e}")
        return False


def restart_ks_auto_bill_process():
    """
    重启开思自动对单（重新调度）

    :return: 是否成功重启
    """
    try:
        # 先停止（如果存在）
        try:
            task_manager._scheduler.remove_job('ks_auto_bill_task')
        except Exception:
            pass
        
        # 重新调度
        task_manager.schedule(
            ks_auto_bill_task,
            'interval',
            'ks_auto_bill_task',
            minutes=1,
            replace_existing=True
        )
        logger.info("[开思自动对单] 已重新调度定时任务")
        
        # 立即执行一次
        task_manager.submit(ks_auto_bill_task)
        return True
    except Exception as e:
        logger.error(f"[开思自动对单] 重启失败: {e}")
        return False


def get_ks_auto_bill_status():
    """
    获取开思自动对单任务状态

    :return: 状态字典
    """
    status = get_ks_auto_bill_task_status()
    
    # 获取用户当前所在门店
    current_store = get_user_store()
    status['current_company'] = current_store
    status['current_company_name'] = get_company_name(current_store)
    
    # 补充定时任务状态
    try:
        job = task_manager._scheduler.get_job('ks_auto_bill_task')
        status['scheduled'] = True
        status['next_run_time'] = str(job.next_run_time) if job.next_run_time else None
    except Exception:
        status['scheduled'] = False
        status['next_run_time'] = None
    
    return status


@ks_auto_bill_bp.route('/api/ks_auto_bill/control', methods=['POST'])
@login_required
def control_ks_auto_bill():
    """
    控制开思自动对单任务

    请求参数:
        action: str - 操作类型 (start/stop/restart/status/run_once)

    返回:
        code: int - 0表示成功，1表示失败
        msg: str - 提示信息
        data: dict - 状态信息
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 1, 'msg': '请求参数不能为空'}), 400
        
        action = data.get('action')
        
        if action == 'start':
            success = True
            try:
                task_manager.schedule(
                    ks_auto_bill_task,
                    'interval',
                    'ks_auto_bill_task',
                    minutes=1,
                    replace_existing=True
                )
                msg = '定时任务已启动'
            except Exception as e:
                success = False
                msg = f'启动失败: {str(e)}'
            
            return jsonify({
                'code': 0 if success else 1,
                'msg': msg,
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
        
        elif action == 'run_once':
            success = start_ks_auto_bill_process()
            return jsonify({
                'code': 0 if success else 1,
                'msg': '已提交执行' if success else '执行失败',
                'status': get_ks_auto_bill_status()
            })
        
        elif action == 'status':
            return jsonify({
                'code': 0,
                'msg': '获取状态成功',
                'status': get_ks_auto_bill_status()
            })
        
        else:
            return jsonify({'code': 1, 'msg': '无效的操作类型'}), 400
            
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'操作失败: {str(e)}'}), 500
