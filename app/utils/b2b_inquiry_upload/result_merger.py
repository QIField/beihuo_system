"""
结果合并模块
合并B2B上传结果和新建产品结果
"""


def merge_results(df, skipped_items, b2b_results, create_results):
    """
    合并所有结果，生成处理结果列
    
    逻辑：
    1. 上传成功 → 显示上传成功（update/insert）
    2. 上传失败（产品不存在）→ 尝试新建产品，显示上传失败 + 新建结果
    3. 上传失败（其他原因）→ 只显示上传失败
    4. 跳过 → 显示跳过原因
    
    Args:
        df: 原始DataFrame
        skipped_items: 跳过的数据项列表
        b2b_results: B2B上传结果 {oe: {status, msg, operation, mapped_brand}}
        create_results: 新建产品结果 {oe: result_string}
    
    Returns:
        list: 合并后的结果列表，每项包含原始数据和处理结果
    """
    merged = []
    
    # 处理所有行
    for idx, row in df.iterrows():
        oe = str(row.get('oe', '')).strip()
        brand = str(row.get('brand', '')).strip()
        
        result_item = {
            'index': idx,
            'oe': oe,
            'brand': brand,
            'supplier': str(row.get('supplier', '')).strip(),
            'warehouse': str(row.get('warehouse', '')).strip(),
            'price': row.get('price', ''),
            'stock_quantity': row.get('stock_quantity', ''),
            'expire_time': row.get('expire_time', ''),
            'remark': str(row.get('remark', '')).strip(),
            '处理结果': ''
        }
        
        # 1. 检查是否跳过
        skipped_item = next((s for s in skipped_items if s['index'] == idx), None)
        if skipped_item:
            result_item['处理结果'] = f"跳过 - {skipped_item.get('skip_reason', '')}"
            merged.append(result_item)
            continue
        
        # 2. 获取B2B结果
        b2b_res = b2b_results.get(oe, {})
        
        if b2b_res.get('status') == 'success':
            # 上传成功 - 直接显示成功
            operation = b2b_res.get('operation', 'unknown')
            mapped_brand = b2b_res.get('mapped_brand')
            
            if mapped_brand:
                result_item['处理结果'] = f"上传{operation}成功（使用{mapped_brand}）"
            else:
                result_item['处理结果'] = f"上传{operation}成功"
            
            merged.append(result_item)
            continue
        
        if b2b_res.get('status') == 'error':
            # 上传失败 - 检查是否有新建结果
            msg = b2b_res.get('msg', '未知错误')
            mapped_brand = b2b_res.get('mapped_brand')
            create_res = create_results.get(oe, '')
            
            if create_res:
                # 有新建结果 - 合并显示
                # 提取B2B错误的核心信息（去掉重复的品牌和OE号）
                error_summary = msg
                if "物料所属品牌" in msg and "OE号" in msg:
                    # 简化错误信息
                    error_summary = "产品不存在"
                
                if mapped_brand:
                    result_item['处理结果'] = f"上传失败（{error_summary}，使用{mapped_brand}），{create_res}"
                else:
                    result_item['处理结果'] = f"上传失败（{error_summary}），{create_res}"
            else:
                # 没有新建结果 - 只显示上传失败
                if mapped_brand:
                    result_item['处理结果'] = f"上传失败 - {msg}（使用{mapped_brand}）"
                else:
                    result_item['处理结果'] = f"上传失败 - {msg}"
            
            merged.append(result_item)
            continue
        
        # 未知状态
        result_item['处理结果'] = "未知状态"
        merged.append(result_item)
    
    return merged


def generate_result_message(b2b_results, create_results, skipped_count):
    """
    生成结果汇总消息
    """
    # B2B统计
    b2b_success = sum(1 for r in b2b_results.values() if r.get('status') == 'success')
    b2b_error = sum(1 for r in b2b_results.values() if r.get('status') == 'error')
    
    # 新建统计
    created = sum(1 for r in create_results.values() if '成功' in r and '失败' not in r)
    exists = sum(1 for r in create_results.values() if '已存在' in r)
    create_failed = sum(1 for r in create_results.values() if '失败' in r)
    
    return {
        'upload_success': b2b_success,
        'upload_failed': b2b_error,
        'created': created,
        'exists': exists,
        'create_failed': create_failed,
        'skipped': skipped_count
    }
