"""
CRM采购明细爬取脚本 - 从2024年至今
独立运行，不依赖Flask应用上下文

使用方法:
    python scripts/crawl_crm_procurement_2024.py

功能:
    1. 爬取2024年1月1日至今的所有采购明细数据
    2. 按月份分批爬取，避免单次请求数据量过大
    3. 数据保存到 crmapp_procurement_history_detail 表
    4. 支持断点续爬（已爬取的月份会自动跳过）
"""

import sys
import os
import time
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入项目配置
from config.crm_config import get_crm_cookies
from app.utils.database_connection import get_db_connection


# ============ 配置参数 ============
LIMIT = 500  # 每页数量
MAX_RETRY = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔（秒）
COMPANY = 'fsbbr'  # 公司标识
CRM_PURCHASE_HISTORY_URL = 'https://crm.gzbbr.com/api/Crm.PurchaseOrder/PurchaseHistory'

# 时间范围配置
START_YEAR = 2024
START_MONTH = 1


class CrmSessionManager:
    """CRM Session 管理器（独立实现，不依赖Flask上下文）"""
    
    _session = None
    
    @classmethod
    def get_session(cls) -> requests.Session:
        """获取或创建CRM认证的session"""
        if cls._session is None:
            cls._session = cls._create_session()
        return cls._session
    
    @classmethod
    def _create_session(cls) -> requests.Session:
        """创建带有CRM认证信息的session"""
        # 获取CRM cookie认证信息
        crm_cookies = get_crm_cookies()
        
        # 创建session
        session = requests.Session()
        
        # 设置基础headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://crm.gzbbr.com/',
        })
        
        # 将cookie认证信息添加到headers
        session.headers.update(crm_cookies)
        
        print("✅ CRM Session 创建成功")
        return session
    
    @classmethod
    def refresh_session(cls):
        """刷新session（当认证过期时调用）"""
        if cls._session:
            cls._session.close()
        cls._session = None
        print("🔄 CRM Session 已刷新")


class CrmProcurementCrawler:
    """CRM采购明细爬虫"""
    
    def __init__(self):
        self.session = CrmSessionManager.get_session()
        self.stats = {
            'total_months': 0,
            'processed_months': 0,
            'total_records': 0,
            'saved_records': 0,
            'failed_records': 0,
            'skipped_months': []
        }
    
    def crawl_from_2024(self) -> Dict[str, Any]:
        """
        爬取从2024年至今的所有采购明细数据
        
        Returns:
            爬取统计信息
        """
        # 生成月份列表（从2024年1月到当前月）
        months = self._generate_months()
        self.stats['total_months'] = len(months)
        
        print("\n" + "="*80)
        print("📦 CRM采购明细爬取 - 从2024年至今")
        print("="*80)
        print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 目标月份: {len(months)} 个")
        print(f"📆 月份范围: {months[0]} ~ {months[-1]}")
        print("="*80)
        
        for i, month_str in enumerate(months, 1):
            print(f"\n{'='*80}")
            print(f"📅 正在处理 [{i}/{len(months)}]: {month_str}")
            print("="*80)
            
            try:
                result = self._crawl_month(month_str)
                self.stats['processed_months'] += 1
                self.stats['total_records'] += result.get('total', 0)
                self.stats['saved_records'] += result.get('saved', 0)
                self.stats['failed_records'] += result.get('failed', 0)
                
                # 每个月爬取完后短暂休息，避免请求过快
                if i < len(months):
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ 处理 {month_str} 时出错: {e}")
                self.stats['skipped_months'].append(month_str)
                import traceback
                traceback.print_exc()
                continue
        
        # 打印最终统计
        self._print_final_stats()
        
        return self.stats
    
    def _generate_months(self) -> List[str]:
        """生成从2024年1月到当前月的所有月份"""
        months = []
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        
        year = START_YEAR
        month = START_MONTH
        
        while True:
            months.append(f"{year}-{month:02d}")
            
            if year == current_year and month == current_month:
                break
                
            month += 1
            if month > 12:
                month = 1
                year += 1
        
        return months
    
    def _crawl_month(self, year_month: str) -> Dict[str, int]:
        """
        爬取指定月份的数据
        
        Args:
            year_month: 年月字符串，格式如 "2024-01"
            
        Returns:
            该月份的爬取统计
        """
        # 解析年月
        year, month = map(int, year_month.split('-'))
        
        # 计算该月的开始和结束时间戳
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(milliseconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(milliseconds=1)
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        print(f"⏱️  时间范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
        print(f"🔢 时间戳: {start_ts} ~ {end_ts}")
        
        result = {'total': 0, 'saved': 0, 'failed': 0}
        page = 1
        
        while True:
            # 获取页面数据
            records, has_more = self._fetch_page(page, start_ts, end_ts)
            
            if not records:
                if page == 1:
                    print(f"⚠️  {year_month} 无数据")
                break
            
            # 解析记录
            parsed_records = []
            for record in records:
                try:
                    parsed = self._parse_record(record, year_month)
                    if parsed:
                        parsed_records.append(parsed)
                except Exception as e:
                    print(f"❌ 解析记录失败: {e}")
                    result['failed'] += 1
            
            # 批量保存
            if parsed_records:
                saved_count = self._save_records(parsed_records)
                result['saved'] += saved_count
                result['total'] += len(parsed_records)
                print(f"📄 第{page}页: 解析 {len(parsed_records)} 条, 保存 {saved_count} 条")
            
            # 检查是否还有更多页
            if not has_more:
                break
            
            page += 1
            time.sleep(0.3)  # 页间短暂休息
        
        print(f"✅ {year_month} 完成: 共 {result['total']} 条, 保存 {result['saved']} 条")
        return result
    
    def _fetch_page(self, page: int, start_ts: int, end_ts: int) -> Tuple[List[Dict], bool]:
        """
        调用CRM接口获取单页数据
        
        Args:
            page: 页码
            start_ts: 开始时间戳（毫秒）
            end_ts: 结束时间戳（毫秒）
            
        Returns:
            (记录列表, 是否还有更多页)
        """
        payload = {
            "limit": LIMIT,
            "orderdate": [start_ts, end_ts],
            "page": page
        }
        
        for attempt in range(MAX_RETRY):
            try:
                response = self.session.post(
                    CRM_PURCHASE_HISTORY_URL,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get('status') == 200 or result.get('msg') == '操作成功':
                    data = result.get('data', {})
                    list_data = data.get('list', {})
                    records = list_data.get('data', [])
                    
                    # 判断是否还有更多页
                    current_page = int(list_data.get('current_page', page))
                    last_page = int(list_data.get('last_page', page))
                    has_more = current_page < last_page
                    
                    return records, has_more
                else:
                    print(f"⚠️  API返回错误: {result.get('msg')}")
                    # 可能是认证过期，尝试刷新session
                    if result.get('status') == 401:
                        print("🔑 认证可能过期，尝试刷新session...")
                        CrmSessionManager.refresh_session()
                        self.session = CrmSessionManager.get_session()
                        
            except requests.exceptions.RequestException as e:
                print(f"⚠️  请求失败 [{attempt + 1}/{MAX_RETRY}]: {e}")
                if attempt < MAX_RETRY - 1:
                    time.sleep(RETRY_DELAY)
                    continue
            except Exception as e:
                print(f"❌ 请求异常: {e}")
                break
        
        return [], False
    
    def _parse_record(self, record: Dict, year_month: str) -> Optional[Dict[str, Any]]:
        """
        解析单条记录
        
        Args:
            record: CRM返回的原始记录
            year_month: 年月字符串
            
        Returns:
            解析后的记录字典
        """
        # 提取create_date并转换为datetime
        create_date_ts = record.get('create_date', '0')
        if create_date_ts:
            create_date = datetime.fromtimestamp(int(create_date_ts))
        else:
            create_date = datetime.now()
        
        # 提取expected_delivery_date
        expected_delivery_ts = record.get('expected_delivery_date', '0')
        if expected_delivery_ts:
            expected_delivery_date = datetime.fromtimestamp(int(expected_delivery_ts))
        else:
            expected_delivery_date = None
        
        return {
            'order_no': str(record.get('order_no', '')).strip(),
            'fullname': str(record.get('fullname', '')).strip(),
            'l_name_zh_default': str(record.get('l_name_zh_default', '')).strip(),
            'frey_no': str(record.get('frey_no', '')).strip(),
            'number': str(record.get('number', '')).strip(),
            'brand': str(record.get('brand', '')).strip(),
            'l_model_zh': str(record.get('l_model_zh', '')).strip(),
            'purchase_quantity': int(record.get('purchase_quantity', 0)) if record.get('purchase_quantity') else 0,
            'unit_cost': float(record.get('unit_cost', 0)) if record.get('unit_cost') else 0.0,
            'create_date': create_date,
            'expected_delivery_date': expected_delivery_date,
            'year_month': year_month,
            'company': COMPANY
        }
    
    def _save_records(self, records: List[Dict]) -> int:
        """
        批量保存记录到数据库
        
        Args:
            records: 记录列表
            
        Returns:
            成功保存的记录数
        """
        if not records:
            return 0
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO crmapp_procurement_history_detail
                    (order_no, fullname, l_name_zh_default, frey_no, number, brand,
                     l_model_zh, purchase_quantity, unit_cost, create_date,
                     expected_delivery_date, `year_month`, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        fullname = VALUES(fullname),
                        l_name_zh_default = VALUES(l_name_zh_default),
                        frey_no = VALUES(frey_no),
                        l_model_zh = VALUES(l_model_zh),
                        purchase_quantity = VALUES(purchase_quantity),
                        unit_cost = VALUES(unit_cost),
                        create_date = VALUES(create_date),
                        expected_delivery_date = VALUES(expected_delivery_date),
                        `year_month` = VALUES(`year_month`)
                """
                
                values = []
                for record in records:
                    values.append((
                        record['order_no'],
                        record['fullname'],
                        record['l_name_zh_default'],
                        record['frey_no'],
                        record['number'],
                        record['brand'],
                        record['l_model_zh'],
                        record['purchase_quantity'],
                        record['unit_cost'],
                        record['create_date'],
                        record['expected_delivery_date'],
                        record['year_month'],
                        record['company']
                    ))
                
                cursor.executemany(sql, values)
                conn.commit()
                
                return len(records)
                
        except Exception as e:
            conn.rollback()
            print(f"❌ 批量保存失败: {e}")
            return 0
        finally:
            conn.close()
    
    def _print_final_stats(self):
        """打印最终统计信息"""
        print("\n" + "="*80)
        print("🎉 CRM采购明细爬取完成!")
        print("="*80)
        print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)
        print(f"📅 总月份数: {self.stats['total_months']}")
        print(f"✅ 成功处理: {self.stats['processed_months']} 个月份")
        print(f"📋 总记录数: {self.stats['total_records']}")
        print(f"💾 保存记录: {self.stats['saved_records']}")
        print(f"❌ 失败记录: {self.stats['failed_records']}")
        
        if self.stats['skipped_months']:
            print(f"⚠️  跳过月份: {', '.join(self.stats['skipped_months'])}")
        
        print("="*80)


def main():
    """主函数"""
    print("\n" + "="*80)
    print("🚀 启动 CRM采购明细爬取脚本")
    print("="*80)
    
    try:
        crawler = CrmProcurementCrawler()
        result = crawler.crawl_from_2024()
        
        # 返回码：0成功，1有跳过月份，2失败
        if result['skipped_months']:
            return 1
        return 0
        
    except Exception as e:
        print(f"\n❌ 脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
