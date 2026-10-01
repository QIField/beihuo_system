# -*- coding:utf-8 -*-
"""
奔驰登录测试脚本 —— 【真实代码对齐版】
关键原则：底层库/请求方式/UA/header **完全等同于** mercedes_login.py
  - 不用 curl_cffi，直接用 requests.Session()（和 mercedes_login._direct_request 一致）
  - User-Agent: Chrome/146（和 spider_tool.py 一致）
  - 参数提取：urlparse + parse_qs 从 login_url_with_params 取（和 mercedes_login._step3 一致）
  - 表单 header：Origin / Referer / Content-Type / Cache-Control 全齐（和 mercedes_login._step6 一致）

用途：
  1) 线下跑一次：确认"用真实代码相同栈"能否拿到 PASSWORD 并登录成功 → 排除代码逻辑问题
  2) 线上跑一次：如果线下 PASSWORD 线上 WEBAUTHN，就 100% 坐实是【服务端 IP 风控】，和代码无关

使用：
  
"""

import sys
import os
import json
import time
import re
import base64
import urllib.parse
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ===============================
# 【配置区域】
# ===============================
USERNAME = "D8LINSZ1"
PASSWORD = "Zhoulingshuang1314520#"
TEST_PART_NUMBER = "A0004663740"
TEST_CUSTOMER_ID = "193211390"
TEST_SALES_ORG_ID = "O 50000741"


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests
from requests import Session
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class SimpleMercedesLogin:
    """奔驰登录器 —— 完全对齐 mercedes_login.py 真实流程 + 真实底层库"""

    BASE_URL = "https://dalfsc.aftersales.mercedes-benz.com"
    LOGIN_URL = "https://login.mercedes-benz.com"

    def __init__(self, username, password, timeout=30):
        self.username = username
        self.password = password
        self.timeout = timeout

        # ---------- 100% 和 spider_tool.py._init_session() 保持一致 ----------
        # SpiderTool 初始化 session 时默认就带了这 3 个 header（见 spider_tool.py L22-26）
        # _direct_request 用的是 self.session.headers.copy() + update，
        # 所以真实项目里所有请求"默认"都带着 Accept=application/json,...
        # 只有步骤 1/2/6/7 显式传 headers={Accept: text/html,...} 时才会覆盖
        self.session = Session()
        self.session.headers.update({
            # 和 spider_tool.py L22-26 完全一致
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
        })

        # 参数缓存
        self.login_url_with_params = None
        self.csrf_token = None
        self.public_key_pem = None
        self.timestamp = None
        self.ping_resume = None
        self.ref_value = None
        self.unique_id = None

    # ---------------- 工具：完全对齐 mercedes_login._direct_request ----------------
    def _direct_request(self, url, method="GET", params=None, data=None, json_body=None,
                        headers=None, allow_redirects=True):
        """
        和 mercedes_login._direct_request 签名/实现一一对应：
          - 用 self.session.request(...)
          - headers = session.headers.copy() + update(入参 headers)
          - verify=False（和真实项目一致）
          - timeout=self.timeout
        返回 requests.Response；异常返回 None（且打印完整 traceback，避免之前的"静默 None"）
        """
        req_headers = self.session.headers.copy()
        if headers:
            req_headers.update(headers)

        method = method.upper()
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,   # 注意：session.request 的 json 参数名就是 json
                data=data,
                headers=req_headers,
                timeout=self.timeout,
                allow_redirects=allow_redirects,
                verify=False,
            )
            return response
        except Exception as e:
            print(f"  [请求异常] URL: {url[:160]} | {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ---------------- 步骤 1：访问初始页面 ----------------
    def _step1_visit_initial_page(self) -> bool:
        print("[步骤 1/8] 访问初始页面 ...")
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Upgrade-Insecure-Requests": "1",
        }
        resp = self._direct_request(f"{self.BASE_URL}/sop-china/", headers=headers)
        ok = resp and resp.status_code in (200, 302)
        print("  " + ("[成功] 成功访问初始页面" if ok else
                     f"[失败] 访问初始页面失败 status={resp.status_code if resp else 'None'}"))
        return ok

    # ---------------- 步骤 2：OAuth2 + 2 次跳转拿登录页 HTML ----------------
    def _step2_visit_oauth_and_redirect(self):
        """
        和 mercedes_login._step2_visit_oauth_and_redirect 一一对应：
        1) GET /oauth2/authorization/sop-china  （裸路径，不传 client_id/scope）
        2) 在 history / 响应头 / 最终 url 里找 login.mercedes-benz.com?...
        3) 再 GET 一次那个完整 URL，拿到登录页 HTML
        """
        print("[步骤 2/8] 访问 OAuth2 授权页面 ...")

        url = f"{self.BASE_URL}/oauth2/authorization/sop-china"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }
        resp = self._direct_request(url, method="GET", headers=headers, allow_redirects=True)
        if not resp:
            print("  [失败] 访问 OAuth2 授权页面失败")
            return None
        print("  [成功] 成功访问 OAuth2 授权页面")

        # --- 查找 login.mercedes-benz.com 的完整 URL（含参数） ---
        login_url = None
        if hasattr(resp, "history") and resp.history:
            for r in resp.history:
                if "location" in r.headers:
                    loc = r.headers["location"]
                    if "login.mercedes-benz.com" in loc:
                        login_url = loc
                        break
        if not login_url and "location" in resp.headers:
            loc = resp.headers["location"]
            if "login.mercedes-benz.com" in loc:
                login_url = loc
        if not login_url and resp.url and "login.mercedes-benz.com" in resp.url:
            login_url = resp.url

        if not login_url:
            print("  [失败] 无法获取登录页面 URL")
            return None

        print("  [成功] 找到登录页面 URL")
        # 调试：把完整 URL 打出来，方便排查 query 参数是否齐全
        print(f"  [调试] login_url_with_params = {login_url[:200]}" + ("..." if len(login_url) > 200 else ""))
        self.login_url_with_params = login_url

        # --- 第二次请求：GET 登录页 URL，拿 HTML ---
        login_resp = self._direct_request(login_url, method="GET", allow_redirects=True)
        if login_resp and login_resp.status_code in (200, 302):
            print("  [成功] 成功访问登录页面")
            return login_resp.text

        print("  [失败] 无法获取登录页面内容")
        return None

    # ---------------- 步骤 3：提取登录参数 ----------------
    def _step3_extract_parameters(self, html_content: str) -> bool:
        print("[步骤 3/8] 提取登录参数 ...")
        success = True

        # CSRF：三条正则，和 mercedes_login._extract_csrf_token 完全一致
        self.csrf_token = None
        for p in [
            r'name="_csrf"\s+value="([^"]+)"',
            r'"_csrf":"([^"]+)"',
            r'_csrf\s*=\s*["\']([^"\']+)["\']',
        ]:
            m = re.search(p, html_content)
            if m:
                self.csrf_token = m.group(1)
                break
        if self.csrf_token:
            print(f"  [成功] 提取 CSRF Token 成功: {self.csrf_token[:20]}...")
        else:
            print("  [失败] 无法提取 CSRF Token")
            success = False

        # RSA 公钥：和 mercedes_login._extract_public_key 完全一致
        rsa_match = re.search(r'data-encryption-key="([^"]+)"', html_content)
        self.public_key_pem = rsa_match.group(1) if rsa_match else None
        if self.public_key_pem:
            print("  [成功] 提取 RSA 公钥成功")
        else:
            print("  [失败] 无法提取 RSA 公钥")
            success = False

        # resumePath / REF / unique_id：从 URL query 里取（和 mercedes_login._step3 一致）
        if self.login_url_with_params:
            parsed_url = urllib.parse.urlparse(self.login_url_with_params)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            # parse_qs 官方语义：返回 {key: [val1, val2]}，因此用 [0]
            self.ping_resume = query_params.get("resumePath", [None])[0]
            self.ref_value = query_params.get("REF", [None])[0]
            self.unique_id = query_params.get("unique_id", [None])[0]

            if self.ping_resume:
                print(f"  [成功] 提取 resumePath 成功: {self.ping_resume[:30]}...")
            else:
                print("  [失败] URL 中未找到 resumePath（参数缺失？）")
                success = False
            if self.ref_value:
                print(f"  [成功] 提取 REF 成功: {self.ref_value[:20]}...")
            else:
                print("  [提示] URL 中未找到 REF（可能不影响）")
            if self.unique_id:
                print(f"  [成功] 提取 unique_id 成功: {self.unique_id}")
            else:
                print("  [提示] URL 中未找到 unique_id（可能不影响）")

        return success

    # ---------------- 步骤 4：提交用户名 -> features ----------------
    def _step4_submit_username(self):
        """
        对齐 mercedes_login._step4_submit_username：
          - 基础 Accept 来自 session 默认（application/json, text/plain, */*），然后显式覆盖为 application/json
          - X-Requested-With: XMLHttpRequest
          - uid.upper()
        真实代码即使失败也只打警告继续，所以这里只返回 feature，不做中断逻辑。
        """
        print("[步骤 4/8] 提交用户名 -> 获取 loginFeature ...")
        url = f"{self.LOGIN_URL}/features"
        params = {"uid": self.username.upper()}
        headers = {
            # Referer：用登录页的完整 URL（含参数），模拟"在登录页上输入用户名后发 AJAX"
            "Referer": self.login_url_with_params or f"{self.LOGIN_URL}/",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = self._direct_request(url, method="GET", params=params, headers=headers)

        if resp and resp.status_code == 200:
            print("  [成功] 成功提交用户名")
            try:
                data = resp.json()
                feature = data.get("loginFeature", "")
                print(f"  - 获取到 loginFeature: {feature}")
                # 顺便把所有字段打出来，方便观察
                extra = {k: v for k, v in data.items() if k != "loginFeature"}
                if extra:
                    print(f"  - features 其他字段: {json.dumps(extra, ensure_ascii=False)[:200]}")
                return feature
            except Exception as e:
                print(f"  - 返回非 JSON: {resp.text[:200]}  (err={e})")
                return "__NON_JSON__"
        else:
            print(f"  [失败] 提交用户名失败 status={resp.status_code if resp else 'None'}")
            if resp:
                print(f"  - 响应 body 前 200 字: {resp.text[:200]}")
            return ""

    # ---------------- 步骤 5：获取时间戳 ----------------
    def _step5_get_timestamp(self) -> bool:
        """对齐 mercedes_login._step5_get_timestamp：先 .json()，失败回退本地 ms"""
        print("[步骤 5/8] 获取时间戳 ...")
        url = f"{self.LOGIN_URL}/time"
        headers = {"Accept": "application/json"}
        resp = self._direct_request(url, method="GET", headers=headers)
        if resp and resp.status_code == 200:
            try:
                self.timestamp = resp.json()
                print(f"  [成功] 成功获取时间戳: {self.timestamp}")
                return True
            except Exception:
                pass
        self.timestamp = int(time.time() * 1000)
        print(f"  [警告] 使用本地时间作为备选: {self.timestamp}")
        return True

    # ---------------- 加密 ----------------
    def _encrypt_password_rsa(self):
        """
        对齐 mercedes_login._encrypt_password_rsa：
          - 公钥 PEM
          - json.dumps({"password": pwd, "timestamp": ts}, separators=(",", ":"))
          - RSA OAEP MGF1+SHA256
          - base64
        OAEP 带随机 seed，**每次 encrypt 结果必然不同**，这是正常的（解密端用私钥可还原）。
        """
        public_key = serialization.load_pem_public_key(
            self.public_key_pem.encode("utf-8"),
            backend=default_backend(),
        )
        data = {"password": self.password, "timestamp": self.timestamp}
        data_json = json.dumps(data, separators=(",", ":"))
        # 调试：确认 json 串格式（是否带空格、字段顺序是否正确）
        # 正常应为：{"password":"...","timestamp":1787...} —— 没有空格，password 在前
        print(f"  [调试] 加密前 JSON: {data_json[:80]}... (len={len(data_json)})")

        encrypted = public_key.encrypt(  # type: ignore[attr-defined]
            data_json.encode("utf-8"),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("utf-8")

    # ---------------- 步骤 6：提交登录表单 ----------------
    def _step6_submit_login_form(self) -> bool:
        """
        对齐 mercedes_login._step6_submit_login_form：5 个 header + form 字段全部一致
        注意：真实代码提交的 Content-Type 是 application/x-www-form-urlencoded，
              这会覆盖掉 session 默认的 "Content-Type: application/json"（因为 headers 参数 update）。
              和真实逻辑一致。
        """
        print("[步骤 6/8] 提交登录表单 ...")
        if not self.public_key_pem:
            print("  [失败] 没有 RSA 公钥，无法加密密码")
            return False

        encrypted_password = self._encrypt_password_rsa()

        # 表单 key 顺序/名称 完全对齐 mercedes_login L422-L433
        form_data = {
            "username": self.username.upper(),
            "password": "",
            "password-encrypted": encrypted_password,
            "pingResume": self.ping_resume or "",
            "instance": "default",
            "usedRememberMeSwitchId": "",
        }
        if self.csrf_token:
            form_data["_csrf"] = self.csrf_token

        # 调试：打印提交的字段（除密码加密值本身）
        debug_form = {k: (v if k not in ("password-encrypted", "_csrf") else v[:20] + "...") for k, v in form_data.items()}
        print(f"  [调试] 提交表单字段: {json.dumps(debug_form, ensure_ascii=False)}")

        login_action_url = f"{self.LOGIN_URL}/"

        # 6 个关键 header：和 mercedes_login L439-L446 完全一致（顺序不计）
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.LOGIN_URL,
            "Referer": self.login_url_with_params or self.LOGIN_URL,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        resp = self._direct_request(
            url=login_action_url,
            method="POST",
            data=form_data,
            headers=headers,
            allow_redirects=True,
        )

        if resp:
            print(f"  [成功] 登录表单提交，状态码: {resp.status_code}")
            print(f"  [调试] 最终 URL: {str(resp.url)[:260]}")

            # 如无 code，尝试从最终页面 HTML 里找"错误提示"关键词
            auth_code_found = False
            if hasattr(resp, "url") and "code=" in resp.url:
                print("  [成功] 在最终 URL 中找到授权码")
                auth_code_found = True
            if hasattr(resp, "history") and resp.history:
                for r in resp.history:
                    loc = r.headers.get("location", "")
                    if "code=" in loc:
                        print(f"  [成功] 在重定向中找到授权码 (step: {r.status_code})")
                        auth_code_found = True
                        break

            if auth_code_found:
                return True

            # 无授权码 → 分析最终响应，看是"被打回登录页提示错误"还是"进入其他页"
            print("  [警告] 未找到授权码，开始分析最终响应 ...")
            text = resp.text or ""
            # 常见错误关键词（中英文都尝试）
            error_hits = []
            for kw in [
                "error", "Error", "invalid", "Invalid", "fail", "Fail",
                "wrong", "密码", "用户名", "验证码", "过期", "CSRF", "csrf",
                "Unauthorized", "locked", "Lock", "验证失败", "不正确", "WebAuthn", "webauthn",
            ]:
                if kw in text:
                    # 取命中位置前后 60 字符
                    idx = text.index(kw)
                    snippet = text[max(0, idx - 60): idx + 60].replace("\n", " ").strip()
                    error_hits.append(f"[{kw}] ...{snippet}...")
                    if len(error_hits) >= 5:
                        break
            if error_hits:
                print(f"  [调试] 最终页面疑似错误信息（前 5 条）:")
                for e in error_hits:
                    print("     ·", e[:220])
            else:
                # 如果没错误关键词，dump 前 400 字
                preview = re.sub(r"\s+", " ", text)[:400]
                print(f"  [调试] 最终页面前 400 字: {preview}")

            print("  [警告] 未找到授权码，但按真实代码逻辑 → 仍返回 True 继续")
            return True

        print("  [失败] 登录表单提交失败")
        return False

    # ---------------- 步骤 7：OAuth2 回调收尾 ----------------
    def _step7_complete_oauth_callback(self) -> bool:
        print("[步骤 7/7] 完成 OAuth2 回调 ...")
        url = f"{self.BASE_URL}/sop-china/"
        resp = self._direct_request(url, method="GET")
        if resp and resp.status_code in (200, 302):
            print("  [成功] OAuth2 回调完成")
            # ---- 调试：打印当前 session 里所有 cookie（按域名分组） ----
            self._debug_dump_cookies()
            return True
        print(f"  [失败] OAuth2 回调可能失败 status={resp.status_code if resp else 'None'}，但继续")
        self._debug_dump_cookies()
        return True

    def _debug_dump_cookies(self):
        """按域名分组打印 session cookie 名、长度、路径、过期时间"""
        print("  [调试] 登录完成后 Session Cookie 清单：")
        by_domain = {}
        for c in self.session.cookies:
            by_domain.setdefault(c.domain, []).append(c)
        for dom, cs in by_domain.items():
            print(f"     · Domain: {dom}  共 {len(cs)} 条")
            for c in cs:
                size = len(str(c.value))
                # 敏感：只打印 cookie 名和长度，不打印值
                print(f"       - {c.name:<40s} len={size:<5d} path={c.path} "
                      f"expires={'永久' if not c.expires else time.strftime('%m-%d %H:%M', time.localtime(c.expires))}")
        total = len(self.session.cookies)
        print(f"     【合计 Cookie 数量: {total}】")
        if total == 0:
            print("     ⚠️  Cookie 数量为 0，OAuth2 回调根本没写入任何 cookie！")

    def get_cookie(self) -> str:
        """对齐 mercedes_login.get_cookie：拼接成 'key1=val1; key2=val2' 字符串"""
        parts = []
        for c in self.session.cookies:
            parts.append(f"{c.name}={c.value}")
        return "; ".join(parts)

    # ---------------- 验证 cookie（1:1 对齐 MercedesLoginService.validate_cookie） ----------------
    def validate_cookie(self):
        """
        对齐 [mercedes_login.py] MercedesLoginService.validate_cookie 逻辑：
          - 不用当前登录 session，用一个全新的 requests（模拟线上"从数据库读 cookie 字符串 -> 验证"的场景）
          - 只传 headers={"Cookie": cookie_str}，不依赖 session 上下文
          - 返回 (is_valid, msg)
        这样验证通过，才等于"保存到数据库里的 cookie 在线上批量刷新时能正常使用"。
        """
        print("[验证] 请求零件接口验证 cookie ...")

        cookie_str = self.get_cookie()
        print(f"   - 待验证 Cookie 条目数: {cookie_str.count('=')}")
        print(f"   - 待验证 Cookie 字符串长度: {len(cookie_str)}")
        if not cookie_str:
            return False, "Cookie 字符串为空，登录根本没产生任何 cookie"

        url = f"{self.BASE_URL}/api/sop-china/parts-informations"
        params = {
            "partNumber": TEST_PART_NUMBER,
            "customerId": TEST_CUSTOMER_ID,
            "salesOrganizationId": TEST_SALES_ORG_ID,
        }
        print(f"   - 目标 URL: {url}")
        print(f"   - 请求 params: {json.dumps(params, ensure_ascii=False)}")

        # 全新 requests（不使用任何登录 session 上下文）
        tmp_headers = {
            "User-Agent": self.session.headers.get("User-Agent", ""),
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_str,
        }
        try:
            response = requests.request(
                method="GET",
                url=url,
                params=params,
                headers=tmp_headers,
                timeout=20,
                verify=False,
                allow_redirects=True,   # 允许 302 跟到登录页（cookie 失效时会这样）
            )
        except Exception as e:
            print(f"   ⛔ 验证请求抛出异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False, f"验证Cookie时发生异常：{str(e)}"

        # 分析最终 URL：如果被重定向到了 login.mercedes-benz.com = cookie 完全无效
        final_url = str(response.url)
        print(f"   - 响应状态码: {response.status_code}")
        print(f"   - 最终 URL: {final_url[:240]}")
        if "login.mercedes-benz.com" in final_url:
            return False, "Cookie 无效，请求被重定向回奔驰登录页（401/登出状态）"

        if response.status_code == 401:
            return False, "Cookie 已过期或无效（401未授权）"
        if response.status_code == 403:
            return False, "Cookie 权限不足（403禁止访问）"
        if response.status_code != 200:
            # 非 200：把响应 body 前 500 字 dump 出来看
            body = re.sub(r"\s+", " ", response.text or "")[:500]
            return False, f"请求返回异常状态码 {response.status_code}，响应: {body}"

        # 200：尝试解析 JSON
        try:
            j = response.json()
            preview = json.dumps(j, ensure_ascii=False)[:300]
            print(f"   - 响应 JSON 预览: {preview}")
            # 真实项目 validate_cookie 里 200 就认为有效
            return True, "Cookie 有效（200 且可解析 JSON）"
        except Exception as e:
            # 非 JSON 但 200 也认为有效（和真实代码对齐）
            preview = re.sub(r"\s+", " ", response.text or "")[:300]
            print(f"   - 响应非 JSON，但状态码 200。前 300 字: {preview}")
            return True, f"Cookie 有效（非 JSON 但 200，err={e}）"

    # ---------------- 主流程 ----------------
    def run(self):
        print("=" * 72)
        print("奔驰登录测试 【真实代码对齐版 - requests.Session + Chrome/146】")
        print(f"用户名: {self.username.upper()}")
        print("=" * 72)

        try:
            if not self._step1_visit_initial_page():
                return False

            login_html = self._step2_visit_oauth_and_redirect()
            if not login_html:
                return False

            if not self._step3_extract_parameters(login_html):
                print("\n[步骤 3 提取参数部分失败，仍继续尝试 ...]")

            feature = self._step4_submit_username()

            # --- 关键改动：完全对齐 mercedes_login.login() L222-L225 ---
            # 真实代码：即使 step4 返回 False（失败），也只打印"警告：继续尝试"，
            # 并且**完全不判断 loginFeature 的值**，不管是 PASSWORD / WEBAUTHN / 啥，都继续 step5/6/7。
            # 之前版本遇到 WEBAUTHN 就 return False 是【和真实逻辑不一致的】，这可能是最大的偏差来源。
            if feature and feature not in ("PASSWORD", "NONE", ""):
                print("\n⚠️  注意 loginFeature:", feature)
                if "WEBAUTHN" in feature:
                    print("   → 奔驰推荐 WebAuthn 流，但按真实代码逻辑：仍继续走密码登录。")
                    print("   → （真实项目代码对此值不做任何分支判断，直接提交表单）")
                print()

            # 继续：step5 -> step6 -> step7 -> validate
            self._step5_get_timestamp()

            if not self._step6_submit_login_form():
                return False

            self._step7_complete_oauth_callback()

            ok, msg = self.validate_cookie()
            print("\n" + "=" * 72)
            print("最终结果:", msg)
            print("=" * 72)
            return ok

        except Exception as e:
            print(f"\n⛔ 异常：{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    ok = SimpleMercedesLogin(USERNAME, PASSWORD).run()
    sys.exit(0 if ok else 1)
