"""
品牌优先级管理
用于车型同步时确定哪个品牌的车型优先使用
"""


class BrandPriority:
    """品牌优先级管理类"""

    # 优先级定义：数字越小优先级越高
    PRIORITY_MAP = {
        '原厂国内4s件': 1,
        '原厂': 2,
    }

    @classmethod
    def get_priority(cls, brand: str) -> int:
        """
        获取品牌优先级

        Args:
            brand: 品牌名称

        Returns:
            优先级数字，1为最高，3为最低（其他品牌）
        """
        return cls.PRIORITY_MAP.get(brand, 3)

    @classmethod
    def is_high_priority(cls, brand: str) -> bool:
        """
        判断是否为高优先级品牌（原厂国内4s件或原厂）

        Args:
            brand: 品牌名称

        Returns:
            是否为高优先级
        """
        return cls.get_priority(brand) <= 2

    @classmethod
    def get_best_model(cls, models: dict) -> tuple:
        """
        从多个品牌车型中选择优先级最高的车型

        Args:
            models: 字典，格式为 {品牌: (车型, 优先级)}

        Returns:
            (最佳车型, 最佳优先级)，如果没有高优先级则返回 (None, None)
        """
        if not models:
            return None, None

        # 按优先级排序，取优先级最高的
        sorted_models = sorted(models.items(), key=lambda x: x[1][1])
        best_brand, (best_model, best_priority) = sorted_models[0]

        # 只返回高优先级的车型（优先级1或2）
        if best_priority <= 2:
            return best_model, best_priority

        return None, None
