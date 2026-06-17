import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SpiderTool:
    """
    独立通用爬虫工具类
    职责：封装请求、会话、重试、异常、公共请求头
    不绑定任何业务，纯工具
    """
    def __init__(self, timeout=10, retry_count=3):
        self.timeout = timeout
        # 初始化持久化会话
        self.session = self._init_session()
        # 配置请求重试机制
        self._set_retry(retry_count)

    def _init_session(self):
        """初始化会话 + 统一公共请求头"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*"
        })
        return session

    def _set_retry(self, retry_count):
        """配置自动重试（网络波动/5xx错误自动重发）"""
        retry_strategy = Retry(
            total=retry_count,
            backoff_factor=1,
            allowed_methods=["GET", "POST"],
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch(self, url, method="GET", params=None, json=None, headers=None, verify=False):
        """
        统一请求入口（业务类只调用这个方法）
        :param headers: 临时请求头（如Authorization）
        :param verify: 是否验证SSL证书，默认False（CRM接口需要跳过验证）
        """
        # 合并请求头（公共头 + 临时头）
        req_headers = self.session.headers.copy()
        if headers:
            req_headers.update(headers)

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json,
                headers=req_headers,
                timeout=self.timeout,
                verify=verify
            )

            if response.status_code != 200:
                print(f"请求失败 | URL: {url} | 状态码: {response.status_code}")

            return response     # 关键优化：返回原生响应，不做业务截断
            
            
        except requests.exceptions.Timeout:
            print(f"请求超时 | URL: {url}")
        except requests.exceptions.ConnectionError:
            print(f"网络连接失败 | URL: {url}")
        except Exception as e:
            print(f"请求异常 | URL: {url} | 错误: {str(e)}")
        
        return None
    
    
    def close(self):
        """关闭会话连接"""
        self.session.close()
