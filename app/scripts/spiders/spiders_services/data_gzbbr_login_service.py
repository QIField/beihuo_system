# -*- coding:utf-8 -*-
# @Time    : 2026/08/28
# @Author  : Data GZBBR Login Service
# @Project : beihuo_system
# @File    : data_gzbbr_login_service.py
# @Software: PyCharm

"""
data.gzbbr.com 登录业务服务层

职责：
- 编排登录流程
- 登录成功后保存 Cookie 到系统配置
- 对外提供统一的 run() 入口
"""

from typing import Optional, Tuple

from app.scripts.spiders.spider_entities.data_gzbbr_login import DataGzbbrLoginSpider
from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from app.utils.logger_config import get_task_logger

logger = get_task_logger("data_gzbbr_login")


class DataGzbbrLoginService:
    """data.gzbbr.com 登录业务服务"""

    DEFAULT_CONFIG_KEY = "data_gzbbr_com_fs"

    def __init__(
        self,
        username: str = "张锐",
        password: str = "China2028",
        config_key: str = DEFAULT_CONFIG_KEY,
    ):
        self.username = username
        self.password = password
        self.config_key = config_key

    def save_cookie_to_config(self, cookie_str: str) -> bool:
        """将 Cookie 保存到指定配置键（带缓存刷新）"""
        try:
            result = update_json_config(
                config_key=self.config_key,
                update_dict={"cookie": cookie_str},
                env="prod",
            )
            if result.get("code") == 200:
                logger.info(f"[配置] Cookie 已保存到配置键 '{self.config_key}'")
                return True
            else:
                logger.error(f"[配置] 保存 Cookie 失败: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"[配置] 保存 Cookie 异常: {e}")
            return False

    def run(self) -> Tuple[bool, str]:
        """
        执行登录并更新 Cookie

        Returns:
            (是否成功, Cookie 字符串或错误信息)
        """
        spider = None
        try:
            logger.info("[服务] 开始执行 data.gzbbr.com 登录更新 Cookie")
            spider = DataGzbbrLoginSpider(
                username=self.username,
                password=self.password,
            )

            login_success, cookie_str = spider.login()
            if not login_success or not cookie_str:
                logger.error("[服务] 登录失败，未获取到有效 Cookie")
                return False, ""

            if self.save_cookie_to_config(cookie_str):
                logger.info("[服务] 登录并更新 Cookie 完成")
                return True, cookie_str
            else:
                logger.error("[服务] 登录成功但保存 Cookie 失败")
                return False, cookie_str

        except Exception as e:
            logger.exception(f"[服务] 登录更新 Cookie 流程异常: {e}")
            return False, ""
        finally:
            if spider:
                spider.close()


def run_data_gzbbr_login(config_key: Optional[str] = None) -> Tuple[bool, str]:
    """便捷函数：执行一次登录并更新 Cookie"""
    service = DataGzbbrLoginService(config_key=config_key or DataGzbbrLoginService.DEFAULT_CONFIG_KEY)
    return service.run()
