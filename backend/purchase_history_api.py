# beihuo_system/purchase_history_api.py
from flask import Blueprint, jsonify, session
from functools import wraps
import threading
import pymysql

# 创建蓝图
purchase_history_bp = Blueprint('purchase_history', __name__, url_prefix='/api/purchase_history')


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


@purchase_history_bp.route('/trigger_task', methods=['POST'])
@login_required
def trigger_purchase_history_task():
    """手动触发采购历史同步任务"""
    try:
        from app.services.procurement_service.purchase_history_main import run

        def run_task():
            """在后台线程中运行任务"""
            try:
                print("=" * 60)
                print("采购历史同步任务开始")
                print("=" * 60)
                run(company='fsbbr', days=5)
                print("=" * 60)
                print("采购历史同步任务完成")
                print("=" * 60)
            except Exception as e:
                print(f"采购历史同步任务执行失败: {e}")
                import traceback
                traceback.print_exc()

        # 在后台线程中运行任务，避免阻塞请求
        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()

        return jsonify({
            'code': 0,
            'msg': '采购历史同步任务已启动，请在后台查看执行结果'
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'启动失败: {str(e)}'
        }), 500


@purchase_history_bp.route('/status', methods=['GET'])
@login_required
def get_purchase_history_status():
    """查询采购历史表的状态信息"""
    try:
        from app.utils.database_connection import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 查询新表 crmapp_procurement_history_detail 的总记录数和最新日期
        detail_table_info = {}
        try:
            # 查询总记录数
            cursor.execute("""
                SELECT COUNT(*) as total_count 
                FROM crmapp_procurement_history_detail
            """)
            detail_result = cursor.fetchone()
            detail_table_info['total_count'] = detail_result['total_count'] if detail_result else 0

            # 查询最新日期
            cursor.execute("""
                SELECT MAX(create_date) as latest_date 
                FROM crmapp_procurement_history_detail
            """)
            latest_result = cursor.fetchone()
            detail_table_info['latest_date'] = str(latest_result['latest_date']) if latest_result and latest_result['latest_date'] else None
        except Exception as e:
            detail_table_info['error'] = str(e)
            detail_table_info['total_count'] = 0
            detail_table_info['latest_date'] = None

        # 查询旧表 crmapp_procurement_history 的总记录数和月份列表
        history_table_info = {}
        try:
            # 查询总记录数
            cursor.execute("""
                SELECT COUNT(*) as total_count 
                FROM crmapp_procurement_history
            """)
            history_result = cursor.fetchone()
            history_table_info['total_count'] = history_result['total_count'] if history_result else 0

            # 查询月份列表（去重）
            cursor.execute("""
                SELECT DISTINCT year_month as month 
                FROM crmapp_procurement_history 
                WHERE year_month IS NOT NULL 
                ORDER BY month DESC
            """)
            month_rows = cursor.fetchall()
            history_table_info['months'] = [row['month'] for row in month_rows if row['month']]
        except Exception as e:
            history_table_info['error'] = str(e)
            history_table_info['total_count'] = 0
            history_table_info['months'] = []

        cursor.close()
        conn.close()

        return jsonify({
            'code': 0,
            'data': {
                'detail_table': detail_table_info,
                'history_table': history_table_info
            }
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'msg': f'查询状态失败: {str(e)}'
        }), 500


def register_purchase_history_routes(app):
    """注册采购历史蓝图到主应用"""
    app.register_blueprint(purchase_history_bp)
