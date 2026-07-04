import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment, NamedStyle, Font
from openpyxl.utils import get_column_letter
import chardet
import warnings
from decimal import Decimal, getcontext
import tempfile
import shutil
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

def read_file(file_path):
    """根据文件扩展名读取文件"""
    # 检查文件真实格式
    def detect_file_type(filepath):
        try:
            with open(filepath, 'rb') as f:
                header = f.read(8)
                # 检查是否为ZIP格式（Excel xlsx文件）
                if header[:2] == b'PK':
                    return 'xlsx'
                return None
        except:
            return None
    
    # 检查文件真实类型
    real_type = detect_file_type(file_path)
    
    if file_path.endswith('.xlsx') or real_type == 'xlsx':
        try:
            return pd.read_excel(file_path, dtype=str)
        except Exception as e:
            print(f"读取Excel文件失败: {str(e)}")
            return None
    elif file_path.endswith('.csv'):
        # 对于.csv文件，也要检查真实格式
        if real_type == 'xlsx':
            # 实际上是Excel文件
            try:
                return pd.read_excel(file_path, dtype=str)
            except Exception as e:
                print(f"读取Excel文件失败: {str(e)}")
                return None
        else:
            # 真正是CSV文件
            # 尝试多种编码方式读取CSV文件
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
            
            # 首先尝试自动检测编码
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read(10000)
                    encoding_result = chardet.detect(raw_data)
                    if encoding_result['confidence'] > 0.5:
                        detected_encoding = encoding_result['encoding']
                        if detected_encoding:
                            try:
                                return pd.read_csv(file_path, dtype=str, encoding=detected_encoding)
                            except:
                                pass
            except:
                pass
            
            # 如果自动检测失败，尝试预定义的编码
            for encoding in encodings:
                try:
                    return pd.read_csv(file_path, dtype=str, encoding=encoding)
                except UnicodeDecodeError:
                    continue
                except:
                    continue
            
            print("所有编码尝试均失败，无法读取此CSV文件")
            return None
    else:
        return None
def process_file(df, filename):
    """处理单个文件的数据"""
    required_cols = ["订单号", "订单日期", "订单数量", "订单金额", "实发金额"]
    
    actual_cols = {}
    for col in required_cols:
        found_col = None
        for df_col in df.columns:
            if col in df_col or df_col in col:
                found_col = df_col
                break
        if found_col is None:
            print(f"[失败] {filename} 缺少必要列: {col}")
            return False
        actual_cols[col] = found_col

    # 使用 Decimal 处理金额列
    for col in ["订单数量", "订单金额", "实发金额"]:
        df[actual_cols[col]] = df[actual_cols[col]].astype(str).apply(lambda x: Decimal(x) if x.strip() else Decimal(0))

    # 添加序号
    df.insert(0, "序号", range(1, len(df) + 1))

    new_rows = []

    # 按原始顺序获取唯一订单号
    seen = set()
    ordered_groups = []
    for oid in df[actual_cols["订单号"]]:
        if oid not in seen:
            ordered_groups.append(oid)
            seen.add(oid)

    merge_cols = ["订单日期", "交货日期", "客户名称", "经手人", "创建人", "关联职员", "订单类型", "订单 状态", "订单备注", "SAP订单号", "SAP发货单号"]
    
    for order_id in ordered_groups:
        group = df[df[actual_cols["订单号"]] == order_id].copy().reset_index(drop=True)
        
        # 计算统计值
        total_qty = sum(group[actual_cols['订单数量']])
        total_amt = sum(group[actual_cols['订单金额']])
        total_paid = sum(group[actual_cols['实发金额']])

        # 构建小计行
        subtotal_text = f"小计-订单号：{order_id}，订单数量：{int(total_qty)}，订单金额：{total_amt}，实发金额：{total_paid}"
        subtotal = {col: "" for col in df.columns}
        first_data_col = list(df.columns)[1]
        subtotal[first_data_col] = subtotal_text
        
        if "序号" in df.columns:
            subtotal["序号"] = "小计"
        
        new_rows.append(subtotal)

        # 添加明细行
        for local_idx, (_, row) in enumerate(group.iterrows(), start=1):
            row_dict = row.to_dict()
            row_dict["序号"] = local_idx
            new_rows.append(row_dict)

    # 总计行
    total_row = {col: "" for col in df.columns}
    total_row[actual_cols["订单数量"]] = sum(df[actual_cols['订单数量']])
    total_row[actual_cols["订单金额"]] = sum(df[actual_cols['订单金额']])
    total_row[actual_cols["实发金额"]] = sum(df[actual_cols['实发金额']])

    if "序号" in df.columns:
        total_row["序号"] = "总计"

    new_rows.append(total_row)

    output_df = pd.DataFrame(new_rows).fillna("")
    return output_df, actual_cols

def write_to_excel(output_df, output_file, actual_cols):
    """将处理后的数据写入Excel文件并添加样式"""
    try:
        wb = Workbook()
        ws = wb.active

        # 添加默认样式以避免警告
        if 'Normal' not in wb.named_styles:
            normal_style = NamedStyle(name='Normal')
            wb.add_named_style(normal_style)

        # 设置全局字体为等线
        font = Font(name='等线')
        ws.font = font

        # 标题
        ws.append(["佛山巴博瑞对账单"])
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(output_df.columns))
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        # 修改：增大标题字体到26号
        ws["A1"].font = Font(name='等线', size=26, bold=True)

        # 表头
        ws.append(list(output_df.columns))
        
        
        # 表头样式
        dark_green_fill = PatternFill("solid", fgColor="80A0A0")
        for cell in ws[2]:
            cell.fill = dark_green_fill
            cell.font = Font(name='等线', bold=True)

        # 找到订单号列的索引
        order_col_idx = None
        for idx, col_name in enumerate(output_df.columns):
            if "订单号" in col_name:
                order_col_idx = idx
                break
        
        if order_col_idx is None:
            print("[失败] 未找到订单号列")
            return

        # 找到序号列的索引
        seq_col_idx = None
        for idx, col_name in enumerate(output_df.columns):
            if "序号" in col_name:
                seq_col_idx = idx
                break
        
        if seq_col_idx is None:
            print("[失败] 未找到序号列")
            return

        # 数据行逐行写入
        data_rows = list(output_df.itertuples(index=False, name=None))
        
        # 先写入所有行
        for idx, row_data in enumerate(data_rows):
            current_row = idx + 3  # 当前行号（从第3行开始）

            
            # 检查是否是总计行，如果是则使用SUBTOTAL函数
            row_list = list(row_data)
            
            # 检查是否是总计行
            is_total_row = (isinstance(row_data[seq_col_idx], str) and row_data[seq_col_idx] == "总计")
            
            if is_total_row:
                # 对总计行使用SUBTOTAL函数，但需要排除小计行
                # 我们将使用SUBTOTAL(109, range)函数，它会自动忽略隐藏行
                # 但我们需要确保小计行被正确处理
                
                # 处理订单数量列
                if "订单数量" in actual_cols and actual_cols["订单数量"] in output_df.columns:
                    qty_col_idx = list(output_df.columns).index(actual_cols["订单数量"])
                    qty_col_letter = get_column_letter(qty_col_idx + 1)
                    # 使用SUBTOTAL函数，109表示SUM函数，忽略隐藏行
                    # 但这里需要更复杂的方法来排除小计行
                    # 我们先写入一个占位值，然后在最后设置公式
                    row_list[qty_col_idx] = "TOTAL_QTY_PLACEHOLDER"
                
                # 处理订单金额列
                if "订单金额" in actual_cols and actual_cols["订单金额"] in output_df.columns:
                    amount_col_idx = list(output_df.columns).index(actual_cols["订单金额"])
                    amount_col_letter = get_column_letter(amount_col_idx + 1)
                    row_list[amount_col_idx] = "TOTAL_AMT_PLACEHOLDER"
                
                # 处理实发金额列
                if "实发金额" in actual_cols and actual_cols["实发金额"] in output_df.columns:
                    paid_amount_col_idx = list(output_df.columns).index(actual_cols["实发金额"])
                    paid_amount_col_letter = get_column_letter(paid_amount_col_idx + 1)
                    row_list[paid_amount_col_idx] = "TOTAL_PAID_PLACEHOLDER"

            # 写入当前行
            ws.append(row_list)
            
            # 检查是否是小计行或总计行
            is_summary_row = (isinstance(row_data[seq_col_idx], str) and 
                             (row_data[seq_col_idx] == "小计" or row_data[seq_col_idx] == "总计"))
            
            if is_summary_row:
                # 为小计行或总计行设置特殊样式 - 先设置样式再处理合并
                for col_idx in range(len(output_df.columns)):
                    cell = ws.cell(current_row, col_idx+1)
                    cell.font = Font(name='等线', bold=True)
                    # 设置垂直居中和左对齐
                    cell.alignment = Alignment(vertical="center", horizontal="left")
                
                # 为小计和总计行设置不同的背景色
                if row_data[seq_col_idx] == "小计":
                    # 小计行使用灰色背景
                    for col_idx in range(len(output_df.columns)):
                        cell = ws.cell(current_row, col_idx+1)
                        cell.fill = PatternFill("solid", fgColor="D9D9D9")
                elif row_data[seq_col_idx] == "总计":
                    # 总计行使用绿色背景
                    for col_idx in range(len(output_df.columns)):
                        cell = ws.cell(current_row, col_idx+1)
                        cell.fill = PatternFill("solid", fgColor="80A0A0")

        # 查找订单状态和SAP订单号列的索引（使用 actual_cols 映射）
        order_status_col_idx = None
        sap_order_col_idx = None
        
        if "订单 状态" in actual_cols:
            order_status_col_idx = list(output_df.columns).index(actual_cols["订单 状态"])
        elif "订单状态" in actual_cols:
            order_status_col_idx = list(output_df.columns).index(actual_cols["订单状态"])
        
        if "SAP订单号" in actual_cols:
            sap_order_col_idx = list(output_df.columns).index(actual_cols["SAP订单号"])


        
        # 按订单分组进行合并操作
        # 定义需要合并的列（仅对明细行，不包括小计行）
        merge_cols = ["订单日期", "交货日期", "客户名称", "经手人", "创建人", "关联职员", "订单类型", "订单 状态", "订单备注", "SAP订单号", "SAP发货单号"]
        
        # 找到这些列的索引
        merge_col_indices = []
        
        # 查找所有需要合并的列索引
        for col_name in merge_cols:
            if col_name in actual_cols:
                col_idx = list(output_df.columns).index(actual_cols[col_name])
                merge_col_indices.append(col_idx)
            else:
                # 如果没有在 actual_cols 中找到，尝试直接匹配
                for idx, df_col in enumerate(output_df.columns):
                    if col_name in df_col or df_col in col_name:
                        merge_col_indices.append(idx)
                        break

        # 然后按订单分组进行合并操作
        current_order_id = None
        order_start_row = None
        order_end_row = None
        order_detail_count = 0  # 记录当前订单的明细行数量
        
        for idx, row_data in enumerate(data_rows):
            current_row = idx + 3  # 当前行号（从第3行开始）
            order_id = row_data[order_col_idx]
            
            # 检查是否是小计行或总计行
            is_summary_row = (isinstance(row_data[seq_col_idx], str) and 
                            (row_data[seq_col_idx] == "小计" or row_data[seq_col_idx] == "总计"))
            
            if not is_summary_row:  # 明细行
                if current_order_id != order_id:
                    # 新订单开始，先处理上一个订单的合并
                    if order_start_row is not None and order_end_row is not None and order_end_row > order_start_row and order_detail_count > 1:
                        
                        # 对上一个订单的指定列进行合并（从第一行开始）
                        for col_idx in merge_col_indices:
                            # 从第一行开始合并（即从order_start_row开始）
                            if order_end_row > order_start_row:  # 至少有两行明细才合并
                                ws.merge_cells(start_row=order_start_row, start_column=col_idx+1,
                                             end_row=order_end_row, end_column=col_idx+1)
                                
                                # 设置合并后的单元格样式
                                merged_cell = ws.cell(order_start_row, col_idx+1)
                                merged_cell.alignment = Alignment(vertical="center", horizontal="left")
                                merged_cell.font = Font(name='等线')
                    
                    # 开始新订单
                    current_order_id = order_id
                    order_start_row = current_row
                    order_end_row = current_row
                    order_detail_count = 1  # 第一行明细
                    
                        
                else:
                    # 同一订单的后续行
                    order_end_row = current_row
                    order_detail_count += 1
                    

            else:  # 小计行或总计行
                # 检查是否是小计行，如果是，则合并整个小计行
                if row_data[seq_col_idx] == "小计":
                    # 合并小计行的所有单元格，除了序号列
                    start_col = 2  # 从第二列开始合并（序号列之后）
                    end_col = len(output_df.columns)
                    if end_col >= start_col:
                        ws.merge_cells(start_row=current_row, start_column=start_col,
                                     end_row=current_row, end_column=end_col)
                
                # 检查是否是总计行，如果是，则合并特定范围的单元格
                if row_data[seq_col_idx] == "总计":
                    # 合并B-R列（第2列到第18列）
                    if len(output_df.columns) >= 18:
                        ws.merge_cells(start_row=current_row, start_column=2, end_row=current_row, end_column=min(18, len(output_df.columns)))
                    # 合并T-V列（第20列到第22列）
                    if len(output_df.columns) >= 22:
                        ws.merge_cells(start_row=current_row, start_column=20, end_row=current_row, end_column=min(22, len(output_df.columns)))
                    # 合并Y-Z列（第25列到第26列）
                    if len(output_df.columns) >= 26:
                        ws.merge_cells(start_row=current_row, start_column=25, end_row=current_row, end_column=min(26, len(output_df.columns)))
                
                # 处理当前订单的合并（如果有的话）
                if order_start_row is not None and order_end_row is not None and order_end_row > order_start_row and order_detail_count > 1:
                    
                    # 对当前订单的指定列进行合并（从第一行开始）
                    for col_idx in merge_col_indices:
                        # 从第一行开始合并（即从order_start_row开始）
                        if order_end_row > order_start_row:  # 至少有两行明细才合并
                            ws.merge_cells(start_row=order_start_row, start_column=col_idx+1,
                                         end_row=order_end_row, end_column=col_idx+1)
                            
                            # 设置合并后的单元格样式
                            merged_cell = ws.cell(order_start_row, col_idx+1)
                            merged_cell.alignment = Alignment(vertical="center", horizontal="left")
                            merged_cell.font = Font(name='等线')
                
                # 重置订单跟踪变量
                current_order_id = None
                order_start_row = None
                order_end_row = None
                order_detail_count = 0

        
        # 处理最后一个订单的合并
        if order_start_row is not None and order_end_row is not None and order_end_row > order_start_row and order_detail_count > 1:
            for col_idx in merge_col_indices:
                # 从第一行开始合并（即从order_start_row开始）
                if order_end_row > order_start_row:  # 至少有两行明细才合并
                    ws.merge_cells(start_row=order_start_row, start_column=col_idx+1,
                                 end_row=order_end_row, end_column=col_idx+1)
                    
                    # 设置合并后的单元格样式
                    merged_cell = ws.cell(order_start_row, col_idx+1)
                    merged_cell.alignment = Alignment(vertical="center", horizontal="left")
                    merged_cell.font = Font(name='等线')

        # 应用等线字体到所有单元格
        for row in ws.iter_rows():
            for cell in row:
                if cell.font.name != '等线':  # 不覆盖已设置的特殊字体
                    cell.font = Font(name='等线')
                    # 修改：为所有单元格设置垂直居中和左对齐
                    cell.alignment = Alignment(vertical="center", horizontal="left")

        # 为整个表格添加边框
        from openpyxl.styles import Border, Side
        
        # 定义边框样式
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 为所有单元格添加边框
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.border = thin_border

        # 冻结前两行（表头固定，不能被筛选）
        ws.freeze_panes = 'A3'
        
        # 创建分组结构
        subtotal_positions = []
        for row_num in range(3, ws.max_row + 1):
            cell_value = ws.cell(row=row_num, column=order_col_idx+1).value
            if isinstance(cell_value, str) and cell_value.startswith("小计-"):
                subtotal_positions.append(row_num)
        
        for i, subtotal_row in enumerate(subtotal_positions):
            if i < len(subtotal_positions) - 1:
                next_subtotal_row = subtotal_positions[i+1]
                outline_level = 1
                for row_num in range(subtotal_row + 1, next_subtotal_row):
                    ws.row_dimensions[row_num].outline = outline_level
            else:
                outline_level = 1
                for row_num in range(subtotal_row + 1, ws.max_row + 1):
                    ws.row_dimensions[row_num].outline = outline_level
        ws.sheet_properties.outlinePr.summaryBelow = False

        # 最后，设置总计行的SUBTOTAL函数，确保它能够响应筛选
        # 遍历所有行找到总计行并设置公式
        for row_num in range(3, ws.max_row + 1):
            seq_cell_value = ws.cell(row=row_num, column=seq_col_idx+1).value
            if seq_cell_value == "总计":
                # 找到总计行，设置SUBTOTAL公式
                if "订单数量" in actual_cols:
                    qty_col_idx = list(output_df.columns).index(actual_cols["订单数量"])
                    qty_col_letter = get_column_letter(qty_col_idx + 1)
                    # 使用SUBTOTAL函数，109表示SUM函数，忽略隐藏行
                    # 但为了排除小计行，我们需要使用更复杂的方法
                    ws.cell(row=row_num, column=qty_col_idx+1, value=f'=SUBTOTAL(109,{qty_col_letter}3:{qty_col_letter}{row_num-1})')
                    ws.cell(row=row_num, column=qty_col_idx+1).number_format = '0.00'

                if "订单金额" in actual_cols:
                    amount_col_idx = list(output_df.columns).index(actual_cols["订单金额"])
                    amount_col_letter = get_column_letter(amount_col_idx + 1)
                    ws.cell(row=row_num, column=amount_col_idx+1, value=f'=SUBTOTAL(109,{amount_col_letter}3:{amount_col_letter}{row_num-1})')
                    ws.cell(row=row_num, column=amount_col_idx+1).number_format = '0.00'

                if "实发金额" in actual_cols:
                    paid_amount_col_idx = list(output_df.columns).index(actual_cols["实发金额"])
                    paid_amount_col_letter = get_column_letter(paid_amount_col_idx + 1)
                    ws.cell(row=row_num, column=paid_amount_col_idx+1, value=f'=SUBTOTAL(109,{paid_amount_col_letter}3:{paid_amount_col_letter}{row_num-1})')
                    ws.cell(row=row_num, column=paid_amount_col_idx+1).number_format = '0.00'
                    
                # 在序号列确认写入"总计"
                ws.cell(row=row_num, column=seq_col_idx+1, value="总计")
                break

        wb.save(output_file)
    except Exception as e:
        print(f"写入Excel文件时出错: {str(e)}")
        raise

def process_files(file_paths):
    """处理指定的文件列表，返回处理后的文件路径列表"""
    results = []
    temp_dir = tempfile.mkdtemp()  # 创建临时目录存放处理后的文件
    
    for file_path in file_paths:
        try:
            df = read_file(file_path)
            if df is None:
                print(f"[失败] 无法读取文件: {file_path}")
                continue

            # 检查必要列
            required_cols = ["订单号", "订单日期", "订单数量", "订单金额", "实发金额"]
            missing_cols = []
            for col in required_cols:
                found = False
                for df_col in df.columns:
                    if col in df_col or df_col in col:
                        found = True
                        break
                if not found:
                    missing_cols.append(col)

            if missing_cols:
                print(f"[失败] {file_path} 缺少必要列: {missing_cols}")
                continue

            # 处理数据
            result, actual_cols = process_file(df, os.path.basename(file_path))

            if result is not False:
                # 生成输出文件名，使用原文件名+已处理标识，并确保扩展名为.xlsx
                original_filename = os.path.splitext(os.path.basename(file_path))[0]
                output_file = os.path.join(temp_dir, f"{original_filename}已处理.xlsx")
                
                # 检查文件是否已存在，如果存在则添加数字后缀
                counter = 1
                base_output_file = output_file
                while os.path.exists(output_file):
                    name_part = os.path.splitext(base_output_file)[0]
                    ext_part = os.path.splitext(base_output_file)[1]
                    output_file = f"{name_part}_{counter}{ext_part}"
                    counter += 1
                    
                write_to_excel(result, output_file, actual_cols)
                results.append(output_file)
                print(f"[成功] 处理完成: {file_path} -> {output_file}")
            else:
                print(f"[失败] 处理失败: {file_path}")

        except Exception as e:
            print(f"[失败] 处理文件时出错 {file_path}: {str(e)}")
            continue

    return results
def main(file_paths=None):
    """主函数，接受文件路径列表作为参数进行处理"""
    if file_paths is None:
        print("[失败] 未提供文件路径列表")
        return []
    
    print("=" * 80)
    print("CRM对账单处理工具")
    print("=" * 80)
    print(f"处理文件数量: {len(file_paths)}")
    print("-" * 80)
    print(f"{'文件路径':<50} {'状态':<25}")
    print("-" * 80)

    return process_files(file_paths)

if __name__ == "__main__":
    main()