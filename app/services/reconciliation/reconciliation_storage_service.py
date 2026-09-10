# -*- coding:utf-8 -*-
"""
reconciliation_storage_service.py —— 开思对账结果文件存储管理（业务层）

负责：
- 结果文件目录管理（static/excel/reconciliation/temp/<task_id>/）
- 收款单模板固定路径
- 结果数量控制（最多保留 MAX_KEEP 份，超出删除最旧的）
- 结果下载 URL 构造

不涉及 HTTP 请求处理，供 API 层调用。
"""
import os
import shutil

from flask import current_app


# ---- 结果文件存放目录（相对于 static 根目录） ----
# 磁盘路径用 os.path.join 拼接（跨平台安全）
RESULT_DIR_NAME = os.path.join("excel", "reconciliation", "temp")
# URL 一律使用正斜杠，避免 Windows 下 os.path.join 产生反斜杠导致下载 URL 失效
RESULT_URL_DIR = "excel/reconciliation/temp"
# 模板固定路径（相对于 static 根目录）
PAY_TEMPLATE_REL_PATH = os.path.join("excel", "reconciliation", "收款单导入模板.xlsx")
# temp 目录最多保留的份数（一份 = 一次对账生成的一个子目录）
MAX_KEEP = 5


def _get_static_dir():
    """获取 static 根目录"""
    return current_app.static_folder or os.path.join(current_app.root_path, "static")


def get_result_dir():
    """获取结果文件存放目录（确保存在）"""
    result_dir = os.path.join(_get_static_dir(), *RESULT_DIR_NAME.split(os.sep))
    os.makedirs(result_dir, exist_ok=True)
    return result_dir


def get_pay_template_path():
    """获取固定收款单模板路径"""
    return os.path.join(_get_static_dir(), *PAY_TEMPLATE_REL_PATH.split(os.sep))


def cleanup_old_results(result_dir=None, max_keep=MAX_KEEP):
    """
    清理结果目录，最多保留 max_keep 份结果。

    每次对账生成一个 task_id 子目录 = 一份结果。
    当子目录数量超过 max_keep 时，按修改时间删除最旧的，保持最多 max_keep 份。

    :param result_dir: 结果存放目录（默认取 get_result_dir()）
    :param max_keep: 最多保留的份数（默认 5）
    """
    if result_dir is None:
        result_dir = get_result_dir()
    try:
        # 只统计子目录（一份结果 = 一个 task_id 目录）
        subdirs = [
            os.path.join(result_dir, d)
            for d in os.listdir(result_dir)
            if os.path.isdir(os.path.join(result_dir, d))
        ]
        # 按修改时间升序排序（最旧的在前）
        subdirs.sort(key=lambda p: os.path.getmtime(p))
        # 超过 max_keep 份，删除最旧的
        while len(subdirs) > max_keep:
            oldest = subdirs.pop(0)
            shutil.rmtree(oldest, ignore_errors=True)
    except Exception:
        # 清理失败不影响主流程
        pass


def build_result_url(task_id, filename):
    """
    构造结果文件的静态下载 URL。

    使用正斜杠拼接（RESULT_URL_DIR），保证在 Windows / Linux 下
    生成的 URL 都一致有效（磁盘路径与 URL 路径分离）。

    :param task_id: 任务 ID
    :param filename: 文件名
    :return: 形如 /static/excel/reconciliation/temp/<task_id>/<filename> 的 URL
    """
    return f"/static/{RESULT_URL_DIR}/{task_id}/{filename}"


def resolve_result_file(task_id, filename):
    """
    解析结果文件的完整磁盘路径（供下载接口使用）。

    :param task_id: 任务 ID
    :param filename: 文件名
    :return: 文件完整路径；不存在返回 None
    """
    file_path = os.path.join(get_result_dir(), task_id, filename)
    if not os.path.exists(file_path):
        return None
    return file_path
