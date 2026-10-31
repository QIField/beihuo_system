# -*- coding:utf-8 -*-
# @Time    : 2026/10/29
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : oe_diff_scan_task.py
# @Desc    : OE替换号差异扫描与每日发放定时任务
#            每天早上 08:00 执行：
#            1. 增量扫描新增 oe（已扫描的永不重算），补充差异池
#            2. 从差异池取未发放的 100 条，生成当天 Excel
#            3. 通过业务任务系统发布飞书任务给业务员（默认黄锐洪，可用环境变量调整）
#            下载链接：/download_excel/oe_replace_diff/{company}/{YYYYMMDD}

import os
from datetime import datetime, time

from app.services.business_task_service.task_service import TaskService
from app.services.oe_diff_scan_service import (
    EXPORT_CATEGORY,
    db_service,
    export_diff_excel,
    run_daily_scan,
)
from app.routes.excel_download import DOWNLOAD_BASE_URL
from app.utils.logger_config import get_task_logger

logger = get_task_logger('oe_diff_scan')

# 每日发放数量与任务负责人（系统用户ID，默认黄锐洪）
DAILY_LIMIT = int(os.environ.get('OE_DIFF_DAILY_LIMIT', '100'))
ASSIGNEE_ID = int(os.environ.get('OE_DIFF_TASK_ASSIGNEE_ID', '8'))


def _build_download_link(company: str, date_str: str) -> str:
    return f'{DOWNLOAD_BASE_URL}/download_excel/{EXPORT_CATEGORY}/{company}/{date_str}'


def _publish_task(company: str, oes: list, excel_path: str):
    """通过业务任务系统发布任务（自动同步飞书），返回业务任务ID"""
    date_str = datetime.now().strftime('%Y-%m-%d')
    deadline = datetime.combine(datetime.now().date(), time(23, 59))
    detail = TaskService.create_task(
        title=f'OE替换号差异核对任务 {date_str}（{len(oes)}条）',
        content=(
            f'今日差异核对清单共 {len(oes)} 条 OE，请下载附件核对替换号：\n'
            f'{_build_download_link(company, datetime.now().strftime("%Y%m%d"))}'
        ),
        assignee_id=ASSIGNEE_ID,
        deadline=deadline,
        created_by='OE替换号差异扫描',
    )
    task_id = detail.get('id')
    logger.info(f"[定时任务] 业务任务已创建: id={task_id}, Excel: {excel_path}")
    return task_id


def run_oe_diff_scan():
    """执行 OE替换号差异扫描与每日发放定时任务。"""
    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] OE替换号差异扫描开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    company = 'fsbbr'

    # 1. 增量扫描（已扫描的 oe 永不重算）
    scan_result = run_daily_scan(company)
    pool = scan_result['pool']
    logger.info(
        f"[定时任务] 扫描完成: 新扫描 {scan_result['scanned']} 条, "
        f"差异池 共{pool['total_diff']}条/未发放{pool['unassigned']}条"
    )

    # 2. 取未发放的差异 oe（每天限量，发过的永不重复）
    batch = db_service.fetch_unassigned_diff_oes(company, DAILY_LIMIT)
    if not batch:
        logger.info("[定时任务] 差异池已发完，今日无发放")
        return

    # 3. 生成当天 Excel（下载路由复用，文件按日期覆盖）
    excel_path = export_diff_excel(company, batch)

    # 4. 发布业务任务（同步飞书），成功后标记本批已发放
    task_id = _publish_task(company, batch, excel_path)
    db_service.mark_batch_assigned(company, batch, task_id, datetime.now().date())

    logger.info(
        f"[定时任务] 今日发放 {len(batch)} 条, 剩余未发放 {pool['unassigned'] - len(batch)} 条"
    )

    logger.info("\n" + "=" * 80)
    logger.info(f"[定时任务] OE替换号差异扫描完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80 + "\n")


def register_oe_diff_scan_tasks(task_manager):
    """
    注册 OE替换号差异扫描定时任务

    :param task_manager: 任务管理器实例（来自 app.core.task_manager）
    """
    auto_start = os.environ.get('AUTO_START_OE_DIFF_SCAN', 'true').lower() != 'false'
    if not auto_start:
        logger.info("[OE替换号差异扫描] 已禁用")
        return

    try:
        task_manager.schedule(
            run_oe_diff_scan,
            'cron',
            'oe_diff_scan',
            hour=8,
            minute=0,
            replace_existing=True
        )
        logger.info("[OE替换号差异扫描] 定时任务已注册（每天08:00）")
    except Exception as e:
        logger.error(f"[OE替换号差异扫描] 定时任务注册失败: {e}")
