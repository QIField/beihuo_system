# -*- coding:utf-8 -*-
# @Time    : 2026/06/04
# @Author  : Mercedes Login Spider
# @Project : beihuo_system
# @File    : mercedes_login.py
# @Software: PyCharm

"""
奔驰网站自动登录模块 - 纯 API 实现
根据HAR文件和JavaScript代码逆向分析实现
"""

import re
import urllib.parse
import json
import base64
from typing import Dict, Optional, Tuple, List
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from app.scripts.spiders.spider_tool import SpiderTool
from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from config.config_list_manager.config_cache import get_config_value


class MercedesLogin:
    """奔驰登录类 - 处理完整的 OAuth2 登录流程"""

    # 基础 URL 配置
    BASE_URL = "https://dalfsc.aftersales.mercedes-benz.com"
    SSO_URL = "https://sso.mercedes-benz.com"
    LOGIN_URL = "https://login.mercedes-benz.com"

    # OAuth2 配置（从 HAR 文件中提取）
    CLIENT_ID = "4ba4df44-3b84-49a0-aecb-d239a3283186"
    REDIRECT_URI = "https://dalfsc.aftersales.mercedes-benz.com/login/oauth2/code/sop-china"
    SCOPE = "openid offline_access"

    def __init__(self, username: str, password: str, timeout: int = 30, retry_count: int = 3):
        """
        初始化登录类

        Args:
            username: 登录用户名
            password: 登录密码
            timeout: 请求超时时间（秒）
            retry_count: 重试次数
        """
        self.username = username
        self.password = password
        self.spider_tool = SpiderTool(timeout=timeout, retry_count=retry_count)
        self.session = self.spider_tool.session
        self.auth_code: Optional[str] = None
        self.state: Optional[str] = None
        self.nonce: Optional[str] = None
        self.csrf_token: Optional[str] = None
        self.ping_resume: Optional[str] = None
        self.login_url_with_params: Optional[str] = None
        self.ref_value: Optional[str] = None
        self.unique_id: Optional[str] = None
        self.public_key_pem: Optional[str] = None
        self.timestamp: Optional[int] = None

    def _generate_state(self) -> str:
        """
        生成随机 state 参数（用于 OAuth2 安全验证）

        Returns:
            str: 随机生成的 state 字符串
        """
        import secrets
        import base64
        random_bytes = secrets.token_bytes(32)
        state = base64.urlsafe_b64encode(random_bytes).rstrip(b'=').decode('utf-8')
        return state

    def _extract_csrf_token(self, html_content: str) -> Optional[str]:
        """
        从 HTML 内容中提取 CSRF token

        Args:
            html_content: HTML 页面内容

        Returns:
            str: 提取到的 CSRF token，如果未找到返回 None
        """
        # 尝试多种方式提取 CSRF token
        patterns = [
            r'name="_csrf"\s+value="([^"]+)"',
            r'"_csrf":"([^"]+)"',
            r'_csrf\s*=\s*["\']([^"\']+)["\']'
        ]

        for pattern in patterns:
            match = re.search(pattern, html_content)  # pyright: ignore[reportArgumentType]
            if match:
                return match.group(1)

        return None

    def _extract_public_key(self, html_content: str) -> Optional[str]:
        """
        从 HTML 内容中提取 RSA 公钥

        Args:
            html_content: HTML 页面内容

        Returns:
            str: 提取到的 PEM 格式公钥，如果未找到返回 None
        """
        pattern = r'data-encryption-key="([^"]+)"'
        match = re.search(pattern, html_content)
        if match:
            return match.group(1)
        return None

    def _encrypt_password_rsa(self, public_key_pem: str, password: str, timestamp: int) -> str:
        """
        使用 RSA-OAEP SHA-256 加密密码

        Args:
            public_key_pem: PEM 格式的公钥
            password: 原始密码
            timestamp: 时间戳

        Returns:
            str: Base64 编码的加密结果
        """
        # 构建加密数据结构
        data = {
            "password": password,
            "timestamp": timestamp
        }
        data_json = json.dumps(data, separators=(',', ':'))

        # 加载公钥
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        # 使用 RSA-OAEP SHA-256 加密
        encrypted = public_key.encrypt(  # pyright: ignore[reportAttributeAccessIssue]
            data_json.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Base64 编码
        return base64.b64encode(encrypted).decode('utf-8')

    def _direct_request(self, url, method="GET", params=None, json=None, data=None, headers=None, allow_redirects=True):
        """
        直接使用 requests 发送请求，绕过 SpiderTool 的限制

        Args:
            url: 请求URL
            method: 请求方法
            params: 查询参数
            json: JSON数据
            data: 表单数据
            headers: 请求头
            allow_redirects: 是否允许重定向

        Returns:
            Response对象
        """
        req_headers = self.session.headers.copy()  # pyright: ignore[reportAttributeAccessIssue]
        if headers:
            req_headers.update(headers)

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json,
                data=data,
                headers=req_headers,
                timeout=self.spider_tool.timeout,
                allow_redirects=allow_redirects
            )
            return response
        except Exception as e:
            print(f"请求异常 | URL: {url} | 错误: {str(e)}")
            return None

    def login(self) -> Tuple[bool, dict]:
        """
        执行完整的登录流程

        Returns:
            Tuple[bool, dict]: (是否成功, 包含结果信息的字典)
            成功时字典格式: {"cookie": str, "customerId": str, "salesOrganizationId": str}
            失败时字典格式: {"error": str}
        """
        try:
            print("=" * 60)
            print("开始奔驰网站登录流程")
            print("=" * 60)

            # 步骤 1: 访问初始页面
            print("\n[步骤 1/8] 访问初始页面...")
            if not self._step1_visit_initial_page():
                return False, {"error": "访问初始页面失败"}

            # 步骤 2: 访问 OAuth2 授权页面并跟随重定向
            print("\n[步骤 2/8] 访问 OAuth2 授权页面...")
            login_html = self._step2_visit_oauth_and_redirect()
            if not login_html:
                return False, {"error": "访问 OAuth2 授权页面失败"}

            # 步骤 3: 从登录页面提取参数
            print("\n[步骤 3/8] 提取登录参数...")
            if not self._step3_extract_parameters(login_html):
                return False, {"error": "提取登录参数失败"}

            # 步骤 4: 提交用户名获取 features
            print("\n[步骤 4/8] 提交用户名获取 features...")
            if not self._step4_submit_username():
                print("警告: 提交用户名失败，继续尝试...")

            # 步骤 5: 获取时间戳
            print("\n[步骤 5/8] 获取时间戳...")
            if not self._step5_get_timestamp():
                print("警告: 获取时间戳失败，使用本地时间...")

            # 步骤 6: 提交登录表单
            print("\n[步骤 6/8] 提交登录表单...")
            if not self._step6_submit_login_form():
                return False, {"error": "提交登录表单失败"}

            # 步骤 7: 完成 OAuth2 回调
            print("\n[步骤 7/7] 完成 OAuth2 回调...")
            if not self._step7_complete_oauth_callback():
                return False, {"error": "完成 OAuth2 回调失败"}

            # 获取最终 Cookie
            cookie = self.get_cookie()
            print(f"\n登录成功!")
            print(f"  Cookie 长度: {len(cookie)}")
            print("=" * 60)

            return True, {
                "cookie": cookie
            }

        except Exception as e:
            print(f"\n登录过程中发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, {"error": f"登录异常: {str(e)}"}

    def _step1_visit_initial_page(self) -> bool:
        """步骤 1: 访问初始页面"""
        url = f"{self.BASE_URL}/sop-china/"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1"
        }
        response = self._direct_request(url, method="GET", headers=headers)

        if response and (response.status_code == 200 or response.status_code == 302):
            print(f"  [成功] 成功访问初始页面")
            return True
        else:
            print(f"  [失败] 访问初始页面失败: {response.status_code if response else '无响应'}")
            return False

    def _step2_visit_oauth_and_redirect(self) -> Optional[str]:
        """步骤 2: 访问 OAuth2 授权页面并跟随所有重定向"""
        # 首先访问 OAuth2 授权端点
        url = f"{self.BASE_URL}/oauth2/authorization/sop-china"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        }
        response = self._direct_request(url, method="GET", headers=headers, allow_redirects=True)

        if not response:
            print(f"  [失败] 访问 OAuth2 授权页面失败")
            return None

        print(f"  [成功] 成功访问 OAuth2 授权页面")

        # 从响应历史中查找 login.mercedes-benz.com 的 URL
        login_url = None
        if hasattr(response, 'history') and response.history:
            for resp in response.history:
                if 'location' in resp.headers:
                    location = resp.headers['location']
                    if 'login.mercedes-benz.com' in location:
                        login_url = location
                        break

        # 如果在历史中没找到，检查当前响应
        if not login_url and 'location' in response.headers:
            location = response.headers['location']
            if 'login.mercedes-benz.com' in location:
                login_url = location

        # 如果还没找到，直接使用最终响应的 URL
        if not login_url and response.url and 'login.mercedes-benz.com' in response.url:
            login_url = response.url

        if login_url:
            print(f"  [成功] 找到登录页面 URL")
            self.login_url_with_params = login_url

            # 访问最终的登录页面
            login_response = self._direct_request(login_url, method="GET")
            if login_response and (login_response.status_code == 200 or login_response.status_code == 302):
                print(f"  [成功] 成功访问登录页面")
                return login_response.text

        print(f"  [失败] 无法获取登录页面内容")
        return None

    def _step3_extract_parameters(self, html_content: str) -> bool:
        """步骤 3: 从登录页面提取必要参数"""
        success = True

        # 提取 CSRF token
        self.csrf_token = self._extract_csrf_token(html_content)
        if self.csrf_token:
            print(f"  [成功] 提取 CSRF Token 成功: {self.csrf_token[:20]}...")
        else:
            print(f"  [失败] 无法提取 CSRF Token")
            success = False

        # 提取 RSA 公钥
        self.public_key_pem = self._extract_public_key(html_content)
        if self.public_key_pem:
            print(f"  [成功] 提取 RSA 公钥成功")
        else:
            print(f"  [失败] 无法提取 RSA 公钥")
            success = False

        # 从保存的登录 URL 中提取 resumePath 等参数
        if self.login_url_with_params:
            parsed_url = urllib.parse.urlparse(self.login_url_with_params)
            query_params = urllib.parse.parse_qs(parsed_url.query)

            self.ping_resume = query_params.get('resumePath', [None])[0]
            self.ref_value = query_params.get('REF', [None])[0]
            self.unique_id = query_params.get('unique_id', [None])[0]

            if self.ping_resume:
                print(f"  [成功] 提取 resumePath 成功: {self.ping_resume[:30]}...")
            if self.ref_value:
                print(f"  [成功] 提取 REF 成功: {self.ref_value[:20]}...")
            if self.unique_id:
                print(f"  [成功] 提取 unique_id 成功: {self.unique_id}")

        return success

    def _step4_submit_username(self) -> bool:
        """步骤 4: 提交用户名获取 features"""
        url = f"{self.LOGIN_URL}/features"
        params = {
            "uid": self.username.upper()
        }
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

        response = self._direct_request(url, method="GET", params=params, headers=headers)

        if response and response.status_code == 200:
            print(f"  [成功] 成功提交用户名")
            try:
                data = response.json()
                print(f"  - 获取到 loginFeature: {data.get('loginFeature', 'unknown')}")
            except:
                pass
            return True
        else:
            print(f"  [失败] 提交用户名失败: {response.status_code if response else '无响应'}")
            return False

    def _step5_get_timestamp(self) -> bool:
        """步骤 5: 从服务器获取时间戳"""
        url = f"{self.LOGIN_URL}/time"
        headers = {
            "Accept": "application/json"
        }

        response = self._direct_request(url, method="GET", headers=headers)

        if response and response.status_code == 200:
            try:
                self.timestamp = response.json()
                print(f"  [成功] 成功获取时间戳: {self.timestamp}")
                return True
            except:
                pass

        # 如果失败，使用本地时间作为备选
        import time
        self.timestamp = int(time.time() * 1000)
        print(f"  [警告] 使用本地时间作为备选: {self.timestamp}")
        return True

    def _step6_submit_login_form(self) -> bool:
        """步骤 6: 提交登录表单"""
        if not self.public_key_pem:
            print("  [失败] 没有 RSA 公钥，无法加密密码")
            return False

        # 加密密码
        encrypted_password = self._encrypt_password_rsa(
            self.public_key_pem,
            self.password,
            self.timestamp  # pyright: ignore[reportArgumentType]
        )

        # 构建表单数据
        form_data = {
            "username": self.username.upper(),
            "password": "",  # 密码字段留空
            "password-encrypted": encrypted_password,
            "pingResume": self.ping_resume or "",
            "instance": "default",
            "usedRememberMeSwitchId": ""
        }

        # 添加 CSRF token
        if self.csrf_token:
            form_data["_csrf"] = self.csrf_token

        # 构建完整的登录 URL
        login_action_url = f"{self.LOGIN_URL}/"

        # 添加自定义请求头
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.LOGIN_URL,
            "Referer": self.login_url_with_params or self.LOGIN_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }

        # 发送 POST 请求（使用 data 参数提交表单）
        response = self._direct_request(
            url=login_action_url,
            method="POST",
            data=form_data,
            headers=headers,
            allow_redirects=True
        )

        if response:
            print(f"  [成功] 登录表单提交，状态码: {response.status_code}")

            # 检查是否包含 code（授权码）
            auth_code_found = False

            # 检查最终 URL
            if hasattr(response, 'url') and 'code=' in response.url:
                print(f"  [成功] 在最终 URL 中找到授权码")
                auth_code_found = True

            # 检查重定向历史
            if hasattr(response, 'history') and response.history:
                for resp in response.history:
                    if 'location' in resp.headers and 'code=' in resp.headers['location']:
                        print(f"  [成功] 在重定向中找到授权码")
                        auth_code_found = True
                        break

            if auth_code_found:
                return True
            else:
                print(f"  [警告] 未找到授权码，但继续尝试")
                return True
        else:
            print(f"  [失败] 登录表单提交失败")
            return False

    def _step7_complete_oauth_callback(self) -> bool:
        """步骤 7: 完成 OAuth2 回调流程"""
        # 访问初始页面确认 Cookie 设置
        url = f"{self.BASE_URL}/sop-china/"
        response = self._direct_request(url, method="GET")

        if response and (response.status_code == 200 or response.status_code == 302):
            print(f"  [成功] OAuth2 回调完成")
            return True
        else:
            print(f"  [失败] OAuth2 回调可能失败，状态码: {response.status_code if response else '无响应'}")
            # 即使失败也继续，因为可能已经有 Cookie
            return True

    def get_cookie(self) -> str:
        """
        获取格式化的 Cookie 字符串

        Returns:
            str: Cookie 字符串，格式为 "key1=value1; key2=value2"
        """
        cookies = self.session.cookies
        cookie_parts = []

        for cookie in cookies:
            cookie_parts.append(f"{cookie.name}={cookie.value}")

        return "; ".join(cookie_parts)

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()


class MercedesLoginService:
    """奔驰登录服务类 - 提供高级功能"""

    @staticmethod
    def login_and_get_cookie(username: str, password: str) -> Tuple[bool, dict]:
        """
        登录并获取完整登录信息

        Args:
            username: 用户名
            password: 密码

        Returns:
            Tuple[bool, dict]: (是否成功, 包含登录信息的字典)
            成功时字典格式: {"cookie": str}
            失败时字典格式: {"error": str}
        """
        login = MercedesLogin(username, password)
        try:
            success, result = login.login()
            return success, result
        finally:
            login.close()

    @staticmethod
    def validate_cookie(cookie, test_part_number="A0002521620"):
        """
        验证 Cookie 是否有效

        Args:
            cookie: Cookie 字符串
            test_part_number: 用于验证的零件编号

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """

        # 从配置中获取客户ID和销售组织ID
        config = get_config_value('mercedes_benz')
        test_customer_id = config.get("customer_id", "193211390")  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        test_sales_organization_id = config.get("sales_organization_id", "O 50000741")  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]



        spider_tool = SpiderTool(timeout=10, retry_count=1)
        try:
            # 直接构造请求参数
            url = "https://dalfsc.aftersales.mercedes-benz.com/api/sop-china/parts-informations"
            params = {
                "partNumber": test_part_number,
                "customerId": test_customer_id,
                "salesOrganizationId": test_sales_organization_id
            }
            headers = {"Cookie": cookie}
            
            print(f"【验证 cookie】请求 {url}")
            response = spider_tool.fetch(url, method="GET", params=params, headers=headers)
            
            if not response:
                return False, "请求失败，无法验证Cookie"
            
            # 检查响应状态码
            if response.status_code == 401:
                return False, "Cookie已过期或无效（401未授权）"
            elif response.status_code == 403:
                return False, "Cookie权限不足（403禁止访问）"
            elif response.status_code != 200:
                return False, f"请求返回异常状态码：{response.status_code}"
            
            # 尝试解析响应
            try:
                response.json()
                # 如果能正常解析JSON，说明cookie有效
                return True, ""
            except:
                # 即使不是JSON，只要状态码是200也认为cookie有效
                return True, ""
                
        except Exception as e:
            return False, f"验证Cookie时发生异常：{str(e)}"
        finally:
            spider_tool.close()

    @staticmethod
    def get_valid_config() -> str:
        """
        获取有效的奔驰配置，按照指定的登录流程
        从数据库获取配置，如果cookie无效则自动使用配置中的username/password重新登录

        登录流程:
        1. 先从数据库获取配置
        2. 验证cookie是否有效
        3. 如果验证失败，调用API登录（使用配置中保存的username/password）
        4. 登录成功后保存到数据库
        5. 再次验证新配置
        6. 如果还是失败则抛出异常

        Returns:
            str: 有效的 cookie 字符串
        """
        print("=" * 80)
        print("开始获取奔驰配置...")
        print("=" * 80)

        # 默认值
        DEFAULT_CUSTOMER_ID = "193211390"
        DEFAULT_SALES_ORG_ID = "O 50000741"

        # 1. 先从数据库获取配置
        print("\n[1/6] 尝试从数据库获取现有配置...")
        config = get_config_value('mercedes_benz')
        
        if config:
            cookie = config.get('cookie')  # pyright: ignore[reportAttributeAccessIssue]
            
            if cookie:
                print("[成功] 从数据库获取到配置")
                
                # 2. 验证cookie是否有效
                print("\n[2/6] 验证数据库中的cookie...")
                is_valid, error_msg = MercedesLoginService.validate_cookie(cookie)
                
                if is_valid:
                    print("[成功] 数据库中的cookie有效，直接使用现有配置")
                    print("=" * 80)
                    return cookie
                else:
                    print(f"[失败] Cookie验证失败: {error_msg}")
                    print("需要重新登录...")
            else:
                print("[失败] 数据库中没有有效的cookie")
        else:
            print("[失败] 数据库中没有找到配置")

        # 从配置中获取登录凭据
        username = config.get('username') if config else None  # pyright: ignore[reportAttributeAccessIssue]
        password = config.get('password') if config else None  # pyright: ignore[reportAttributeAccessIssue]
        
        # 检查是否有登录凭据
        if not username or not password:
            raise Exception("无法登录：配置中没有保存用户名和密码")

        # 3. 调用API登录
        print("\n[3/6] 开始API登录...")
        success, result = MercedesLoginService.login_and_get_cookie(username, password)
        
        if not success:
            error_msg = result.get('error', '未知登录错误')
            print(f"[失败] 登录失败: {error_msg}")
            print("=" * 80)
            raise Exception(f"登录失败: {error_msg}")

        print("[成功] API登录成功")
        new_cookie = result['cookie']

        # 4. 保存到数据库 - 直接调用通用函数
        print("\n[4/6] 保存登录信息到数据库...")
        save_result = update_json_config(
            'mercedes_benz',
            {
                'cookie': new_cookie,
                'customer_id': DEFAULT_CUSTOMER_ID,
                'sales_organization_id': DEFAULT_SALES_ORG_ID
            }
        )
        
        if save_result.get('code') != 200:
            error_msg = save_result.get('message', '保存配置失败')
            print(f"[失败] {error_msg}")
            print("=" * 80)
            raise Exception(error_msg)
        print("[成功] 配置保存成功")

        # 5. 再次验证新配置
        print("\n[5/6] 验证新保存的配置...")
        is_valid, error_msg = MercedesLoginService.validate_cookie(new_cookie)

        if is_valid:
            print("[成功] 新配置验证通过")
            print("\n[6/6] 获取有效配置完成")
            print("=" * 80)
            return new_cookie
        else:
            # 6. 如果还是失败则抛出异常
            print(f"[失败] 新配置验证失败: {error_msg}")
            print("\n[6/6] 配置验证失败，异常抛出")
            print("=" * 80)
            raise Exception(f"新配置验证失败: {error_msg}")
