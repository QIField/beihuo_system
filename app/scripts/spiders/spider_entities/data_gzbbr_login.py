# -*- coding:utf-8 -*-
# @Time    : 2026/08/28
# @Author  : Data GZBBR Login Spider
# @Project : beihuo_system
# @File    : data_gzbbr_login.py
# @Software: PyCharm

"""
data.gzbbr.com 验证码登录交互层

职责：
- 只负责与 data.gzbbr.com 网站交互
- 验证码获取、OCR 识别、登录提交、提取 Cookie
- 不处理业务编排（如保存配置），不处理定时任务调度
"""

import json
import os
import random
import sys
import time
from typing import Any, Dict, Optional, Tuple

# 确保直接运行脚本时能找到项目根目录
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.scripts.spiders.spider_tool import SpiderTool
from app.utils.logger_config import get_task_logger

logger = get_task_logger("data_gzbbr_login")


class DataGzbbrLoginSpider:
    """data.gzbbr.com 登录交互类"""

    BASE_URL = "https://data.gzbbr.com"
    VERIFY_URL = f"{BASE_URL}/admin/Login/verify.html"
    LOGIN_URL = f"{BASE_URL}/admin/Login/index.html"

    def __init__(
        self,
        username: str = "张锐",
        password: str = "China2028",
        timeout: int = 30,
        retry_count: int = 3,
        max_verify_attempts: int = 5,
    ):
        self.username = username
        self.password = password
        self.max_verify_attempts = max_verify_attempts

        self.spider_tool = SpiderTool(timeout=timeout, retry_count=retry_count)
        self.session = self.spider_tool.session
        self._ocr = None

    def _get_ocr(self):
        """懒加载 ddddocr 识别器"""
        if self._ocr is not None:
            return self._ocr

        try:
            import ddddocr

            self._ocr = ddddocr.DdddOcr(show_ad=False)
            logger.info("[OCR] ddddocr 初始化成功")
            return self._ocr
        except ImportError:
            logger.error("[OCR] 未安装 ddddocr 库，请执行: pip install ddddocr")
            return None
        except Exception as e:
            logger.error(f"[OCR] 初始化失败: {e}")
            return None

    def _generate_random_param(self) -> str:
        """生成随机参数，防止验证码缓存"""
        return str(random.random())

    def get_verify_image(self) -> Optional[bytes]:
        """获取验证码图片二进制数据"""
        try:
            random_param = self._generate_random_param()
            url = f"{self.VERIFY_URL}?{random_param}"

            headers = {
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": f"{self.BASE_URL}/admin/Login/index.html",
            }

            response = self.session.get(
                url,
                headers=headers,
                timeout=self.spider_tool.timeout,
            )

            if response.status_code != 200:
                logger.error(f"[验证码] 获取失败: HTTP {response.status_code}")
                return None

            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type:
                logger.error(f"[验证码] 响应类型不是图片: {content_type}")
                return None

            logger.info(f"[验证码] 获取成功，大小: {len(response.content)} bytes")
            return response.content

        except Exception as e:
            logger.error(f"[验证码] 获取异常: {e}")
            return None

    def recognize_verify(self, image_data: bytes) -> Optional[str]:
        """使用 ddddocr 识别验证码"""
        if not image_data:
            return None

        ocr = self._get_ocr()
        if ocr is None:
            return None

        try:
            result = ocr.classification(image_data)
            if result:
                verify_text = str(result).strip().lower()
                logger.info(f"[OCR] 识别结果: {verify_text}")
                return verify_text
            else:
                logger.warning("[OCR] 识别结果为空")
                return None
        except Exception as e:
            logger.error(f"[OCR] 识别异常: {e}")
            return None

    def _validate_verify_text(self, verify_text: str) -> bool:
        """简单校验验证码格式"""
        if not verify_text:
            return False
        text = verify_text.strip()
        if len(text) != 4:
            return False
        return text.isalnum()

    def submit_login(self, verify_code: str) -> Tuple[bool, Dict[str, Any]]:
        """提交登录请求"""
        try:
            login_data = {
                "username": self.username,
                "password": self.password,
                "verify": verify_code,
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/admin/Login/index.html",
                "X-Requested-With": "XMLHttpRequest",
            }

            logger.info(f"[登录] 提交请求: username={self.username}, verify={verify_code}")

            response = self.session.post(
                self.LOGIN_URL,
                data=login_data,
                headers=headers,
                timeout=self.spider_tool.timeout,
            )

            logger.info(f"[登录] 响应状态码: {response.status_code}")

            try:
                response_data = response.json()
                logger.info(f"[登录] 响应内容: {response_data}")

                code = response_data.get("code") or response_data.get("status")
                msg = response_data.get("msg", "")

                if code in (1, 200, "1", "200"):
                    return True, {"data": response_data, "msg": msg}
                else:
                    return False, {"data": response_data, "msg": msg}
            except json.JSONDecodeError:
                logger.warning(f"[登录] 响应非 JSON: {response.text[:200]}")
                if response.status_code == 200 and self.session.cookies:
                    return True, {"data": response.text[:200]}
                return False, {"error": "响应格式错误"}

        except Exception as e:
            logger.error(f"[登录] 请求异常: {e}")
            return False, {"error": str(e)}

    def get_login_cookies(self) -> str:
        """将当前登录会话的 cookies 拼接为字符串"""
        cookie_dict = self.session.cookies.get_dict()
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
        logger.info(f"[Cookie] 提取到登录 Cookie: {cookie_str}")
        return cookie_str

    def login(self) -> Tuple[bool, str]:
        """完整登录流程，包含验证码自动重试"""
        logger.info("=" * 60)
        logger.info(f"[登录流程] 开始 data.gzbbr.com 登录 - 用户: {self.username}")
        logger.info("=" * 60)

        for attempt in range(1, self.max_verify_attempts + 1):
            logger.info(f"\n[尝试 {attempt}/{self.max_verify_attempts}]")

            logger.info("  步骤1: 获取验证码图片...")
            verify_image = self.get_verify_image()
            if not verify_image:
                logger.warning("  [失败] 无法获取验证码图片，等待后重试...")
                time.sleep(1)
                continue

            logger.info("  步骤2: OCR 识别验证码...")
            verify_text = self.recognize_verify(verify_image)
            if not verify_text or not self._validate_verify_text(verify_text):
                logger.warning(f"  [失败] 验证码识别失败或格式不正确: '{verify_text}'，重新获取...")
                continue

            logger.info("  步骤3: 提交登录请求...")
            success, result = self.submit_login(verify_text)

            if success:
                cookie_str = self.get_login_cookies()
                logger.info("  [成功] 登录成功并获取 Cookie")
                return True, cookie_str
            else:
                error_msg = result.get("msg", result.get("error", "未知错误"))
                logger.warning(f"  [失败] 登录失败: {error_msg}")

                if "验证码" in error_msg or "verify" in error_msg.lower():
                    logger.info("  可能是验证码识别错误，重新获取验证码...")
                    continue
                else:
                    return False, ""

        logger.error("\n[登录流程] 所有登录尝试均失败")
        return False, ""

    def close(self):
        """关闭登录会话"""
        self.spider_tool.close()


if __name__ == "__main__":
    spider = DataGzbbrLoginSpider()
    try:
        success, cookie = spider.login()
        logger.info(f"\n最终状态: {success}")
        logger.info(f"Cookie: {cookie}")
    finally:
        spider.close()
