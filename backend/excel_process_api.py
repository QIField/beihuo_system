"""
Excel文件处理API接口
提供前端上传Excel文件并处理的功能
支持两列模式和三列模式处理
"""
import os
import tempfile
import pandas as pd
import importlib.util
from flask import request, jsonify, send_file
from datetime import datetime

# 导入必要的函数
from app.utils.crm_product.crm新建产品 import (
    prepare_three_column_data,
    prepare_two_column_data, 
    get_global_session,
    process_batch_items,
    save_results_to_excel
)

def register_excel_process_routes(app):
    """注册Excel处理相关的路由"""
    
    @app.route('/api/excel/process', methods=['POST'])
    def process_excel_file():
        """
        处理前端上传的Excel文件
        支持两列模式和三列模式
        参数:
        - file: 上传的Excel文件
        - mode: 处理模式 ('two_column' 或 'three_column')
        """
        try:
            print("=== Excel处理API调用开始 ===")
            print(f"请求表单数据: {list(request.form.keys())}")
            print(f"请求文件字段: {list(request.files.keys())}")
            
            # 检查是否有文件上传
            if 'file' not in request.files:
                print("错误: 请求中没有'file'字段")
                return jsonify({
                    'code': 1,
                    'msg': '没有上传文件，请确保使用file字段上传'
                }), 400
            
            file = request.files['file']
            print(f"接收到文件: {file.filename}")
            
            if file.filename == '':
                print("错误: 文件名为空")
                return jsonify({
                    'code': 1,
                    'msg': '文件名为空'
                }), 400
            
            # 获取处理模式参数，默认为两列模式
            mode = request.form.get('mode', 'two_column')
            if mode not in ['two_column', 'three_column']:
                return jsonify({
                    'code': 1,
                    'msg': '无效的处理模式，支持: two_column, three_column'
                }), 400
            
            # 验证文件类型
            allowed_extensions = {'.xlsx', '.xls', '.csv'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({
                    'code': 1,
                    'msg': f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
                }), 400
            
            # 保存上传的文件到临时目录
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_filename = f"upload_{timestamp}_{file.filename}"
            temp_file_path = os.path.join(tempfile.gettempdir(), temp_filename)
            
            file.save(temp_file_path)
            print(f"文件已保存到临时路径: {temp_file_path}")
            print(f"处理模式: {mode}")
            
            try:
                # 根据模式选择不同的处理函数
                if mode == 'two_column':
                    from app.utils.crm_product import process_excel_two_column_mode
                    result_file_path = process_excel_two_column_mode(temp_file_path)
                else:  # three_column
                    from app.utils.crm_product import process_excel_three_column_mode
                    result_file_path = process_excel_three_column_mode(temp_file_path)
                
                # 检查结果文件是否成功创建
                if os.path.exists(result_file_path):
                    # 返回文件下载
                    return send_file(
                        result_file_path,
                        as_attachment=True,
                        download_name=f"处理结果_{mode}_{timestamp}{os.path.splitext(result_file_path)[1]}",
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                else:
                    return jsonify({
                        'code': 1,
                        'msg': f'{mode}模式处理失败：结果文件未生成'
                    }), 500
                    
            except Exception as e:
                print(f"{mode}模式处理过程中发生错误: {e}")
                return jsonify({
                    'code': 1,
                    'msg': f'{mode}模式处理失败: {str(e)}'
                }), 500
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        print(f"临时文件已清理: {temp_file_path}")
                except Exception as e:
                    print(f"清理临时文件时出错: {e}")
                    
        except Exception as e:
            print(f"API处理过程中发生错误: {e}")
            return jsonify({
                'code': 1,
                'msg': f'服务器内部错误: {str(e)}'
            }), 500
    
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
                # 读取Excel文件检查列名
                df = pd.read_excel(temp_file_path) if temp_file_path.endswith(('.xlsx', '.xls')) else pd.read_csv(temp_file_path)
                
                # 检查支持的列组合
                from app.utils.crm_product import identify_columns, identify_columns_extended
                
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
                try:
                    oe_col, brand_col = identify_columns(df)
                    result['data']['supported_modes'].append({
                        'mode': 'two_column',
                        'description': '两列模式(oe + brand)',
                        'columns': {
                            'oe_column': oe_col,
                            'brand_column': brand_col
                        }
                    })
                except ValueError:
                    pass  # 不支持两列模式
                
                # 检查三列模式支持
                try:
                    oe_col, brand_col, brand_code_col = identify_columns_extended(df)
                    if brand_code_col:  # 必须有brand_code列
                        result['data']['supported_modes'].append({
                            'mode': 'three_column',
                            'description': '三列模式(oe + brand + brand_code)',
                            'columns': {
                                'oe_column': oe_col,
                                'brand_column': brand_col,
                                'brand_code_column': brand_code_col
                            }
                        })
                except ValueError:
                    pass  # 不支持三列模式
                
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
    
    print("✅ Excel处理API接口已注册（支持两列和三列模式）")

def process_excel_concurrent(file_path, process_type, mode='two_column'):
    """
    并发处理Excel文件的主要函数
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path, sheet_name=None)
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
