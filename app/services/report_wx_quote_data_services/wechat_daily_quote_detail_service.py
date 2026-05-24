# -*- coding:utf-8 -*-
# @Time    : 2026/5/13 17:25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wechat_daily_quote_detail_service.py
# @Software: PyCharm

import re
import traceback
from datetime import datetime, timedelta
from app.utils.orm.session import orm_session
from app.models.orm_models.weixin_decoding_result import WeixinDecodingResult
from app.models.orm_models.wechat_daily_quote_detail import WechatDailyQuoteDetail
from app.models.orm_models.crmapp_sales_history_detail import CrmappSalesHistoryDetail

def convert_to_database_format(records):
    """
    将 weixin_decoding_result 字典列表转换为 wechat_daily_quote_detail 表格式
    
    Args:
        records: weixin_decoding_result 字典列表
        
    Returns:
        适合插入 wechat_daily_quote_detail 表的数据列表
    """
    database_data = []
    
    for record in records:
        # 获取源数据的 id 和 result
        source_id = record.get('id')
        
        # ==========================================
        # 第一步：解析 result 字段，获取所有报价行
        # ==========================================
        result_text = record.get('result', '')
        result_array = parse_lines(result_text) if result_text else []
        
        # ==========================================
        # 第二步：判断是否需要跳过第一行
        # 通常第一行是 VIN 码或查询条件，不是报价信息
        # ==========================================
        should_skip_first = True
        content = record.get('content', '')
        if content:
            content_lines = parse_lines(content)
            if content_lines:
                first_content_line = content_lines[0].strip()
                
                # 情况1：result 第一行与 content 第一行相同 → 跳过（通常是 VIN 码）
                if len(result_array) > 0 and result_array[0].strip() == first_content_line:
                    should_skip_first = True
                
                # 情况2：content 第一行是纯数字/字母组合 → 不跳过（可能是 OE 码查询）
                elif re.match(r'^[A-Za-z0-9]+$', first_content_line):
                    should_skip_first = False
        
        # 执行跳过操作
        if should_skip_first and len(result_array) > 0:
            result_array = result_array[1:]
        
        # ==========================================
        # 第三步：逐行解析报价信息
        # 每行格式示例："1、92A启停电池 (61215A14945) = 菲尔(蓄电池 AGM L5(92AH)) 800 / 菲尔(蓄电池 AGM L5 92AH) 800 / 盖茨 800 / 原厂国内4s件(92A蓄电池) 1400 / 原厂国内4s件(进口92A蓄电池) 1450"
        # ==========================================
        for result_item in result_array:
            # 初始化字段
            quote_number = None      # 报价序号
            part_name = ''           # 配件名称
            oe_code = ''             # OE 码
            brand_price = ''         # 品牌价格（完整报价信息）
            original_quote = result_item  # 原始报价（完整一行）
            
            # ---------- 3.0 解析序号 ----------
            # 正则说明：匹配开头的数字+顿号/逗号/点，如 "1、" "2," "3."
            quote_num_match = re.match(r'^(\d+)[、.,]\s*', result_item)
            if quote_num_match:
                quote_number = int(quote_num_match.group(1))
            
            # ---------- 3.1 解析配件名称 ----------
            # 正则说明：匹配数字开头+顿号/逗号/点，然后提取到括号或等号之前的内容
            part_name_match = re.match(r'^(?:\d+[、.,])?\s*(.*?)(?=\s*\(|=|$)', result_item)
            if part_name_match:
                part_name = part_name_match.group(1).strip()
            
            # ---------- 3.2 解析 OE 码 ----------
            # 正则说明：匹配括号中的数字字母组合，如 (61215A14945)
            oe_match = re.search(r'\(([A-Za-z0-9]+)\)', result_item)
            oe_code = oe_match.group(1) if oe_match else ''
            # 特殊处理：OE 码为 "0" 时，当作空处理
            if oe_code == '0':
                oe_code = ''
            
            # ---------- 3.3 解析报价信息 ----------
            # 正则说明：匹配等号之后的所有内容
            quote_match = re.search(r'=\s*(.*)$', result_item)
            if quote_match:
                brand_price = quote_match.group(1).strip()
            
            # ---------- 3.4 判断是否缺货 ----------
            # 正则说明：匹配 "=0" 或 "= 0" 格式，表示缺货
            is_out_of_stock = bool(re.search(r'=\s*0', result_item))
            
            # ==========================================
            # 第四步：构建数据库记录
            # ==========================================
            db_item = {
                'weixin_decoding_result_id': source_id,          # 微信解码结果表ID
                'quote_number': quote_number,                    # 报价序号
                'create_date': record.get('creation_date'),      # 创建日期（字符串格式）
                'group_name': record.get('groupname'),           # 群名称
                'user_name': record.get('nickname'),             # 用户昵称
                'inquiry': content,                              # 询价内容
                'part_name': part_name,                          # 配件名称
                'oe_code': oe_code,                              # OE 码
                'brand_price': brand_price,                      # 品牌价格（完整报价信息）
                'original_quote': original_quote,                # 原始报价（完整一行）
                'is_out_of_stock': is_out_of_stock,  # 缺货状态
                # 成交相关字段暂时为空，后续可能需要根据其他数据填充
                'deal_customer_id': None,
                'deal_customer': None,
                'deal_brand': None,
                'deal_amount': None,
                'deal_status': 0                                 # 成交状态：0-未知，1-成交，2-未成交
            }
            
            database_data.append(db_item)
    
    return database_data


def parse_lines(text):
    """
    按行分割文本，过滤空行
    
    Args:
        text: 文本内容
        
    Returns:
        行列表
    """
    items = []
    
    if not text:
        return items
    
    # 按行分割
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        items.append(line)
    
    return items


def get_weixin_decoding_result(start_date=None, end_date=None):
    """
    从 weixin_decoding_result 表获取数据并转换为 wechat_daily_quote_detail 格式
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        
    Returns:
        转换后的数据列表
    """
    records = []
    
    with orm_session() as session:
        # 构建查询
        query = session.query(WeixinDecodingResult).filter(
            WeixinDecodingResult.result.isnot(None),
            WeixinDecodingResult.result != ''
        )
        
        # 添加时间范围筛选 - 直接比较字符串
        if start_date:
            # 例如 start_date='2026-01-05' → 匹配 >= '2026-01-05 00:00:00'
            query = query.filter(WeixinDecodingResult.creation_date >= f'{start_date} 00:00:00')
        if end_date:
            # 例如 end_date='2026-01-05' → 匹配 <= '2026-01-05 23:59:59'
            query = query.filter(WeixinDecodingResult.creation_date <= f'{end_date} 23:59:59')
        
        # 按创建时间倒序
        query = query.order_by(WeixinDecodingResult.creation_date.desc())
        
        # 获取数据
        items = query.all()
        
        # 转换为字典
        for item in items:
            records.append(item.to_dict())
    
    # 转换为数据库格式
    return records


def batch_save_to_database(data_list):
    """
    批量保存数据到 wechat_daily_quote_detail 表
    以 quote_number 和 weixin_decoding_result_id 为联合索引进行插入更新
    
    Args:
        data_list: 转换后的数据列表
        
    Returns:
        保存的记录数
    """
    if not data_list:
        return 0
    
    with orm_session() as session:
        result = WechatDailyQuoteDetail.bulk_upsert(session, data_list)
        session.commit()
        return result


def fetch_data_paged(start_date=None, end_date=None, groupname=None, nickname=None, deal_status=None, page=1, limit=20):
    """
    从数据库获取微信日报报价详情数据（使用 ORM，带分页信息）
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，可选
        end_date: 结束日期 (YYYY-MM-DD)，可选
        groupname: 群名称，可选
        nickname: 业务员，可选
        deal_status: 成交状态，可选 (0-未知, 1-成交, 2-未成交)
        page: 页码，从1开始
        limit: 每页条数
        
    Returns:
        包含分页信息的字典 {'result': [...], 'total': ..., 'page': ..., 'limit': ...}
    """
    total = 0
    
    with orm_session() as session:
        # 先获取 distinct 的 weixin_decoding_result_id，用于分页
        id_query = session.query(WechatDailyQuoteDetail.weixin_decoding_result_id).distinct()
        
        # 添加筛选条件
        if start_date:
            # 例如 start_date='2026-01-05' → 匹配 >= '2026-01-05 00:00:00'
            id_query = id_query.filter(WechatDailyQuoteDetail.create_date >= f'{start_date} 00:00:00')
        if end_date:
            # 例如 end_date='2026-01-05' → 匹配 <= '2026-01-05 23:59:59'
            id_query = id_query.filter(WechatDailyQuoteDetail.create_date <= f'{end_date} 23:59:59')
        if groupname:
            id_query = id_query.filter(WechatDailyQuoteDetail.group_name == groupname)
        if nickname:
            id_query = id_query.filter(WechatDailyQuoteDetail.user_name.like(f'%{nickname}%'))
        if deal_status is not None:
            id_query = id_query.filter(WechatDailyQuoteDetail.deal_status == deal_status)
        
        # 排序
        id_query = id_query.order_by(WechatDailyQuoteDetail.weixin_decoding_result_id.desc())
        
        # 获取总数
        total = id_query.count()
        
        # 分页获取 id 列表
        id_list = []
        if page and limit:
            offset = (page - 1) * limit
            id_list = [row[0] for row in id_query.offset(offset).limit(limit).all()]
        else:
            id_list = [row[0] for row in id_query.all()]
        
        # 如果没有 id，直接返回
        if not id_list:
            items = []
        else:
            # 根据 id 列表获取所有详情数据
            query = session.query(WechatDailyQuoteDetail).filter(
                WechatDailyQuoteDetail.weixin_decoding_result_id.in_(id_list)
            )
            # 添加deal_status筛选条件
            if deal_status is not None:
                query = query.filter(WechatDailyQuoteDetail.deal_status == deal_status)
            # 排序：weixin_decoding_result_id 降序，quote_number 升序
            query = query.order_by(
                WechatDailyQuoteDetail.weixin_decoding_result_id.desc(),
                WechatDailyQuoteDetail.quote_number.asc()
            )
            items = query.all()
        
        # 转换为字典并直接分组
        grouped_data = {}
        for item in items:
            record = item.to_dict()
            result_id = record['weixin_decoding_result_id']
            
            if result_id not in grouped_data:
                grouped_data[result_id] = {
                    'content': record.get('inquiry', ''),
                    'create_time': record.get('create_date', ''),
                    'groupname': record.get('group_name', ''),
                    'id': str(result_id) if result_id else '',
                    'nickname': record.get('user_name', ''),
                    'oe_code_list': [],
                    'result': [],
                    'result_details': []
                }
            
            # 添加数据
            if record.get('oe_code'):
                grouped_data[result_id]['oe_code_list'].append(record['oe_code'])
            
            if record.get('original_quote'):
                grouped_data[result_id]['result'].append(record['original_quote'])
            
            # 构建 result_details
            detail = {
                'quote_number': record.get('quote_number'),
                'is_out_of_stock': record.get('is_out_of_stock', False),
                'item': record.get('original_quote', ''),
                'oe_code': record.get('oe_code', ''),
                'part_name': record.get('part_name', ''),
                'quote_info': record.get('brand_price', ''),
                'deal_customer': record.get('deal_customer'),
                'deal_brand': record.get('deal_brand'),
                'deal_amount': record.get('deal_amount'),
                'deal_status': record.get('deal_status', 0)
            }
            grouped_data[result_id]['result_details'].append(detail)
    
    # 转换为列表
    result_list = list(grouped_data.values())
    
    # 返回带分页信息的数据
    return {
        'result': result_list,
        'total': total,
        'page': page or 1,
        'limit': limit or 20
    }






def get_customer_list(oe_code=None, create_date=None):
    """
    根据 OE 号和创建日期获取客户列表
    
    Args:
        oe_code: OE 码
        create_date: 创建日期
        
    Returns:
        客户列表
    """
    try:
        with orm_session() as session:
            # 构建查询条件
            query = session.query(
                CrmappSalesHistoryDetail.fullname,
                CrmappSalesHistoryDetail.total_price,
                CrmappSalesHistoryDetail.brand_name
            ).filter(
                CrmappSalesHistoryDetail.fullname.isnot(None),
                CrmappSalesHistoryDetail.fullname != ''
            )
            
            # 添加 OE 码条件
            
            # 去掉OE码前面的字母，只保留数字部分
            # 例如: "A12345" → "12345"
                
            oe_code_clean = re.sub(r'^[a-zA-Z]+', '', oe_code)  # pyright: ignore[reportArgumentType, reportCallIssue]
            if oe_code_clean:
                query = query.filter(
                    CrmappSalesHistoryDetail.number == oe_code_clean
                )
            
            # 添加日期条件
            try:
                # 提取日期部分（只取 yyyy-mm-dd）
                # 支持格式：2026-04-09 18:19:08 或 2026-04-09
                date_part = None
                if ' ' in create_date:  # pyright: ignore[reportOperatorIssue]
                    date_part = create_date.split(' ')[0]  # pyright: ignore[reportOptionalMemberAccess]
                elif 'T' in create_date:  # pyright: ignore[reportOperatorIssue]
                    date_part = create_date.split('T')[0]  # pyright: ignore[reportOptionalMemberAccess]
                else:
                    date_part = create_date
                
                # 确保日期格式正确（只保留前10个字符）
                if date_part and len(date_part) >= 10:
                    date_part = date_part[:10]
                
                if date_part:
                    # 例如 date_part='2026-01-05' → 匹配 >= '2026-01-05 00:00:00' and <= '2026-01-05 23:59:59'
                    query = query.filter(
                        CrmappSalesHistoryDetail.create_date >= f'{date_part} 00:00:00',
                        CrmappSalesHistoryDetail.create_date <= f'{date_part} 23:59:59'
                    )
            except Exception as e:
                print(f"处理日期条件时出错: {str(e)}")
                pass
            
            # 执行查询
            results = query.all()
            
            # 转换为需要的格式
            customer_list = []
            for i, row in enumerate(results, 1):
                if row[0]:
                    customer_list.append({
                        'id': i,
                        'fullname': row[0],
                        'total_price': float(row[1]) if row[1] is not None else None,
                        'brand_name': row[2]
                    })
            
            return customer_list
            
    except Exception as e:
        print(f"获取客户列表失败: {str(e)}")
        traceback.print_exc()
        return []


def update_deal_info(quote_number, weixin_decoding_result_id, deal_status=None, deal_customer=None, deal_brand=None, deal_amount=None):
    """
    更新成交信息
    
    Args:
        quote_number: 报价序号
        weixin_decoding_result_id: 微信解码结果表ID
        deal_status: 成交状态：0-未知，1-成交，2-未成交
        deal_customer: 成交客户
        deal_brand: 成交品牌
        deal_amount: 成交金额
        
    Returns:
        是否成功
    """
    try:
        with orm_session() as session:
            # 根据quote_number和weixin_decoding_result_id查找记录
            record = session.query(WechatDailyQuoteDetail).filter_by(
                quote_number=quote_number,
                weixin_decoding_result_id=weixin_decoding_result_id
            ).first()
            if not record:
                print(f"未找到quote_number为 {quote_number}, weixin_decoding_result_id为 {weixin_decoding_result_id} 的记录")
                return False
            
            # 更新字段
            if deal_status is not None:
                record.deal_status = deal_status
            if deal_customer is not None:
                record.deal_customer = deal_customer
            if deal_brand is not None:
                record.deal_brand = deal_brand
            if deal_amount is not None:
                record.deal_amount = deal_amount
            
            session.commit()
            return True
            
    except Exception as e:
        print(f"更新成交信息失败: {str(e)}")
        traceback.print_exc()
        return False

# 数据批量回填成交信息 - 处理单个日期
def process_single_day(day_date):
    """
    处理单个日期的成交信息回填
    
    Args:
        day_date: 日期字符串，格式 'YYYY-MM-DD'
        
    Returns:
        dict: 当天的处理统计信息
    """
    # 当天的统计信息
    day_stats = {
        'total': 0,           # 总处理记录数
        'updated': 0,         # 成功更新记录数（成交）
        'not_found': 0,       # 未找到匹配记录数
        'multi_found': 0,     # 匹配到多条记录数
        'no_oe_code': 0,      # 没有 OE 码的记录数
        'failed': 0           # 失败记录数
    }
    
    try:
        print(f"处理日期：{day_date}")
        
        with orm_session() as session:
            # 查询当天 deal_status=0 的记录
            records = session.query(WechatDailyQuoteDetail).filter(
                WechatDailyQuoteDetail.create_date >= f'{day_date} 00:00:00',
                WechatDailyQuoteDetail.create_date <= f'{day_date} 23:59:59',
                WechatDailyQuoteDetail.deal_status == 0
            ).all()
            
            if not records:
                print(f"  日期 {day_date} 没有需要处理的记录")
                return day_stats
            
            day_stats['total'] = len(records)
            print(f"  找到 {len(records)} 条记录")
            
            # 逐个处理记录
            for record in records:
                try:
                    # 如果是缺货，直接标记为未成交
                    if record.is_out_of_stock:  # pyright: ignore[reportGeneralTypeIssues]
                        record.deal_status = 2  # pyright: ignore[reportAttributeAccessIssue]
                        day_stats['not_found'] += 1
                        continue
                    
                    # 检查 OE 码
                    if not record.oe_code:  # pyright: ignore[reportGeneralTypeIssues]
                        day_stats['no_oe_code'] += 1
                        continue
                    
                    # 清理 OE 码（去掉前面的字母）
                    oe_code_clean = re.sub(r'^[a-zA-Z]+', '', record.oe_code)  # pyright: ignore[reportCallIssue, reportArgumentType]
                    if not oe_code_clean:
                        day_stats['no_oe_code'] += 1
                        continue
                    
                    # 按日期和 OE 一起查询
                    sales_records = session.query(CrmappSalesHistoryDetail).filter(
                        CrmappSalesHistoryDetail.number == oe_code_clean,
                        CrmappSalesHistoryDetail.create_date >= f'{day_date} 00:00:00',
                        CrmappSalesHistoryDetail.create_date <= f'{day_date} 23:59:59',
                        CrmappSalesHistoryDetail.fullname.isnot(None),
                        CrmappSalesHistoryDetail.fullname != ''
                    ).all()
                    
                    # 只有找到的数据条数为 1 时才回填
                    if len(sales_records) == 1:
                        sales_record = sales_records[0]
                        # 找到匹配，标记为成交
                        record.deal_status = 1  # pyright: ignore[reportAttributeAccessIssue]
                        record.deal_customer = sales_record.fullname
                        record.deal_brand = sales_record.brand_name
                        record.deal_amount = sales_record.total_price
                        day_stats['updated'] += 1
                    elif len(sales_records) == 0:
                        # 没找到匹配，标记为未成交
                        record.deal_status = 2  # pyright: ignore[reportAttributeAccessIssue]
                        day_stats['not_found'] += 1
                    else:
                        # 找到多条匹配，保持状态不变
                        day_stats['multi_found'] += 1
                        
                except Exception as e:
                    print(f"  处理记录失败：{str(e)}")
                    day_stats['failed'] += 1
            
            # 提交当天的更新
            session.commit()
            print(f"  日期 {day_date} 处理完成：更新 {day_stats['updated']}，未找到 {day_stats['not_found']}，多条匹配 {day_stats['multi_found']}，无OE码 {day_stats['no_oe_code']}，失败 {day_stats['failed']}")
        
        return day_stats
        
    except Exception as e:
        print(f"处理日期 {day_date} 失败：{str(e)}")
        traceback.print_exc()
        return day_stats


# 数据批量回填成交信息 - 处理日期范围
def batch_get_update_deal_info(start_date, end_date):
    """
    批量从 crmapp_sales_history_detail 表获取数据并更新数据库中的成交信息
    
    Args:
        start_date: 开始日期，字符串格式，如 '2026-01-04'
        end_date: 结束日期，字符串格式，如 '2026-01-10'
        
    Returns:
        dict: 包含处理统计信息的字典
    """
    # 总统计信息
    total_stats = {
        'total': 0,           # 总处理记录数
        'updated': 0,         # 成功更新记录数（成交）
        'not_found': 0,       # 未找到匹配记录数
        'multi_found': 0,     # 匹配到多条记录数
        'no_oe_code': 0,      # 没有 OE 码的记录数
        'failed': 0           # 失败记录数
    }
    
    try:
        # 获取需要处理的日期范围
        
        # 解析日期
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 生成日期列表（支持同一天的情况）
        date_list = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_list.append(current_dt.strftime('%Y-%m-%d'))
            current_dt += timedelta(days=1)
        
        if not date_list:
            print("没有需要处理的日期")
            return total_stats
        
        print(f"开始处理，共 {len(date_list)} 天")
        
        # 按天循环调用处理单个日期的函数
        for day_date in date_list:
            day_stats = process_single_day(day_date)
            
            # 累加统计信息
            total_stats['total'] += day_stats['total']
            total_stats['updated'] += day_stats['updated']
            total_stats['not_found'] += day_stats['not_found']
            total_stats['multi_found'] += day_stats['multi_found']
            total_stats['no_oe_code'] += day_stats['no_oe_code']
            total_stats['failed'] += day_stats['failed']
        
        print(f"\n批量处理完成！统计：总 {total_stats['total']}，更新 {total_stats['updated']}，未找到匹配 {total_stats['not_found']}，多条匹配 {total_stats['multi_found']}，无OE码 {total_stats['no_oe_code']}，失败 {total_stats['failed']}")
        return total_stats
        
    except Exception as e:
        print(f"批量处理失败：{str(e)}")
        traceback.print_exc()
        return total_stats



def fetch_data_and_save_to_database(start_date, end_date):
    """
    获取并保存数据到数据库（按10天分批处理）
    
    Args:
        start_date: 开始日期字符串，如 "2026-01-01"
        end_date: 结束日期字符串，如 "2026-04-20"
    """
    
    print("\n" + "="*70)
    print("开始批量获取并保存数据")
    print("="*70)
    print(f"日期范围: {start_date} 至 {end_date}")
    
    # 解析日期
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    # 统计信息
    total_records = 0
    
    # 当前处理日期
    current_start = start_dt
    
    # 按10天一批循环处理
    batch_count = 0
    while current_start <= end_dt:
        batch_count += 1
        
        # 计算当前批次的结束日期（不超过总结束日期）
        current_end = current_start + timedelta(days=9)
        if current_end > end_dt:
            current_end = end_dt
        
        # 转换为字符串格式
        batch_start_str = current_start.strftime('%Y-%m-%d')
        batch_end_str = current_end.strftime('%Y-%m-%d')
        
        print(f"\n[批次 {batch_count}] 处理日期: {batch_start_str} 至 {batch_end_str}")
        
        try:
            # 查询数据
            db_data_list = get_weixin_decoding_result(batch_start_str, batch_end_str)
            
            # 转换数据
            data_list = convert_to_database_format(db_data_list)
            
            # 保存到数据库
            if data_list:
                save_stats = batch_save_to_database(data_list)
                print(f"批次 {batch_count} 完成: 获取 {len(data_list)} 条记录，保存统计: {save_stats}")
                total_records += len(data_list)
            else:
                print(f"批次 {batch_count} 完成: 无数据")
        
        except Exception as e:
            print(f"  ✗ 批次 {batch_count} 处理失败: {str(e)}")
            traceback.print_exc()
        
        # 移动到下一批
        current_start = current_end + timedelta(days=1)
    
    print("\n" + "="*70)
    print(f"全部完成！总共处理 {total_records} 条记录")
    print("="*70)




        
       


# def test_batch_get_update_deal_info():
#     """
#     测试批量更新成交信息函数
#     """
#     # 测试批量更新成交信息函数
#     batch_get_update_deal_info("2026-01-05", "2026-01-15")


# if __name__ == '__main__':
#     batch_get_update_deal_info("2026-01-01", "2026-01-21")
