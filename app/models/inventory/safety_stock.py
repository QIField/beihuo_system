# -*- coding: utf-8 -*-
"""
安全库存模型
使用原生 PyMySQL 操作数据库，与项目保持一致
"""
from datetime import datetime
from typing import List, Dict, Optional
from app.utils.database_connection import db_query_one, db_query_all, db_execute, get_db_connection


class SafetyStock:
    """安全库存计算结果模型"""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.sku = kwargs.get('sku')
        self.sku_name = kwargs.get('sku_name')
        self.calc_date = kwargs.get('calc_date')
        self.demand_avg = kwargs.get('demand_avg', 0)
        self.demand_max = kwargs.get('demand_max', 0)
        self.demand_std = kwargs.get('demand_std', 0)
        self.lead_time_avg = kwargs.get('lead_time_avg', 0)
        self.lead_time_max = kwargs.get('lead_time_max', 0)
        self.safety_stock = kwargs.get('safety_stock', 0)
        self.inventory_min = kwargs.get('inventory_min', 0)
        self.reorder_point = kwargs.get('reorder_point', 0)
        self.inventory_max = kwargs.get('inventory_max', 0)
        self.target_inventory = kwargs.get('target_inventory', 0)
        self.current_stock = kwargs.get('current_stock', 0)
        self.suggested_qty = kwargs.get('suggested_qty', 0)
        self.stock_status = kwargs.get('stock_status', 'normal')
        self.inquiry_1m = kwargs.get('inquiry_1m', 0)
        self.inquiry_3m = kwargs.get('inquiry_3m', 0)
        self.service_level = kwargs.get('service_level', 0.95)
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'sku': self.sku,
            'sku_name': self.sku_name,
            'calc_date': self.calc_date.strftime('%Y-%m-%d') if isinstance(self.calc_date, datetime) else self.calc_date,
            'demand_avg': float(self.demand_avg) if self.demand_avg else 0,
            'demand_max': float(self.demand_max) if self.demand_max else 0,
            'demand_std': float(self.demand_std) if self.demand_std else 0,
            'lead_time_avg': float(self.lead_time_avg) if self.lead_time_avg else 0,
            'lead_time_max': float(self.lead_time_max) if self.lead_time_max else 0,
            'safety_stock': float(self.safety_stock) if self.safety_stock else 0,
            'inventory_min': float(self.inventory_min) if self.inventory_min else 0,
            'reorder_point': float(self.reorder_point) if self.reorder_point else 0,
            'inventory_max': float(self.inventory_max) if self.inventory_max else 0,
            'target_inventory': float(self.target_inventory) if self.target_inventory else 0,
            'current_stock': float(self.current_stock) if self.current_stock else 0,
            'suggested_qty': float(self.suggested_qty) if self.suggested_qty else 0,
            'stock_status': self.stock_status,
            'inquiry_1m': self.inquiry_1m,
            'inquiry_3m': self.inquiry_3m,
            'service_level': float(self.service_level) if self.service_level else 0.95,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(self.updated_at, datetime) else self.updated_at
        }
    
    def save(self) -> bool:
        """保存到数据库"""
        sql = """
            INSERT INTO crmapp_safety_stock (
                sku, sku_name, calc_date, demand_avg, demand_max, demand_std,
                lead_time_avg, lead_time_max, safety_stock, inventory_min,
                reorder_point, inventory_max, target_inventory, current_stock,
                suggested_qty, stock_status, inquiry_1m, inquiry_3m, service_level
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        params = (
            self.sku, self.sku_name, self.calc_date, self.demand_avg, self.demand_max,
            self.demand_std, self.lead_time_avg, self.lead_time_max, self.safety_stock,
            self.inventory_min, self.reorder_point, self.inventory_max, self.target_inventory,
            self.current_stock, self.suggested_qty, self.stock_status, self.inquiry_1m,
            self.inquiry_3m, self.service_level
        )
        result = db_execute(sql, params)
        return result > 0
    
    @classmethod
    def get_by_sku(cls, sku: str, limit: int = 1) -> List['SafetyStock']:
        """查询指定SKU的最新计算结果"""
        sql = """
            SELECT * FROM crmapp_safety_stock 
            WHERE sku = %s 
            ORDER BY calc_date DESC 
            LIMIT %s
        """
        results = db_query_all(sql, (sku, limit), dict_cursor=True)
        return [cls(**row) for row in results] if results else []
    
    @classmethod
    def get_warning_list(cls, status: str = 'danger') -> List['SafetyStock']:
        """获取预警列表"""
        sql = """
            SELECT * FROM crmapp_safety_stock 
            WHERE stock_status = %s 
            ORDER BY suggested_qty DESC
        """
        results = db_query_all(sql, (status,), dict_cursor=True)
        return [cls(**row) for row in results] if results else []
    
    @classmethod
    def get_list(cls, page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict:
        """获取列表（带分页）"""
        # 构建WHERE条件
        where_clause = ""
        params = []
        if status:
            where_clause = "WHERE s.stock_status = %s"
            params.append(status)
        
        # 查询总数
        count_sql = f"""
            SELECT COUNT(*) as total FROM (
                SELECT sku, MAX(calc_date) as max_date 
                FROM crmapp_safety_stock 
                GROUP BY sku
            ) latest
        """
        count_result = db_query_one(count_sql, dict_cursor=True)
        total = count_result['total'] if count_result else 0
        
        # 查询数据（只取每个SKU的最新记录）
        sql = f"""
            SELECT s.* FROM crmapp_safety_stock s
            INNER JOIN (
                SELECT sku, MAX(calc_date) as max_date 
                FROM crmapp_safety_stock 
                GROUP BY sku
            ) latest ON s.sku = latest.sku AND s.calc_date = latest.max_date
            {where_clause}
            ORDER BY s.safety_stock DESC
            LIMIT %s OFFSET %s
        """
        query_params = params + [page_size, (page - 1) * page_size]
        results = db_query_all(sql, tuple(query_params), dict_cursor=True)
        
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': [cls(**row).to_dict() for row in results] if results else []
        }


# 便捷函数
def get_db_session():
    """
    获取数据库连接（上下文管理器兼容）
    为了保持和SQLAlchemy版本兼容，返回一个模拟的上下文管理器
    """
    class DBSession:
        def __enter__(self):
            self.conn = get_db_connection()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.conn:
                self.conn.close()
            return False
        
        def query(self, model_class):
            """模拟查询接口"""
            return QueryProxy(model_class, self.conn)
        
        def add(self, obj):
            """添加对象"""
            return obj.save()
        
        def commit(self):
            """提交事务"""
            # PyMySQL自动提交，这里什么都不做
            pass
    
    class QueryProxy:
        """查询代理类"""
        def __init__(self, model_class, conn):
            self.model_class = model_class
            self.conn = conn
            self.filters = []
        
        def filter(self, *conditions):
            """添加过滤条件"""
            # 简化实现，实际使用时直接调用模型类方法
            return self
        
        def order_by(self, *columns):
            """排序"""
            return self
        
        def limit(self, n):
            """限制数量"""
            return self
        
        def all(self):
            """获取所有结果"""
            return []
        
        def count(self):
            """计数"""
            return 0
    
    return DBSession()
