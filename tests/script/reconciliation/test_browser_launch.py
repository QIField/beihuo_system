# coding:utf-8
"""
对比测试 Chrome 启动耗时，复刻 v5_automation.py 的参数组合。
只打开浏览器并访问金蝶登录页（不登录、不操作），然后关闭。
"""
import logging
import subprocess
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

K3_URL = "http://erp.gzbbr.com/K3Cloud/"
CHROMEDRIVER_PATH = None  # 如需测试固定路径，可在此填写


def _kill_stale(sleep_seconds=1.0):
    for proc in ("chrome.exe", "chromedriver.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)


def _build_options(
    original=True,
    add_user_data_dir=False,
    use_fullscreen=True,
):
    opts = Options()
    if original:
        # 完全复刻 v5_automation.py 原参数
        opts.add_argument("--log-level=1")
        opts.add_experimental_option(
            "excludeSwitches", ["enable-logging", "enable-automation"]
        )
        opts.add_argument("--ignore-certificate-errors")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--window-size=1920x1080")
        if use_fullscreen:
            opts.add_argument("--start-fullscreen")
    else:
        # 精简参数
        opts.add_argument("--log-level=3")
        opts.add_experimental_option("excludeSwitches", ["enable-logging"])
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--start-maximized")

    if add_user_data_dir:
        import tempfile
        user_dir = tempfile.mkdtemp(prefix="chrome_test_")
        opts.add_argument(f"--user-data-dir={user_dir}")

    return opts


def _create_service():
    if CHROMEDRIVER_PATH:
        return Service(executable_path=CHROMEDRIVER_PATH)
    return Service()


def run_once(label, original=True, kill=True, add_user_data_dir=False, use_fullscreen=True):
    print(f"\n=== {label} ===")
    timings = {}

    t0 = time.time()
    if kill:
        _kill_stale(sleep_seconds=1.0)
    timings["kill_stale"] = time.time() - t0

    t1 = time.time()
    opts = _build_options(
        original=original,
        add_user_data_dir=add_user_data_dir,
        use_fullscreen=use_fullscreen,
    )
    timings["build_options"] = time.time() - t1

    t2 = time.time()
    service = _create_service()
    timings["build_service"] = time.time() - t2

    driver = None
    try:
        t3 = time.time()
        driver = webdriver.Chrome(service=service, options=opts)
        timings["webdriver_chrome"] = time.time() - t3

        t4 = time.time()
        driver.get(K3_URL)
        timings["get_k3"] = time.time() - t4

        # 让页面基本稳定，但不操作元素
        time.sleep(2)
    finally:
        if driver:
            driver.quit()

    timings["total"] = time.time() - t0

    for k, v in timings.items():
        print(f"  {k:20s}: {v:6.2f}s")

    return timings


def main():
    rounds = 2
    print(f"测试目标 URL: {K3_URL}")
    print(f"每轮只打开浏览器访问登录页，不登录、不操作金蝶。")

    results = []

    # 测试 1：原参数 + 杀进程
    for i in range(1, rounds + 1):
        results.append(run_once(
            f"原参数 (杀进程) 第 {i}/{rounds} 轮",
            original=True,
            kill=True,
            use_fullscreen=True,
        ))

    # 测试 2：原参数 + 不杀进程
    for i in range(1, rounds + 1):
        results.append(run_once(
            f"原参数 (不杀进程) 第 {i}/{rounds} 轮",
            original=True,
            kill=False,
            use_fullscreen=True,
        ))

    # 测试 3：原参数 + 指定临时 user-data-dir
    for i in range(1, rounds + 1):
        results.append(run_once(
            f"原参数 + 临时 profile 第 {i}/{rounds} 轮",
            original=True,
            kill=True,
            add_user_data_dir=True,
            use_fullscreen=True,
        ))

    # 测试 4：精简参数 + 杀进程
    for i in range(1, rounds + 1):
        results.append(run_once(
            f"精简参数 第 {i}/{rounds} 轮",
            original=False,
            kill=True,
            use_fullscreen=False,
        ))

    print("\n=== 汇总 (total) ===")
    labels = [
        "原参数 (杀进程) 第 1/2 轮",
        "原参数 (杀进程) 第 2/2 轮",
        "原参数 (不杀进程) 第 1/2 轮",
        "原参数 (不杀进程) 第 2/2 轮",
        "原参数 + 临时 profile 第 1/2 轮",
        "原参数 + 临时 profile 第 2/2 轮",
        "精简参数 第 1/2 轮",
        "精简参数 第 2/2 轮",
    ]
    for label, r in zip(labels, results):
        print(f"  {label:35s}: total={r['total']:6.2f}s, chrome={r.get('webdriver_chrome', 0):6.2f}s, get={r.get('get_k3', 0):6.2f}s")


if __name__ == "__main__":
    main()
