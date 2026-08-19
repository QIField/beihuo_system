# 奔驰大库爬虫改为 TLS 指纹方案

## 问题背景

线上服务器无法自动登录奔驰大库（dalfsc.aftersales.mercedes-benz.com），日志显示 `loginFeature: WEBAUTHN_REGISTER`，
说明奔驰风控系统检测到请求来自「非浏览器环境」（Python requests 的 JA3 TLS 指纹特征明显），要求额外 WebAuthn 验证。

宝马模块（BMW Brilliance）已使用 `curl_cffi` 的 `impersonate="chrome"` 成功解决同类问题，
线上服务器已验证该库可用。本方案将奔驰模块的底层 HTTP 库从 `requests` 替换为 `curl_cffi`，统一 TLS 指纹策略。

## 涉及文件（共 4 个）

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `app/scripts/spiders/spider_tool.py` | 修改 | 核心改动：增加 curl_cffi 支持 |
| `app/scripts/spiders/spider_entities/mercedes_login.py` | 修改 | 登录流程改用 curl_cffi + 修复 bug |
| `app/scripts/spiders/spider_entities/mercedes_dalfsc.py` | 修改（1行） | 启用 curl_cffi |
| `app/services/car_parts_library_service/mercedes_dalfsc_service.py` | 无需修改 | 自动受益 |

---

## 改动一：SpiderTool 增加 curl_cffi 支持

**文件：** `app/scripts/spiders/spider_tool.py`

### 目标

在 SpiderTool 中增加 `curl_cffi` 作为可选后端，所有使用 SpiderTool 的爬虫（奔驰、兆配云等）自动获得 Chrome TLS 指纹伪装能力。

### 具体改动

#### 1.1 导入 curl_cffi（文件顶部，紧跟 import requests 之后）

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3; urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== curl_cffi：伪造 Chrome TLS 指纹 ==========
# 参考 bmw_brilliance.py 的写法
try:
    from curl_cffi import requests as curl_cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("[警告] 奔驰爬虫: 未检测到 curl_cffi 库，请执行: pip install curl_cffi")
```

#### 1.2 在 `__init__` 中增加 `use_curl_cffi` 参数

```python
def __init__(self, timeout=10, retry_count=3, use_curl_cffi=False):
    self.timeout = timeout
    self.use_curl_cffi = use_curl_cffi and CURL_CFFI_AVAILABLE  # 只有在安装且启用时才为 True
    # 初始化持久化会话
    self.session = self._init_session()
    # 配置请求重试机制
    self._set_retry(retry_count)
```

#### 1.3 增加 `_curl_cffi_fetch` 方法（参考 bmw_brilliance.py 的 `_curl_cffi_request`）

```python
def _curl_cffi_fetch(self, url, method="GET", params=None, data=None, json=None, headers=None):
    """
    使用 curl_cffi 发起请求（伪装 Chrome TLS 指纹）
    签名与 fetch() 保持一致，方便调用方无感切换
    :return: curl_cffi Response 对象（API 与 requests.Response 兼容），失败返回 None
    """
    req_headers = self.session.headers.copy()
    if headers:
        req_headers.update(headers)

    try:
        method = method.upper()
        if method == "GET":
            resp = curl_cffi_requests.get(
                url,
                params=params,
                headers=req_headers,
                impersonate="chrome",
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
        elif method == "POST":
            resp = curl_cffi_requests.post(
                url,
                params=params,
                data=data,
                json=json,
                headers=req_headers,
                impersonate="chrome",
                timeout=self.timeout,
                verify=False,
                allow_redirects=True
            )
        else:
            print(f"[警告] 不支持的请求方法: {method}")
            return None

        if resp.status_code != 200:
            print(f"请求失败 | URL: {url} | 状态码: {resp.status_code}")

        return resp

    except Exception as e:
        print(f"请求异常 | URL: {url} | 错误: {e}")
        return None
```

#### 1.4 修改 `fetch()` 方法，根据 `use_curl_cffi` 分流

```python
def fetch(self, url, method="GET", params=None, data=None, json=None, headers=None, verify=False):
    # 如果启用了 curl_cffi 模式，走伪装指纹路径
    if self.use_curl_cffi:
        return self._curl_cffi_fetch(url, method=method, params=params, data=data, json=json, headers=headers)

    # 原有 requests 逻辑保持不变
    req_headers = self.session.headers.copy()
    if headers:
        req_headers.update(headers)

    try:
        response = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            data=data,
            json=json,
            headers=req_headers,
            timeout=self.timeout,
            verify=verify
        )
        if response.status_code != 200:
            print(f"请求失败 | URL: {url} | 状态码: {response.status_code}")
        return response
    except requests.exceptions.Timeout:
        print(f"请求超时 | URL: {url}")
    except requests.exceptions.ConnectionError:
        print(f"网络连接失败 | URL: {url}")
    except Exception as e:
        print(f"请求异常 | URL: {url} | 错误: {str(e)}")
    return None
```

> **注意：** `curl_cffi` 的 Response 对象与 `requests.Response` API 基本兼容
> （`.json()`、`.text`、`.status_code`、`.headers`、`.url`、`.history` 等都可用），
> 上层业务代码不需要修改。

---

## 改动二：MercedesLogin 改用 curl_cffi + 修复 bug

**文件：** `app/scripts/spiders/spider_entities/mercedes_login.py`

### 2.1 修改 `__init__`，传入 `use_curl_cffi=True`

```python
def __init__(self, username: str, password: str, timeout: int = 30, retry_count: int = 3):
    self.username = username
    self.password = password
    # 关键改动：启用 curl_cffi 伪装 Chrome TLS 指纹
    self.spider_tool = SpiderTool(timeout=timeout, retry_count=retry_count, use_curl_cffi=True)
    self.session = self.spider_tool.session
    # ... 其余不变
```

### 2.2 修改 `_direct_request` 方法，改用 `self.spider_tool.fetch`

当前 `_direct_request` 直接调用 `self.session.request`（绕过了 SpiderTool），
导致 curl_cffi 分流不生效。需要改为通过 `self.spider_tool.fetch` 发出请求。

```python
def _direct_request(self, url, method="GET", params=None, json=None, data=None, headers=None, allow_redirects=True):
    """
    直接使用 spider_tool 发送请求（统一走 curl_cffi 或 requests）
    """
    # 注意：allow_redirects 参数在 curl_cffi 模式下固定为 True，与当前逻辑一致
    req_headers = self.session.headers.copy()
    if headers:
        req_headers.update(headers)

    try:
        # 关键改动：通过 spider_tool.fetch 发出，自动走 curl_cffi 路径
        response = self.spider_tool.fetch(
            url=url,
            method=method,
            params=params,
            json=json,
            data=data,
            headers=req_headers
        )
        return response
    except Exception as e:
        print(f"请求异常 | URL: {url} | 错误: {str(e)}")
        return None
```

### 2.3 修复 Bug：`_step6_submit_login_form` 未找到授权码时应返回 False

这是当前线上失败的关键 bug：步骤 6 没拿到 OAuth2 `code=xxx` 授权码，
但代码仍然返回 `True`，导致残缺 cookie 被写入数据库。

```python
def _step6_submit_login_form(self) -> bool:
    # ... 前面的代码不变（加密、构建表单等） ...

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
            # ========== 关键修复：改为返回 False ==========
            # 原代码：print(f"  [警告] 未找到授权码，但继续尝试"); return True
            print(f"  [失败] 未找到授权码，登录失败")
            print(f"  [诊断] 最终 URL: {response.url}")
            if hasattr(response, 'history') and response.history:
                for resp in response.history:
                    if 'location' in resp.headers:
                        print(f"  [诊断] 重定向: {resp.status_code} -> {resp.headers['location']}")
            return False
    else:
        print(f"  [失败] 登录表单提交失败")
        return False
```

### 2.4 修改 `MercedesLoginService.validate_cookie` 也启用 curl_cffi

```python
@staticmethod
def validate_cookie(cookie, test_part_number="A0009063704"):
    # ... 前面的代码不变 ...
    spider_tool = SpiderTool(timeout=10, retry_count=1, use_curl_cffi=True)  # 改动：启用 curl_cffi
    try:
        # ... 后面的代码不变 ...
        response = spider_tool.fetch(url, method="GET", params=params, headers=headers)
        # ...
    finally:
        spider_tool.close()
```

---

## 改动三：MercedesDalfscSpider 确认启用 curl_cffi

**文件：** `app/scripts/spiders/spider_entities/mercedes_dalfsc.py`

```python
class MercedesDalfscSpider:
    def __init__(self, timeout=10, retry_count=3):
        # 核心：实例化独立爬虫工具（组合模式）
        # 改动：启用 curl_cffi 伪装 Chrome TLS 指纹
        self.spider_tool = SpiderTool(timeout, retry_count, use_curl_cffi=True)
        # 直接通过 MercedesLoginService 获取验证通过的 cookie
        self.cookie = MercedesLoginService.get_valid_config()
    # ... 其余不变
```

---

## 安装依赖

线上服务器需要安装 `curl_cffi` 库（宝马模块已经用过，大概率已安装）：

```bash
pip install curl_cffi
```

如果线上环境之前没装过，需要确认编译环境（部分 Linux 需要 `libcurl` 开发包）：

```bash
# CentOS / RHEL
yum install libcurl-devel gcc

# Ubuntu / Debian
apt-get install libcurl4-openssl-dev gcc
```

---

## 验证步骤

### 步骤 1：本地测试

1. 安装 curl_cffi：`pip install curl_cffi`
2. 运行测试脚本确认改动后代码无语法错误：`python tests/test.py`
3. 观察日志，确认步骤 6 不再出现 `[警告] 未找到授权码，但继续尝试`

### 步骤 2：线上部署

1. 确认 `pip list | grep curl_cffi` 已安装，或运行 `pip install curl_cffi`
2. 部署代码更新（4 个文件）
3. 触发一次奔驰数据刷新，观察日志：
   - 期望：`loginFeature` 不再出现 `WEBAUTHN_REGISTER`，而是 `PASSWORD` 或类似值
   - 期望：步骤 6 能找到 `code=xxx` 授权码
   - 期望：最终 `[成功] 新配置验证通过`，不再报 `请求失败，无法验证Cookie`

### 步骤 3：回退方案

如果改动后出现问题，可以直接：
1. 把 `SpiderTool` 的 `use_curl_cffi=True` 改回 `False`（或删掉参数），恢复原 requests 行为
2. 先用手动上传 Cookie 的方式应急

---

## 影响范围

| 模块 | 影响 | 说明 |
|------|------|------|
| 奔驰大库爬虫 | ✅ 修复 | 自动登录 + API 数据爬取全部走 curl_cffi |
| 兆配云爬虫（ZhaoPeiYunSpider） | 🔵 无影响 | 未传 `use_curl_cffi` 参数，默认 False，仍走 requests |
| 宝马爬虫（BMWBrillianceSpider） | 🔵 无影响 | 独立使用 curl_cffi，不依赖 SpiderTool 改动 |
| 其他使用 SpiderTool 的模块 | 🔵 无影响 | 默认 `use_curl_cffi=False`，行为完全不变 |

---

## 补充说明：为什么只改 TLS 指纹就够了？

1. **loginFeature: WEBAUTHN_REGISTER 是风控信号** — 奔驰的风控系统在 TLS 握手阶段检测到 `requests` 的 JA3 指纹（非浏览器特征），
   将请求标记为"自动化脚本"，要求额外验证（WebAuthn）。
2. **curl_cffi 的 `impersonate="chrome"` 能伪造 JA3 指纹** — 它会模拟 Chrome 浏览器的 TLS 参数（密码套件、扩展、曲线等），
   让奔驰服务器认为请求来自真实浏览器，从而走正常的密码登录流程。
3. **宝马模块已成功验证** — 宝马的 `bmw_brilliance.py` 使用完全相同的方案，`curl_cffi` 在你线上服务器已验证可用。
4. **如果改指纹后仍失败** — 说明奔驰风控还检测了 IP 信誉（云服务器 IP 被标记为高风险），
   此时可考虑启用 `zhaopeiyun_benz_fallback` 装饰器降级到兆配云数据源，或联系奔驰申请 IP 白名单。