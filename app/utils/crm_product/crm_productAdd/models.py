"""
CRM 产品添加模块的数据模型
"""

from dataclasses import dataclass
from typing import Optional


# 处理状态常量
class ProcessStatus:
    SUCCESS = 'success'
    EXISTED = 'existed'
    FAILED = 'failed'


@dataclass
class ProcessResult:
    """
    单个 OE+品牌的处理结果

    Attributes:
        oe_number: OE 号
        brand: 品牌名称
        status: 处理状态 (success / existed / failed)
        product_id: CRM 产品 ID，成功或已存在时可能返回
        message: 结果描述
        brand_code_updated: 是否成功更新 brand_code（三列模式）
    """
    oe_number: str
    status: str
    brand: Optional[str] = None
    product_id: Optional[str] = None
    message: str = ''
    brand_code_updated: bool = False

    def is_success(self) -> bool:
        """是否处理成功（包含已存在）"""
        return self.status in (ProcessStatus.SUCCESS, ProcessStatus.EXISTED)
