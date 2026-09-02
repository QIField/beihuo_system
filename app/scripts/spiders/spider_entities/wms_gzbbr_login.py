# -*- coding:utf-8 -*-
# @Time    : 2026/06/13
# @Author  : WMS GZBBR Login Spider
# @Project : beihuo_system
# @File    : wms_gzbbr_login.py
# @Software: PyCharm

"""
WMS网站自动登录模块
登录流程：
1. GET https://wms.gzbbr.com/api/Base/captcha 获取验证码图片
2. OCR识别验证码文字（使用 ddddocr 库）
3. POST https://wms.gzbbr.com/api/User/login 提交登录信息
4. 从响应中提取 token
"""

import json
import random
import time
from typing import Optional, Tuple, Dict, Any

from app.scripts.spiders.spider_tool import SpiderTool
from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from config.config_list_manager.config_cache import get_config_value


class WmsGzbbrLogin:
    """WMS登录类 - 处理完整的登录流程，包括验证码识别"""

    # 基础 URL 配置
    BASE_URL = "https://wms.gzbbr.com"
    CAPTCHA_URL = f"{BASE_URL}/api/Base/captcha"
    LOGIN_URL = f"{BASE_URL}/api/User/login"

    # 登录渠道
    CHANNEL = "wms"

    def __init__(self, username: str, password: str, timeout: int = 30,
                 retry_count: int = 3, max_captcha_attempts: int = 5):
        """
        初始化登录类

        Args:
            username: 登录用户名
            password: 登录密码
            timeout: 请求超时时间（秒）
            retry_count: 重试次数
            max_captcha_attempts: 验证码识别失败后最大重试次数
        """
        self.username = username
        self.password = password
        self.max_captcha_attempts = max_captcha_attempts

        # 初始化爬虫工具（用于图片获取和登录请求）
        self.spider_tool = SpiderTool(timeout=timeout, retry_count=retry_count)
        self.session = self.spider_tool.session

        # OCR识别器（延迟初始化）
        self._ocr = None

    def _get_ocr(self):
        """
        懒加载OCR识别器 - 使用 ddddocr 库进行验证码识别

        Returns:
            ddddocr实例或None
        """
        if self._ocr is not None:
            return self._ocr

        try:
            import ddddocr
            # show_ad=False 关闭广告弹窗
            self._ocr = ddddocr.DdddOcr(show_ad=False)
            return self._ocr
        except ImportError:
            print("警告: 未安装 ddddocr 库，无法自动识别验证码")
            print("请执行: pip install ddddocr")
            return None
        except Exception as e:
            print(f"警告: OCR初始化失败: {e}")
            return None

    def _generate_random_param(self) -> str:
        """
        生成随机参数，用于验证码URL（防止缓存）
        模拟浏览器的行为: https://wms.gzbbr.com/api/Base/captcha?0.14606573240401777

        Returns:
            随机小数字符串
        """
        return str(random.random())

    def get_captcha_image(self) -> Optional[bytes]:
        """
        获取验证码图片

        Returns:
            图片二进制数据(bytes)，失败返回None
        """
        try:
            random_param = self._generate_random_param()
            url = f"{self.CAPTCHA_URL}?{random_param}"

            # 构造请求头
            headers = {
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": f"{self.BASE_URL}/",
            }

            # 使用 session 发送请求（保持cookie会话）
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.spider_tool.timeout
            )

            if response.status_code != 200:
                print(f"获取验证码失败: HTTP {response.status_code}")
                return None

            # 检查响应内容是否为图片
            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type and "image" not in str(response.content[:4]):
                # 尝试解析是否为JSON错误
                try:
                    error_data = response.json()
                    print(f"获取验证码失败: {error_data}")
                except:
                    print(f"获取验证码失败: 返回的不是图片数据")
                return None

            print(f"成功获取验证码图片，大小: {len(response.content)} bytes")
            return response.content

        except Exception as e:
            print(f"获取验证码图片异常: {e}")
            return None

    def recognize_captcha(self, image_data: bytes) -> Optional[str]:
        """
        使用OCR识别验证码

        Args:
            image_data: 验证码图片的二进制数据

        Returns:
            识别出的验证码文字，失败返回None
        """
        if not image_data:
            return None

        ocr = self._get_ocr()
        if ocr is None:
            # 如果没有OCR库，返回空让用户处理
            return None

        try:
            result = ocr.classification(image_data)
            if result:
                captcha_text = str(result).strip()
                print(f"OCR识别结果: {captcha_text}")
                return captcha_text
            else:
                print("OCR识别结果为空")
                return None
        except Exception as e:
            print(f"OCR识别异常: {e}")
            return None

    def _validate_captcha_text(self, captcha_text: str) -> bool:
        """
        简单验证识别出的验证码文字是否合理
        根据HAR文件观察，验证码通常是4位字母（如 hVPA、GG2Q）

        Args:
            captcha_text: 识别出的验证码文字

        Returns:
            是否符合基本格式要求
        """
        if not captcha_text:
            return False

        # 去除空格
        text = captcha_text.strip()

        # 验证码通常是4位字母数字
        if len(text) < 3 or len(text) > 6:
            return False

        # 只包含字母和数字
        return text.replace(" ", "").isalnum()

    def submit_login(self, captcha: str) -> Tuple[bool, Dict[str, Any]]:
        """
        提交登录请求

        Args:
            captcha: 验证码文字

        Returns:
            (是否成功, 响应数据字典)
            成功时字典格式: {"status": 200, "msg": "...", "data": {...}, "token": "..."}
            失败时字典格式: {"error": "..."}
        """
        try:
            # 构造登录请求体
            # 根据HAR文件分析: {"captcha":"hVPA","user":"李德杰","pwd":"ajs2315","channel":"wms"}
            login_data = {
                "captcha": captcha,
                "user": self.username,
                "pwd": self.password,
                "channel": self.CHANNEL
            }

            # 构造请求头
            headers = {
                "Content-Type": "application/json;chartset=utf-8",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
            }

            print(f"提交登录请求: user={self.username}, captcha={captcha}")

            # 使用 session 发送 POST 请求（保持cookie一致性）
            response = self.session.post(
                self.LOGIN_URL,
                json=login_data,
                headers=headers,
                timeout=self.spider_tool.timeout
            )

            if response.status_code != 200:
                print(f"登录请求失败: HTTP {response.status_code}")
                return False, {"error": f"HTTP {response.status_code}"}

            # 解析响应
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                print(f"登录响应不是JSON: {response.text[:200]}")
                return False, {"error": "响应格式错误"}

            # 检查响应状态
            status = response_data.get("status")
            msg = response_data.get("msg", "")

            if status == 200 and "token" in response_data:
                print(f"登录成功! token已获取，长度: {len(response_data['token'])}")
                return True, response_data
            else:
                print(f"登录失败: status={status}, msg={msg}")
                return False, response_data

        except Exception as e:
            print(f"登录请求异常: {e}")
            return False, {"error": str(e)}

    def login(self) -> Tuple[bool, Dict[str, Any]]:
        """
        执行完整的登录流程（包含验证码自动重试）

        Returns:
            (是否成功, 结果数据字典)
            成功时: {"token": "...", "data": {...}, "msg": "..."}
            失败时: {"error": "..."}
        """
        print("=" * 60)
        print(f"开始WMS网站登录流程 - 用户: {self.username}")
        print("=" * 60)

        # 多次尝试登录（验证码识别可能失败）
        for attempt in range(1, self.max_captcha_attempts + 1):
            print(f"\n[尝试 {attempt}/{self.max_captcha_attempts}]")

            # 步骤1: 获取验证码图片
            print("  步骤1: 获取验证码图片...")
            captcha_image = self.get_captcha_image()
            if not captcha_image:
                print("  [失败] 无法获取验证码图片，等待后重试...")
                time.sleep(1)
                continue

            # 步骤2: OCR识别验证码
            print("  步骤2: OCR识别验证码...")
            captcha_text = self.recognize_captcha(captcha_image)
            if not captcha_text or not self._validate_captcha_text(captcha_text):
                print(f"  [失败] 验证码识别失败或格式不正确: '{captcha_text}'，重新获取...")
                continue

            # 步骤3: 提交登录请求
            print("  步骤3: 提交登录请求...")
            success, result = self.submit_login(captcha_text)

            if success:
                # 登录成功，返回结构化数据
                return True, {
                    "token": result.get("token", ""),
                    "data": result.get("data", {}),
                    "msg": result.get("msg", ""),
                    "status": result.get("status", 200),
                    "captcha_used": captcha_text
                }
            else:
                # 登录失败（可能是验证码错误）
                error_msg = result.get("msg", result.get("error", "未知错误"))
                print(f"  [失败] 登录失败: {error_msg}")

                # 如果是验证码错误，继续尝试
                if "验证码" in error_msg or "captcha" in error_msg.lower():
                    print("  可能是验证码识别错误，重新获取验证码...")
                    continue
                # 其他错误（如用户名密码错误）直接返回
                else:
                    return False, {"error": error_msg}

        # 所有尝试都失败
        print("\n所有登录尝试均失败")
        return False, {"error": f"验证码识别或登录失败，已尝试 {self.max_captcha_attempts} 次"}

    def get_token(self) -> Optional[str]:
        """
        执行登录并返回token的便捷方法

        Returns:
            token字符串，失败返回None
        """
        success, result = self.login()
        if success:
            return result.get("token")
        return None

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()


class WmsGzbbrLoginService:
    """WMS登录服务类 - 提供高级功能和便捷方法"""

    # ========== 配置键名常量 ==========
    CONFIG_KEY = "wms_gzbbr"   # 在数据库中保存 WMS 配置的键名
    # 用于 token 验证的接口（一个简单的 GET 接口，无需参数）
    # 返回格式：{"status": 200, "msg": "返回成功", "data": {"alertred": 0}}
    VALIDATE_API_URL = "https://wms.gzbbr.com/api/Wms.Move/goodsshelves"

    @staticmethod
    def validate_token(token: str) -> Tuple[bool, str]:
        """
        验证 Token 是否有效
        通过调用 goodsshelves 接口，检查响应体 JSON 中的 status 字段：
        - body.status == 200 → token 有效
        - body.status == 401/403 → token 已过期或无效
        - HTTP 401/403 → token 已过期或无效

        WMS 接口统一返回格式：{"status": 200, "msg": "...", "data": {...}}
        其中 status 是 JSON body 内的业务状态码，不是 HTTP 状态码

        Args:
            token: 登录获取的 JWT token

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息或空字符串)
        """
        spider_tool = SpiderTool(timeout=10, retry_count=1)
        try:
            # 请求头格式：和 WmsGzbbrSpider._get_auth_header() 完全一致
            headers = {"Authorization": token}
            print(f"【验证 token】请求 {WmsGzbbrLoginService.VALIDATE_API_URL}")
            response = spider_tool.fetch(
                WmsGzbbrLoginService.VALIDATE_API_URL,
                method="GET",
                headers=headers
            )
            # print(response.json())
            if not response:
                return False, "请求失败，无法验证Token"

            # 先检查 HTTP 状态码
            if response.status_code == 401:
                return False, "Token已过期或无效（HTTP 401）"
            elif response.status_code == 403:
                return False, "Token权限不足（HTTP 403）"
            elif response.status_code != 200:
                return False, f"请求返回异常HTTP状态码：{response.status_code}"
            elif response.json().get("status",{}) == 104:
                return False, response.json().get("msg", "您的账号已在其它设备上登录，请重新登录")

            # 关键：检查 JSON body 中的业务 status 字段
            # WMS 统一格式：{"status": 200, "msg": "...", "data": ...}
            try:
                data = response.json()
                body_status = data.get("status")

                if body_status == 200:
                    # 业务状态为 200 → token 有效
                    return True, ""
                elif body_status in (101, 401, 403):
                    # 101: token过期；401/403: 认证失败
                    msg = data.get("msg", f"业务状态码：{body_status}")
                    return False, f"Token已过期或无效（{msg}）"
                else:
                    # 其他业务错误（如参数错误），但接口有响应说明 token 没被服务端拒绝
                    # 只要不是明确拒绝，就认为 token 有效
                    return True, ""
            except Exception:
                # 解析失败，但 HTTP 200，保守认为 token 有效
                return True, ""

        except Exception as e:
            return False, f"验证Token时发生异常：{str(e)}"
        finally:
            spider_tool.close()

    @staticmethod
    def get_valid_config() -> str:
        """
        获取有效的 WMS 配置，按照指定的登录流程
        从数据库获取配置，如果 token 无效则自动使用配置中的 username/password 重新登录

        登录流程:
        1. 先从数据库获取配置
        2. 验证 token 是否有效
        3. 如果验证失败，调用 API 登录（使用配置中保存的 username/password）
        4. 登录成功后保存到数据库
        5. 再次验证新配置
        6. 如果还是失败则抛出异常

        Returns:
            str: 有效的 token 字符串

        Raises:
            Exception: 多次验证失败后抛出异常
        """
        print("=" * 80)
        print("开始获取 WMS 配置...")
        print("=" * 80)

        # 1. 先从数据库获取配置
        print("\n[1/6] 尝试从数据库获取现有配置...")
        config = get_config_value(WmsGzbbrLoginService.CONFIG_KEY)
        

        if config:
            token = config.get("token")  # pyright: ignore[reportAttributeAccessIssue]

            if token:
                print("[成功] 从数据库获取到配置")

                # 2. 验证 token 是否有效
                print("\n[2/6] 验证数据库中的 token...")
                is_valid, error_msg = WmsGzbbrLoginService.validate_token(token)
               
                if is_valid:
                    print("[成功] 数据库中的 token 有效，直接使用现有配置")
                    print("=" * 80)
                    return token
                else:
                    print(f"[失败] Token 验证失败: {error_msg}")
                    print("需要重新登录...")
            else:
                print("[失败] 数据库中没有有效的 token")
        else:
            print("[失败] 数据库中没有找到配置")

        # 从配置中获取登录凭据
        username = config.get("username") if config else None  # pyright: ignore[reportAttributeAccessIssue]
        password = config.get("password") if config else None  # pyright: ignore[reportAttributeAccessIssue]

        # 检查是否有登录凭据
        if not username or not password:
            raise Exception(
                f"无法登录：配置 '{WmsGzbbrLoginService.CONFIG_KEY}' 中没有保存用户名和密码"
            )

        # 3. 调用 API 登录
        print("\n[3/6] 开始 API 登录...")
        success, result = WmsGzbbrLoginService.login_and_get_token(username, password)

        if not success:
            error_msg = result.get("error", "未知登录错误")
            print(f"[失败] 登录失败: {error_msg}")
            print("=" * 80)
            raise Exception(f"WMS 登录失败: {error_msg}")

        print("[成功] API 登录成功")
        new_token = result.get("token", "")

        # 同时保存用户信息到配置
        user_data = result.get("data", {})

        # 4. 保存到数据库 - 直接调用通用函数
        print("\n[4/6] 保存登录信息到数据库...")
        save_result = update_json_config(
            WmsGzbbrLoginService.CONFIG_KEY,
            {
                "token": new_token,
                "username": username,
                "password": password
            }
        )

        if save_result.get("code") != 200:
            error_msg = save_result.get("message", "保存配置失败")
            print(f"[失败] {error_msg}")
            print("=" * 80)
            raise Exception(error_msg)
        print("[成功] 配置保存成功")

        # 5. 再次验证新配置
        print("\n[5/6] 验证新保存的配置...")
        is_valid, error_msg = WmsGzbbrLoginService.validate_token(new_token)

        if is_valid:
            print("[成功] 新配置验证通过")
            print("\n[6/6] 获取有效配置完成")
            print("=" * 80)
            return new_token
        else:
            # 6. 如果还是失败则抛出异常
            print(f"[失败] 新配置验证失败: {error_msg}")
            print("\n[6/6] 配置验证失败，异常抛出")
            print("=" * 80)
            raise Exception(f"新配置验证失败: {error_msg}")

    @staticmethod
    def login_and_get_token(username: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        """
        登录并获取完整登录信息

        Args:
            username: 用户名
            password: 密码

        Returns:
            (是否成功, 结果字典)
            成功: {"token": "...", "data": {...}, ...}
            失败: {"error": "..."}
        """
        login = WmsGzbbrLogin(username, password)
        try:
            success, result = login.login()
            return success, result
        finally:
            login.close()

 


# if __name__ == "__main__":

#     token = WmsGzbbrLoginService.get_valid_config()
#     print(token)
