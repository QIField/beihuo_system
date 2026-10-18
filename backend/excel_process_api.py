"""
Excel文件处理API接口
提供前端上传Excel文件并处理的功能
支持两列模式和三列模式处理
"""
import os
import tempfile
import pandas as pd
import importlib.util
from flask import request, jsonify, send_file, session, render_template
from datetime import datetime

def register_excel_process_routes(app):
    """注册Excel处理相关的路由"""

    @app.route('/excel_process')
    def excel_process_page():
        """Excel 处理独立页面（询比价模块同款风格）"""
        if 'logged_in' not in session:
            return render_template('login.html')
        return render_template('excel_process.html')

    @app.route('/api/excel/columns/check', methods=['POST'])
    def check_excel_columns():
        """
        检查Excel文件的列名是否符合要求
        返回文件支持的处理模式
        """
        try:
            if 'file' not in request.files:
                return jsonify({
                    'code': 1,
                    'msg': '没有上传文件'
                }), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({
                    'code': 1,
                    'msg': '文件名为空'
                }), 400
            
            # 保存临时文件
            temp_file_path = os.path.join(tempfile.gettempdir(), f"check_{file.filename}")
            file.save(temp_file_path)
            
            try:
                # 读取Excel文件检查列名，统一按字符串读取避免前导零丢失
                df = pd.read_excel(temp_file_path, dtype=str) if temp_file_path.endswith(('.xlsx', '.xls')) else pd.read_csv(temp_file_path, dtype=str)
                
                # 检查支持的列组合
                from app.utils.crm_product.crm_productAdd.excel_reader import identify_columns, identify_columns_extended
                
                result = {
                    'code': 0,
                    'msg': '列名检查完成',
                    'data': {
                        'total_rows': len(df),
                        'columns': list(df.columns),
                        'supported_modes': []
                    }
                }
                
                # 检查两列模式支持
                oe_col, brand_col = identify_columns(df)
                if oe_col and brand_col:
                    result['data']['supported_modes'].append({
                        'mode': 'two_column',
                        'description': '两列模式(oe + brand)',
                        'columns': {
                            'oe_column': oe_col,
                            'brand_column': brand_col
                        }
                    })
                
                # 检查三列模式支持
                oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                if oe_col and brand_col and brand_code_col:
                    result['data']['supported_modes'].append({
                        'mode': 'three_column',
                        'description': '三列模式(oe + brand + brand_code)',
                        'columns': {
                            'oe_column': oe_col,
                            'brand_column': brand_col,
                            'brand_code_column': brand_code_col
                        }
                    })
                
                if not result['data']['supported_modes']:
                    result['code'] = 1
                    result['msg'] = '文件列名不符合任何处理模式要求'
                
                return jsonify(result)
                    
            except Exception as e:
                return jsonify({
                    'code': 1,
                    'msg': f'检查失败: {str(e)}'
                }), 500
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                except Exception:
                    pass
                    
        except Exception as e:
            return jsonify({
                'code': 1,
                'msg': f'服务器错误: {str(e)}'
            }), 500
    
    @app.route('/api/excel/modes', methods=['GET'])
    def get_supported_modes():
        """
        获取支持的处理模式列表
        """
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': [
                {
                    'mode': 'two_column',
                    'name': '两列模式',
                    'description': '处理oe和brand两列数据',
                    'required_columns': ['oe', 'brand'],
                    'column_aliases': {
                        'oe': ['oe', 'OE', '物料条码', 'barcode'],
                        'brand': ['brand', '品牌', '品牌名称']
                    }
                },
                {
                    'mode': 'three_column',
                    'name': '三列模式',
                    'description': '处理oe、brand和brand_code三列数据',
                    'required_columns': ['oe', 'brand', 'brand_code'],
                    'column_aliases': {
                        'oe': ['oe', 'OE', '物料条码', 'barcode'],
                        'brand': ['brand', '品牌', '品牌名称'],
                        'brand_code': ['brand_code', '条码', '物料条码']
                    }
                }
            ]
        })

    # ========== 异步处理接口 ==========
    
    @app.route('/api/excel/async/product_archive', methods=['POST'])
    def async_product_archive():
        """
        新建档案-匹配检查接口（阶段一，不写CRM）
        检查每条 OE+品牌 在 CRM 中是否已存在，已存在的通过 view 接口取品牌编码，
        返回核对清单供页面表格展示；用户确认后调用 confirm 接口真正新建
        """
        try:
            # 检查文件
            if 'file' not in request.files:
                return jsonify({'code': 1, 'msg': '没有上传文件'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'code': 1, 'msg': '文件名为空'}), 400

            # 验证文件类型
            allowed_extensions = {'.xlsx', '.xls', '.csv'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({
                    'code': 1,
                    'msg': f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
                }), 400

            # 获取处理模式
            mode = request.form.get('mode', 'two_column')
            if mode not in ['two_column', 'three_column']:
                return jsonify({
                    'code': 1,
                    'msg': '无效的处理模式，支持: two_column, three_column'
                }), 400

            # 保存临时文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_filename = f"async_{timestamp}_{file.filename}"
            temp_file_path = os.path.join(tempfile.gettempdir(), temp_filename)
            file.save(temp_file_path)

            # 提交异步任务
            from app.core.async_task_store import submit_excel_task
            from app.utils.crm_product.crm_productAdd.api_wrappers import check_excel_items_wrapper

            # 获取用户当前门店/组织
            user_store = session.get('store', 'fsbbr')
            current_org = session.get('current_org', user_store)
            if not current_org or current_org in ('all', 'none', 'undefined', ''):
                company = user_store
            else:
                company = current_org

            task_id = submit_excel_task(check_excel_items_wrapper, temp_file_path, mode, company=company)

            return jsonify({
                'code': 0,
                'msg': '任务已提交',
                'data': {'task_id': task_id}
            })

        except Exception as e:
            import traceback
            print(f"[ERROR] 提交 CRM 匹配检查任务失败: {e}")
            traceback.print_exc()
            return jsonify({'code': 1, 'msg': f'提交失败: {str(e)}'}), 500

    @app.route('/api/excel/async/product_archive_confirm', methods=['POST'])
    def async_product_archive_confirm():
        """
        新建档案-确认处理接口（阶段二）
        待新建条目走新建流程（品牌号用实际更新品牌号）；已存在条目对比系统品牌编码
        与实际更新品牌号，不同才通过 view+updateView 更新。完成后生成结果文件并清理临时文件
        """
        try:
            data = request.get_json(silent=True) or {}
            check_task_id = str(data.get('check_task_id', '') or '')
            raw_items = data.get('items')
            if not check_task_id or not isinstance(raw_items, list) or not raw_items:
                return jsonify({'code': 1, 'msg': '缺少检查任务ID或待新建数据'}), 400

            from app.core.async_task_store import get_task_status, submit_excel_task
            from app.utils.crm_product.crm_productAdd.api_wrappers import create_confirmed_items_wrapper

            # 校验检查任务及临时文件仍然有效
            check_status = get_task_status(check_task_id)
            if not check_status:
                return jsonify({'code': 1, 'msg': '匹配检查任务不存在，请重新上传检查'}), 404

            check_data = check_status.get('result_data') or {}
            file_path = check_data.get('file_path')
            mode = check_data.get('mode')
            if mode not in ('two_column', 'three_column') or not file_path or not os.path.exists(file_path):
                return jsonify({'code': 1, 'msg': '检查任务已失效，请重新上传文件检查'}), 400

            # 清洗确认条目（status=existed 走品牌号对比更新，其余走新建）
            clean_items = []
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                oe = str(it.get('oe', '') or '').strip()
                brand = str(it.get('brand', '') or '').strip()
                if not oe or not brand:
                    continue
                clean_items.append({
                    'sheet_name': str(it.get('sheet_name', '') or ''),
                    'oe': oe,
                    'brand': brand,
                    'brand_code': str(it.get('brand_code', '') or '').strip(),
                    'status': str(it.get('status', '') or '').strip(),
                    'product_id': str(it.get('product_id', '') or '').strip()
                })
            if not clean_items:
                return jsonify({'code': 1, 'msg': '没有有效的处理数据'}), 400

            # 获取用户当前门店/组织
            user_store = session.get('store', 'fsbbr')
            current_org = session.get('current_org', user_store)
            if not current_org or current_org in ('all', 'none', 'undefined', ''):
                company = user_store
            else:
                company = current_org

            task_id = submit_excel_task(create_confirmed_items_wrapper, file_path, clean_items, mode, company=company)

            return jsonify({
                'code': 0,
                'msg': '任务已提交',
                'data': {'task_id': task_id}
            })

        except Exception as e:
            import traceback
            print(f"[ERROR] 提交 CRM 确认新建任务失败: {e}")
            traceback.print_exc()
            return jsonify({'code': 1, 'msg': f'提交失败: {str(e)}'}), 500

    @app.route('/api/excel/async/status/<task_id>', methods=['GET'])
    def get_async_task_status(task_id):
        """
        查询异步任务状态
        前端轮询调用此接口获取进度
        """
        from app.core.async_task_store import get_task_status
        
        status = get_task_status(task_id)
        if not status:
            return jsonify({'code': 1, 'msg': '任务不存在'}), 404
        
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': status
        })

    @app.route('/api/excel/async/download/<task_id>', methods=['GET'])
    def download_async_result(task_id):
        """
        下载异步任务结果文件
        任务完成后调用此接口下载结果
        """
        from app.core.async_task_store import get_task_status
        
        status = get_task_status(task_id)
        if not status:
            return jsonify({'code': 1, 'msg': '任务不存在'}), 404
        
        if status['status'] != 'completed':
            return jsonify({'code': 1, 'msg': '任务尚未完成'}), 400
        
        result_file = status.get('result_file')
        if not result_file or not os.path.exists(result_file):
            return jsonify({'code': 1, 'msg': '结果文件不存在'}), 404
        
        return send_file(
            result_file,
            as_attachment=True,
            download_name=os.path.basename(result_file)
        )

    @app.route('/api/excel/async/replace_number', methods=['POST'])
    def async_replace_number():
        """
        更新替换号-异步提交接口
        支持直接添加/对比添加两种模式
        """
        if 'file' not in request.files:
            return jsonify({'code': 1, 'msg': '没有上传文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'code': 1, 'msg': '文件名为空'}), 400

        allowed_extensions = {'.xlsx', '.xls', '.csv'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({
                'code': 1,
                'msg': f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
            }), 400

        mode = request.form.get('mode')
        if mode not in ['direct', 'compare']:
            return jsonify({
                'code': 1,
                'msg': '无效的处理模式，支持: direct, compare'
            }), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"replace_number_{timestamp}_{file.filename}"
        temp_file_path = os.path.join(tempfile.gettempdir(), temp_filename)
        file.save(temp_file_path)

        from app.core.async_task_store import submit_excel_task
        from app.services.replace_number_service.direct_processor import (
            process_direct_replace_number,
        )
        from app.utils.replace_number.excel_utils import read_replace_number_excel

        user_store = session.get('store', 'fsbbr')
        current_org = session.get('current_org', user_store)
        if not current_org or current_org in ('all', 'none', 'undefined', ''):
            company = user_store
        else:
            company = current_org

        if mode == 'direct':
            task_id = submit_excel_task(
                process_direct_replace_number,
                temp_file_path,
                company,
            )
            return jsonify({
                'code': 0,
                'msg': '任务已提交',
                'data': {'task_id': task_id, 'mode': mode}
            })
        else:
            df, rows = read_replace_number_excel(temp_file_path)
            oe_brand_list = [
                {'oe': r['oe'], 'brand': r['brand'], 'brand_number': r.get('brand_number', '')}
                for r in rows
            ]
            return jsonify({
                'code': 0,
                'msg': '已读取Excel数据',
                'data': {
                    'mode': mode,
                    'redirect_url': '/replace_number_edit',
                    'oe_brand_list': oe_brand_list
                }
            })


def process_excel_concurrent(file_path, process_type, mode='two_column'):
    """
    并发处理Excel文件的主要函数
    """
    try:
        # 读取Excel文件，统一按字符串读取避免前导零丢失
        df = pd.read_excel(file_path, sheet_name=None, dtype=str)
        all_results = {}
        
        for sheet_name, sheet_df in df.items():
            print(f"开始处理工作表: {sheet_name}")
            
            # 根据模式准备数据
            if mode == 'three_column':
                items = prepare_three_column_data(sheet_df, sheet_name)
            else:
                items = prepare_two_column_data(sheet_df, sheet_name)
            
            if not items:
                print(f"工作表 {sheet_name} 无有效数据")
                continue
            
            # 并发处理
            print(f"工作表 {sheet_name} 开始并发处理 {len(items)} 个项目...")
            session = get_global_session()
            batch_results = process_batch_items(session, items)
            
            # 整合结果
            for oe_number, result in batch_results.items():
                all_results[f"{sheet_name}_{oe_number}"] = result
            
            print(f"工作表 {sheet_name} 并发处理完成")
        
        # 保存结果
        result_file = save_results_to_excel(all_results, file_path)
        print(f"并发处理完成，结果文件保存至: {result_file}")
        
        return result_file
        
    except Exception as e:
        print(f"并发处理Excel文件时出错: {e}")
        return None
