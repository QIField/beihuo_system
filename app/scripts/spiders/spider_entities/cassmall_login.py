# -*- coding:utf-8 -*-
# @Time    : 2026/06/24 11:41
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : cassmall_login.py
# @Software: trae-cn

"""
开思mall网站自动登录模块
支持两种登录方式：
1. Cookie API 方式（兼容旧代码）：从外部 API 获取已登录的 cookie
2. 账号密码方式（推荐）：使用用户名密码走 OAuth2 完整登录流程

登录流程（账号密码方式）：
1. GET /passport/login 获取登录页及 session cookie
2. GET /passport/captcha/need 检查是否需要滑块验证码
3. POST /passport/login 提交账号密码
4. 跟随 302 重定向完成 OAuth2 授权流程
5. 最终到达 /seller 页面，cookie 即为有效
"""

import base64
import io
import time
from typing import Optional, Tuple, Dict, Any

from app.scripts.spiders.spider_tool import SpiderTool
from app.services.system_setting_service.beihuo_system_config_service import update_json_config
from config.config_list_manager.config_cache import get_config_value

try:
    from PIL import Image, ImageFilter
    import numpy as np
    _CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    _CAPTCHA_SOLVER_AVAILABLE = False


# ===================== 账号密码登录类 =====================

class CassmallLogin:
    """
    开思mall登录类 - 处理完整的账号密码登录流程（含 OAuth2）
    """

    # 基础 URL 配置
    BASE_URL = "https://www.cassmall.com"
    PASSPORT_URL = "https://www.cassmall.com/passport"

    # 接口地址
    LOGIN_PAGE_URL = f"{PASSPORT_URL}/login"
    CAPTCHA_NEED_URL = f"{PASSPORT_URL}/captcha/need"
    CAPTCHA_IMAGE_URL = f"{PASSPORT_URL}/captcha"
    CAPTCHA_VERIFY_URL = f"{PASSPORT_URL}/captcha/verification"
    LOGIN_SUBMIT_URL = f"{PASSPORT_URL}/login"
    SELLER_HOME_URL = f"{BASE_URL}/seller"
    VALIDATE_API_URL = f"{BASE_URL}/member/seller/menu-plus-star?key=PLUS_STAR_MENU"

    # 登录类型
    LOGIN_TYPE_PASSWORD = "PASSWORD"
    LOGIN_TYPE_VERIFYCODE = "VERIFYCODE"

    def __init__(self, username: str, password: str, timeout: int = 30,
                 retry_count: int = 3):
        """
        初始化登录类

        Args:
            username: 登录用户名（手机号）
            password: 登录密码
            timeout: 请求超时时间（秒）
            retry_count: 重试次数
        """
        self.username = username
        self.password = password

        # 初始化爬虫工具
        self.spider_tool = SpiderTool(timeout=timeout, retry_count=retry_count)
        self.session = self.spider_tool.session

    def _direct_request(self, url, method="GET", params=None, json=None, data=None,
                        headers=None, allow_redirects=True):
        """
        直接使用 requests session 发送请求（带自定义头，支持重定向控制）

        Args:
            url: 请求URL
            method: 请求方法
            params: 查询参数
            json: JSON数据
            data: 表单数据
            headers: 请求头
            allow_redirects: 是否允许重定向

        Returns:
            Response对象或None
        """
        req_headers = self.session.headers.copy()
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

    def _step1_visit_seller_and_get_login_page(self) -> bool:
        """
        步骤1: 访问卖家后台，触发 OAuth 重定向，最终到达登录页
        关键：必须通过 OAuth 流程进入登录页，否则登录后无法跳回卖家后台

        Returns:
            bool: 是否成功到达登录页
        """
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1",
        }

        response = self._direct_request(
            self.SELLER_HOME_URL,
            method="GET",
            headers=headers,
            allow_redirects=True
        )

        if not response:
            print("  [失败] 访问卖家后台无响应")
            return False

        final_url = response.url or ''
        if 'passport/login' in final_url and response.status_code == 200:
            print(f"  [成功] 通过 OAuth 流程到达登录页（重定向 {len(response.history)} 次）")
            self._login_page_url = final_url  # 保存实际登录页 URL（含 OAuth 参数）
            return True
        elif 'seller' in final_url and response.status_code == 200:
            print("  [提示] 已有登录态，直接进入卖家后台")
            self._login_page_url = self.LOGIN_PAGE_URL
            return True
        else:
            print(f"  [失败] 未到达登录页，最终URL: {final_url[:100]}")
            return False

    def _step2_check_captcha_need(self) -> Tuple[bool, bool]:
        """
        步骤2: 检查是否需要滑块验证码

        Returns:
            Tuple[bool, bool]: (请求是否成功, 是否需要验证码)
        """
        params = {
            "userName": self.username,
            "data": int(time.time() * 1000)
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": getattr(self, '_login_page_url', self.LOGIN_PAGE_URL),
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self._direct_request(
            self.CAPTCHA_NEED_URL,
            method="GET",
            params=params,
            headers=headers
        )

        if not response or response.status_code != 200:
            print("  [警告] 检查验证码需求失败，默认不需要")
            return False, False

        try:
            data = response.json()
            need_captcha = data.get("data", False)
            if need_captcha:
                print("  [提示] 需要滑块验证码")
            else:
                print("  [成功] 不需要滑块验证码")
            return True, need_captcha
        except Exception:
            print("  [警告] 解析验证码需求响应失败，默认不需要")
            return False, False

    def _detect_gap_x(self, shade_b64: str, cutout_b64: str, y: int) -> int:
        """
        通过 cutout 滑块图与 shade 背景图的边缘匹配，计算缺口左边缘 x 坐标。

        原理：
        - shade 图中缺口位置的边缘轮廓与 cutout 滑块图的边缘轮廓一致
        - 用 FIND_EDGES 提取两者边缘，做归一化互相关匹配
        - 取匹配度最高的 x 作为候选，并在 ±2px 范围内取次优候选

        Args:
            shade_b64: 背景图 base64
            cutout_b64: 滑块图 base64
            y: 服务端返回的缺口 y 坐标

        Returns:
            int: 缺口左边缘 x 坐标（像素）
        """
        shade = np.array(Image.open(io.BytesIO(base64.b64decode(shade_b64))))
        cutout = np.array(Image.open(io.BytesIO(base64.b64decode(cutout_b64))))

        shade_gray = shade.mean(axis=2) if shade.ndim == 3 else shade
        cutout_gray = cutout[:, :, :3].mean(axis=2) if cutout.ndim == 3 else cutout
        ch, cw = cutout_gray.shape
        h, w = shade_gray.shape

        y0 = max(0, int(y))
        y1 = min(h, y0 + ch)
        shade_roi = shade_gray[y0:y1, :]
        if shade_roi.shape[0] < ch:
            cutout_gray = cutout_gray[:shade_roi.shape[0], :]
            ch = shade_roi.shape[0]

        cutout_edges = np.array(
            Image.fromarray(cutout_gray.astype(np.uint8)).filter(ImageFilter.FIND_EDGES),
            dtype=np.float32
        )
        shade_edges = np.array(
            Image.fromarray(shade_roi.astype(np.uint8)).filter(ImageFilter.FIND_EDGES),
            dtype=np.float32
        )

        scores = []
        for x in range(0, shade_edges.shape[1] - cw + 1):
            region = shade_edges[:, x:x + cw]
            a = region - region.mean()
            b = cutout_edges - cutout_edges.mean()
            denom = np.sqrt((a ** 2).sum()) * np.sqrt((b ** 2).sum()) + 1e-8
            score = (a * b).sum() / denom
            scores.append((score, x))
        scores.sort(reverse=True)
        return scores[0][1] if scores else 0

    def _solve_slider_captcha(self, max_retry: int = 5) -> bool:
        """
        自动求解滑块验证码。

        流程：
        1. GET /passport/captcha 获取背景图、滑块图、captchaToken、y
        2. 用边缘匹配计算缺口 x 坐标
        3. POST /passport/captcha/verification 提交 {y, x, captchaToken, userName}
        4. 成功则返回 True，失败则换一张图重试

        Args:
            max_retry: 最大重试次数

        Returns:
            bool: 是否验证通过
        """
        if not _CAPTCHA_SOLVER_AVAILABLE:
            print("  [失败] 缺少 Pillow/numpy 依赖，无法自动识别滑块验证码")
            return False

        for attempt in range(1, max_retry + 1):
            try:
                # 1. 获取验证码图片
                params = {
                    "userName": self.username,
                    "date": int(time.time() * 1000)
                }
                headers = {
                    "Accept": "application/json, text/plain, */*",
                    "Referer": getattr(self, '_login_page_url', self.LOGIN_PAGE_URL),
                    "X-Requested-With": "XMLHttpRequest",
                }
                response = self._direct_request(
                    self.CAPTCHA_IMAGE_URL,
                    method="GET",
                    params=params,
                    headers=headers
                )
                if not response or response.status_code != 200:
                    print(f"  [重试 {attempt}] 获取验证码图片失败")
                    continue

                data = response.json().get("data", {})
                shade_b64 = data.get("shadeImage", "")
                cutout_b64 = data.get("cutoutImage", "")
                captcha_token = data.get("captchaToken", "")
                y = data.get("y", 0)

                if not shade_b64 or not cutout_b64 or not captcha_token:
                    print(f"  [重试 {attempt}] 验证码数据不完整")
                    continue

                # 2. 检测缺口 x
                gap_x = self._detect_gap_x(shade_b64, cutout_b64, y)
                print(f"  [重试 {attempt}] 检测到缺口 x={gap_x}, y={y}")

                # 3. 提交验证（在最佳匹配 ±2px 范围内尝试）
                success = False
                tried = set()
                candidates = []
                for dx in range(-2, 3):
                    xx = gap_x + dx
                    if 0 <= xx < 400 and xx not in tried:
                        tried.add(xx)
                        candidates.append(xx)

                for x in candidates:
                    payload = {
                        "y": y,
                        "x": x,
                        "captchaToken": captcha_token,
                        "userName": self.username
                    }
                    verify_headers = {
                        "Accept": "application/json, text/plain, */*",
                        "Content-Type": "application/json;charset=UTF-8",
                        "Referer": getattr(self, '_login_page_url', self.LOGIN_PAGE_URL),
                        "X-Requested-With": "XMLHttpRequest",
                    }
                    verify_resp = self._direct_request(
                        self.CAPTCHA_VERIFY_URL,
                        method="POST",
                        json=payload,
                        headers=verify_headers
                    )
                    if verify_resp and verify_resp.status_code == 200:
                        try:
                            result = verify_resp.json()
                            if result.get("code") == 200 and result.get("data") is True:
                                print(f"  [成功] 滑块验证通过 (x={x})")
                                success = True
                                break
                        except Exception:
                            pass
                    # 同一 token 验证失败后快速失败，换下一张图
                    break

                if success:
                    return True

                print(f"  [重试 {attempt}] 验证失败，换图重试")
                time.sleep(0.3)

            except Exception as e:
                print(f"  [重试 {attempt}] 验证码求解异常: {str(e)}")
                time.sleep(0.3)

        print("  [失败] 滑块验证码多次重试均未通过")
        return False

    def _step3_save_privacy_agreement(self) -> bool:
        """
        步骤3: 保存隐私协议确认记录
        登录前需要调用此接口，否则可能被拦截

        Returns:
            bool: 是否成功
        """
        payload = {
            "clientId": "CLIENT_CASS_WEB",
            "source": "LOGIN",
            "templateIds": [
                "695cdb1b91feb6000184644f",
                "6960a51527905000016b00ca",
                "66149865c7748b0001616030"
            ],
            "userIdType": "USER_NAME",
            "userId": self.username,
            "userAgent": self.session.headers.get("User-Agent", "")
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": getattr(self, '_login_page_url', self.LOGIN_PAGE_URL),
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self._direct_request(
            f"{self.PASSPORT_URL}/agreements/save-client-agreement-record",
            method="POST",
            json=payload,
            headers=headers
        )

        if not response or response.status_code != 200:
            print("  [警告] 保存隐私协议失败，继续尝试登录")
            return False

        try:
            data = response.json()
            if data.get("code") == 200 and data.get("data") is True:
                print("  [成功] 隐私协议已确认")
                return True
            else:
                print(f"  [警告] 隐私协议返回异常: {data.get('errorMessage', '')}")
                return False
        except Exception:
            print("  [警告] 解析隐私协议响应失败")
            return False

    def _step4_submit_login(self) -> bool:
        """
        步骤4: 提交登录表单（账号密码），跟随 OAuth2 重定向

        Returns:
            bool: 是否登录成功（最终到达 /seller）
        """
        form_data = {
            "logintype": self.LOGIN_TYPE_PASSWORD,
            "msg": "",
            "username": self.username,
            "password": self.password,
            "cellphone": "",
            "verifycode": "",
        }

        login_page = getattr(self, '_login_page_url', self.LOGIN_PAGE_URL)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": self.BASE_URL,
            "Referer": login_page,
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        print(f"  提交登录: username={self.username}")

        # 提交登录并允许跟随所有重定向（OAuth2 完整流程）
        response = self._direct_request(
            login_page,
            method="POST",
            data=form_data,
            headers=headers,
            allow_redirects=True
        )

        if not response:
            print("  [失败] 登录请求无响应")
            return False

        final_url = response.url or ''
        status_code = response.status_code

        print(f"  最终状态码: {status_code}, 重定向 {len(response.history)} 次")
        print(f"  最终URL: {final_url[:120]}")

        if status_code == 200 and '/seller' in final_url:
            print("  [成功] 登录成功，已跳转到卖家后台")
            return True
        elif status_code == 200 and 'passport' in final_url:
            print("  [失败] 登录失败，仍停留在登录页面（请检查账号密码）")
            return False
        else:
            print(f"  [提示] 登录请求完成，状态码: {status_code}")
            return status_code in (200, 302)

    def login(self) -> Tuple[bool, Dict[str, Any]]:
        """
        执行完整的登录流程

        流程：
        1. 访问 /seller 触发 OAuth 重定向，到达登录页（获取 OAuth state）
        2. 检查是否需要滑块验证码
        3. 保存隐私协议确认记录
        4. 提交登录表单，跟随 OAuth2 重定向到 /seller

        Returns:
            Tuple[bool, dict]: (是否成功, 结果字典)
            成功时: {"cookie": str, "cookie_dict": dict}
            失败时: {"error": str}
        """
        try:
            print("=" * 60)
            print(f"开始开思mall登录流程 - 用户: {self.username}")
            print("=" * 60)

            # 步骤1: 访问卖家后台触发 OAuth 流程，到达登录页
            print("\n[步骤 1/4] 访问卖家后台，触发登录重定向...")
            if not self._step1_visit_seller_and_get_login_page():
                return False, {"error": "获取登录页失败"}

            # 步骤2: 检查是否需要验证码，需要则自动求解
            print("\n[步骤 2/4] 检查验证码需求...")
            _, need_captcha = self._step2_check_captcha_need()
            if need_captcha:
                print("[步骤 2/4] 需要滑块验证码，开始自动识别...")
                if not self._solve_slider_captcha():
                    return False, {"error": "滑块验证码识别失败，请手动登录后更新 Cookie"}

            # 步骤3: 保存隐私协议
            print("\n[步骤 3/4] 确认隐私协议...")
            self._step3_save_privacy_agreement()  # 即使失败也继续尝试

            # 步骤4: 提交登录表单
            print("\n[步骤 4/4] 提交登录...")
            if not self._step4_submit_login():
                return False, {"error": "登录提交失败，请检查账号密码"}

            # 获取 cookie
            cookie_str = self.get_cookie_string()
            cookie_dict = self.get_cookie_dict()

            print(f"\n登录成功!")
            print(f"  Cookie 数量: {len(cookie_dict)}")
            print(f"  Cookie 长度: {len(cookie_str)}")
            print("=" * 60)

            return True, {
                "cookie": cookie_str,
                "cookie_dict": cookie_dict,
            }

        except Exception as e:
            print(f"\n登录过程中发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, {"error": f"登录异常: {str(e)}"}

    def get_cookie_dict(self) -> Dict[str, str]:
        """
        获取 cookie 字典

        Returns:
            dict: {cookie_name: cookie_value}
        """
        cookies = self.session.cookies
        result = {}
        for cookie in cookies:
            # 只保留 cassmall.com 域下的 cookie
            if 'cassmall.com' in cookie.domain:
                result[cookie.name] = cookie.value
        return result

    def get_cookie_string(self) -> str:
        """
        获取格式化的 Cookie 字符串（按字母排序，模拟浏览器）

        Returns:
            str: "key1=value1; key2=value2"
        """
        cookie_dict = self.get_cookie_dict()
        return "; ".join([f"{k}={v}" for k, v in sorted(cookie_dict.items(), key=lambda x: x[0])])

    def close(self):
        """关闭会话连接"""
        self.spider_tool.close()


# ===================== 登录服务类 =====================

class CassmallLoginService:
    """
    开思mall登录服务类 - 提供高级功能和便捷方法

    配置存储：
    - 每个公司独立配置 key: cassmall_{company_code}
    - 配置结构: {"username": "...", "password": "...", "cookie": "..."}
    """

    # 配置 key 前缀
    CONFIG_KEY_PREFIX = "cassmall_"

    # 用于验证 cookie 的接口（菜单配置接口，轻量且能准确判断登录态）
    VALIDATE_API_URL = "https://www.cassmall.com/member/seller/menu-plus-star?key=PLUS_STAR_MENU"

    @staticmethod
    def get_config_key(company: str) -> str:
        """
        获取公司对应的配置 key

        Args:
            company: 公司代码（fsbbr/zsbbr/zhbbr/dghf/dgby）

        Returns:
            str: 配置 key
        """
        return f"{CassmallLoginService.CONFIG_KEY_PREFIX}{company}"

    @staticmethod
    def validate_cookie(cookie: str) -> Tuple[bool, str]:
        """
        验证 Cookie 是否有效
        通过调用菜单配置接口，检查是否被重定向到登录页（302）

        判断逻辑：
        - HTTP 302 且 Location 含 oauth2/authorization → Cookie 已过期/无效
        - HTTP 200 且 JSON code == 200 → Cookie 有效
        - 其他状态码 → 异常

        Args:
            cookie: Cookie 字符串

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息或空字符串)
        """
        spider_tool = SpiderTool(timeout=10, retry_count=1)
        try:
            headers = spider_tool.session.headers.copy()
            headers.update({
                "Cookie": cookie,
                "Referer": "https://www.cassmall.com/seller/",
                "X-Requested-With": "XMLHttpRequest",
            })

            print(f"【验证 cookie】请求 {CassmallLoginService.VALIDATE_API_URL}")
            # 直接用 session.request，禁止重定向，以便通过 302 判断登录态
            try:
                response = spider_tool.session.request(
                    method="GET",
                    url=CassmallLoginService.VALIDATE_API_URL,
                    headers=headers,
                    timeout=spider_tool.timeout,
                    allow_redirects=False,
                    verify=False,
                )
            except Exception as e:
                return False, f"请求失败，无法验证Cookie：{str(e)}"

            # 302 重定向到登录授权页 → cookie 失效
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                if "oauth2/authorization" in location:
                    return False, "Cookie已过期或无效（重定向到登录页）"
                return False, f"Cookie已过期（重定向到: {location}）"

            # 非 200 也非 302 → 异常
            if response.status_code != 200:
                return False, f"请求返回异常HTTP状态码：{response.status_code}"

            # HTTP 200，检查 JSON 响应
            try:
                json_data = response.json()
                if isinstance(json_data, dict):
                    code = json_data.get("code")
                    if code is not None and str(code) == "200":
                        return True, ""
                    error_msg = json_data.get("errorMessage", "")
                    return False, f"Cookie验证失败（code: {code}, {error_msg}）"
                # 非 dict 但 HTTP 200，保守认为有效
                return True, ""
            except Exception:
                # 解析失败但 HTTP 200，保守认为有效
                return True, ""

        except Exception as e:
            return False, f"验证Cookie时发生异常：{str(e)}"
        finally:
            spider_tool.close()

    @staticmethod
    def login_and_get_cookie(username: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        """
        使用账号密码登录并获取 cookie

        Args:
            username: 用户名（手机号）
            password: 密码

        Returns:
            Tuple[bool, dict]: (是否成功, 结果字典)
            成功时: {"cookie": str, "cookie_dict": dict}
            失败时: {"error": str}
        """
        login = CassmallLogin(username, password)
        try:
            success, result = login.login()
            return success, result
        finally:
            login.close()

    @staticmethod
    def get_valid_config(company: str = "fsbbr") -> str:
        """
        获取指定公司有效的开思 cookie

        流程:
        1. 从数据库获取配置
        2. 验证 cookie 是否有效
        3. 如果无效，使用配置中的用户名密码重新登录
        4. 登录成功后保存新 cookie 到数据库
        5. 再次验证新 cookie
        6. 验证失败则抛出异常

        Args:
            company: 公司代码（fsbbr/zsbbr/zhbbr/dghf/dgby）

        Returns:
            str: 有效的 cookie 字符串

        Raises:
            Exception: 多次验证失败后抛出异常
        """
        config_key = CassmallLoginService.get_config_key(company)

        print("=" * 80)
        print(f"开始获取开思配置 - 公司: {company}")
        print("=" * 80)

        # 1. 从数据库获取配置
        print(f"\n[1/6] 尝试从数据库获取配置 [{config_key}]...")
        config = get_config_value(config_key)

        if config:
            cookie = config.get("cookie")

            if cookie:
                print("[成功] 从数据库获取到配置")

                # 2. 验证 cookie 是否有效
                print("\n[2/6] 验证数据库中的 cookie...")
                is_valid, error_msg = CassmallLoginService.validate_cookie(cookie)

                if is_valid:
                    print("[成功] 数据库中的 cookie 有效，直接使用现有配置")
                    print("=" * 80)
                    return cookie
                else:
                    print(f"[失败] Cookie 验证失败: {error_msg}")
                    print("需要重新登录...")
            else:
                print("[失败] 数据库中没有有效的 cookie")
        else:
            print("[失败] 数据库中没有找到配置")

        # 从配置中获取登录凭据
        username = config.get("username") if config else None
        password = config.get("password") if config else None

        # 检查是否有登录凭据
        if not username or not password:
            raise Exception(
                f"无法登录：配置 '{config_key}' 中没有保存用户名和密码。"
                f"请在系统设置中添加配置。"
            )

        # 3. 使用账号密码登录
        print("\n[3/6] 开始账号密码登录...")
        success, result = CassmallLoginService.login_and_get_cookie(username, password)

        if not success:
            error_msg = result.get("error", "未知登录错误")
            print(f"[失败] 登录失败: {error_msg}")
            print("=" * 80)
            raise Exception(f"开思登录失败: {error_msg}")

        print("[成功] 账号密码登录成功")
        new_cookie = result.get("cookie", "")

        # 4. 保存到数据库
        print("\n[4/6] 保存登录信息到数据库...")
        save_result = update_json_config(
            config_key,
            {
                "cookie": new_cookie,
                "username": username,
                "password": password,
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
        is_valid, error_msg = CassmallLoginService.validate_cookie(new_cookie)

        if is_valid:
            print("[成功] 新配置验证通过")
            print("\n[6/6] 获取有效配置完成")
            print("=" * 80)
            return new_cookie
        else:
            # 6. 验证失败，抛出异常
            print(f"[失败] 新配置验证失败: {error_msg}")
            print("\n[6/6] 配置验证失败，异常抛出")
            print("=" * 80)
            raise Exception(f"新配置验证失败: {error_msg}")

